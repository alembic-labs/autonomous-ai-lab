"""Routes for /api/folds and child paths."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import AgentRun, Fold
from ..db.session import get_db
from ..tools.solana_logger import explorer_url_for
from .report_renderer import render_report_html, render_report_json
from .schemas import (
    AgentTraceItem,
    FoldDetail,
    FoldListItem,
    FoldMetricsResponse,
    FoldsListResponse,
)

router = APIRouter(prefix="/api/folds", tags=["folds"])

ALLOWED_SORTS = {
    "newest": Fold.created_at.desc(),
    "oldest": Fold.created_at.asc(),
    "highest_confidence": Fold.confidence_plddt.desc(),
    "lowest_confidence": Fold.confidence_plddt.asc(),
}

LIST_HYPOTHESIS_TRUNCATE = 240


def _safe_json(payload: str | None) -> Any:
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def _truncate(text: str | None, max_len: int) -> str:
    if not text:
        return ""
    return text if len(text) <= max_len else text[: max_len - 1].rstrip() + "…"


@router.get("", response_model=FoldsListResponse)
@router.get("/", response_model=FoldsListResponse)
async def list_folds(
    peptide_class: str | None = Query(None, description="PERFORMANCE/LONGEVITY/etc."),
    status: str | None = Query(
        None, description="PENDING/REFINED/PROMISING/DISCARDED/FAILED"
    ),
    sort: str = Query(
        "newest", description="newest|oldest|highest_confidence|lowest_confidence"
    ),
    search: str | None = Query(
        None,
        description=(
            "Substring filter applied to peptide name, title and target protein "
            "(case-insensitive). Pushed to the database — frontend should not "
            "client-filter the response."
        ),
    ),
    min_confidence: float | None = Query(
        None,
        ge=0.0,
        le=1.0,
        description="Minimum pLDDT (0–1) to include a fold.",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> FoldsListResponse:
    """Paginated, filtered fold listing for the catalog page."""

    stmt = select(Fold)
    count_stmt = select(func.count(Fold.id))
    if peptide_class:
        stmt = stmt.where(Fold.peptide_class == peptide_class.upper())
        count_stmt = count_stmt.where(Fold.peptide_class == peptide_class.upper())
    if status:
        stmt = stmt.where(Fold.status == status.upper())
        count_stmt = count_stmt.where(Fold.status == status.upper())
    if search and search.strip():
        like = f"%{search.strip()}%"
        search_clause = or_(
            Fold.peptide_name.ilike(like),
            Fold.title.ilike(like),
            Fold.target_protein.ilike(like),
            Fold.modification_description.ilike(like),
        )
        stmt = stmt.where(search_clause)
        count_stmt = count_stmt.where(search_clause)
    if min_confidence is not None:
        stmt = stmt.where(Fold.confidence_plddt >= min_confidence)
        count_stmt = count_stmt.where(Fold.confidence_plddt >= min_confidence)

    order_clause = ALLOWED_SORTS.get(sort, ALLOWED_SORTS["newest"])
    stmt = stmt.order_by(order_clause).offset((page - 1) * page_size).limit(page_size)

    rows = list((await db.execute(stmt)).scalars().all())
    total = (await db.execute(count_stmt)).scalar_one() or 0

    items = [
        FoldListItem(
            id=r.id,
            slug=r.slug,
            title=r.title,
            peptide_name=r.peptide_name,
            peptide_class=r.peptide_class,
            modification_description=r.modification_description,
            hypothesis=_truncate(r.hypothesis, LIST_HYPOTHESIS_TRUNCATE),
            status=r.status,
            fold_verdict=r.fold_verdict,
            confidence_plddt=r.confidence_plddt,
            binding_probability=r.binding_probability,
            binding_pic50=r.binding_pic50,
            predicted_binding_change=r.predicted_binding_change,
            created_at=r.created_at,
        )
        for r in rows
    ]

    return FoldsListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


async def _get_or_404(db: AsyncSession, fold_ref: str) -> Fold:
    """Resolve a fold by numeric id, slug, or numeric prefix-of-slug.

    Accepting all three lets the frontend route at any of:
      - ``/folds/12``                                       (legacy)
      - ``/folds/12-sermorelin-d-ala2-substitution``        (slug)
      - ``/folds/sermorelin-d-ala2-substitution``           (slug-only, optional)

    The numeric path stays the cheapest — slug lookups index-scan via the
    ``Fold.slug`` unique index.
    """
    ref = (fold_ref or "").strip()
    if not ref:
        raise HTTPException(status_code=404, detail="fold not found")
    fold: Fold | None = None
    if ref.isdigit():
        fold = await db.get(Fold, int(ref))
    if fold is None:
        # Slug match — try exact, then numeric prefix.
        fold = (
            await db.execute(select(Fold).where(Fold.slug == ref))
        ).scalars().first()
    if fold is None and "-" in ref:
        head = ref.split("-", 1)[0]
        if head.isdigit():
            fold = await db.get(Fold, int(head))
    if fold is None:
        raise HTTPException(status_code=404, detail="fold not found")
    return fold


async def _agent_trace(db: AsyncSession, fold_id: int) -> list[AgentTraceItem]:
    stmt = (
        select(AgentRun)
        .where(AgentRun.fold_id == fold_id)
        .order_by(AgentRun.started_at.asc())
    )
    runs = list((await db.execute(stmt)).scalars().all())
    out: list[AgentTraceItem] = []
    for run in runs:
        duration: float | None = None
        if run.finished_at and run.started_at:
            duration = round(
                (run.finished_at - run.started_at).total_seconds(), 2
            )
        out.append(
            AgentTraceItem(
                agent_name=run.agent_name,
                started_at=run.started_at,
                finished_at=run.finished_at,
                status=run.status,
                model_used=run.model_used,
                summary=run.summary,
                duration_seconds=duration,
            )
        )
    return out


@router.get("/{fold_ref}", response_model=FoldDetail)
async def get_fold(
    fold_ref: str, db: AsyncSession = Depends(get_db)
) -> FoldDetail:
    """Full detail payload for the fold page (all 14 sections).

    ``fold_ref`` accepts either the numeric id (legacy) or a slug.
    """

    fold = await _get_or_404(db, fold_ref)
    trace = await _agent_trace(db, fold.id)

    has_pdb = bool(fold.pdb_file_path) and Path(fold.pdb_file_path).exists()

    detail = FoldDetail(
        id=fold.id,
        slug=fold.slug,
        title=fold.title,
        peptide_name=fold.peptide_name,
        peptide_sequence=fold.peptide_sequence,
        peptide_class=fold.peptide_class,
        modification_description=fold.modification_description,
        modified_sequence=fold.modified_sequence,
        target_protein=fold.target_protein,
        target_uniprot_id=fold.target_uniprot_id,
        target_chembl_id=fold.target_chembl_id,
        target_gene_symbol=fold.target_gene_symbol,
        hypothesis=fold.hypothesis,
        rationale=fold.rationale,
        predicted_outcome=fold.predicted_outcome,
        ai_analysis_tldr=fold.ai_analysis_tldr,
        ai_analysis_detailed=fold.ai_analysis_detailed,
        known_activity=_safe_json(fold.known_activity),
        biohacker_use=fold.biohacker_use,
        mechanism_class=fold.mechanism_class,
        research_brief_markdown=fold.research_brief_markdown,
        confidence_plddt=fold.confidence_plddt,
        confidence_ptm=fold.confidence_ptm,
        confidence_iptm=fold.confidence_iptm,
        chai_agreement=fold.chai_agreement,
        chai1_gated_decision=fold.chai1_gated_decision,
        binding_probability=fold.binding_probability,
        binding_pic50=fold.binding_pic50,
        domain_annotations=_safe_json(fold.domain_annotations),
        structural_caption=fold.structural_caption,
        aggregation_propensity=fold.aggregation_propensity,
        stability_score=fold.stability_score,
        bbb_penetration_score=fold.bbb_penetration_score,
        half_life_estimate=fold.half_life_estimate,
        known_binders=_safe_json(fold.known_binders),
        candidate_variants=_safe_json(fold.candidate_variants),
        agent_trace=trace,
        literature_context=_safe_json(fold.literature_context),
        key_findings_summary=fold.key_findings_summary,
        caveats=_safe_json(fold.caveats),
        has_pdb=has_pdb,
        onchain_hash=fold.onchain_hash,
        onchain_signature=fold.onchain_signature,
        onchain_data_hash=fold.onchain_data_hash,
        onchain_logged_at=fold.onchain_logged_at,
        onchain_explorer_url=explorer_url_for(fold.onchain_signature),
        ipfs_hash=fold.ipfs_hash,
        works_cited=_safe_json(fold.works_cited),
        status=fold.status,
        fold_verdict=fold.fold_verdict,
        predicted_binding_change=fold.predicted_binding_change,
        executive_summary=fold.executive_summary,
        tweet_draft=fold.tweet_draft,
        created_at=fold.created_at,
        updated_at=fold.updated_at,
    )
    return detail


@router.get(
    "/{fold_ref}/structure",
    response_class=PlainTextResponse,
    responses={
        200: {"content": {"chemical/x-pdb": {}}},
        404: {"description": "fold or PDB file not found"},
    },
)
async def get_structure(
    fold_ref: str, db: AsyncSession = Depends(get_db)
) -> PlainTextResponse:
    """Stream the saved PDB file for the 3D viewer."""

    fold = await _get_or_404(db, fold_ref)
    if not fold.pdb_file_path:
        raise HTTPException(status_code=404, detail="no structure stored for this fold")
    path = Path(fold.pdb_file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="structure file missing on disk")
    return PlainTextResponse(
        path.read_text(encoding="utf-8"), media_type="chemical/x-pdb"
    )


def _slug_basename(fold: Fold) -> str:
    """Stable filename stem for downloaded reports — ``0028-tb-500-lactam``."""
    if fold.slug:
        return fold.slug
    return f"fold-{fold.id:04d}"


@router.get("/{fold_ref}/report.html", response_class=HTMLResponse)
@router.get("/{fold_ref}/report", response_class=HTMLResponse)
async def get_report_html(
    fold_ref: str, db: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """Standalone HTML report — single file, no external assets."""

    fold = await _get_or_404(db, fold_ref)
    explorer = explorer_url_for(fold.onchain_signature)
    body = render_report_html(fold, explorer_url=explorer)
    filename = f"{_slug_basename(fold)}-report.html"
    return HTMLResponse(
        content=body,
        headers={
            # ``inline`` so browsers preview the report when the user clicks
            # the link, but the download attribute on the frontend anchor still
            # forces "Save as…" — best of both UX paths.
            "Content-Disposition": f'inline; filename="{filename}"',
            # The orchestrator writes new fields to the fold incrementally, so
            # treat these as fresh on every request.
            "Cache-Control": "no-store",
        },
    )


@router.get("/{fold_ref}/report.json")
async def get_report_json(
    fold_ref: str, db: AsyncSession = Depends(get_db)
) -> JSONResponse:
    """Canonical JSON dump for the downloadable bundle."""

    fold = await _get_or_404(db, fold_ref)
    explorer = explorer_url_for(fold.onchain_signature)
    payload = render_report_json(fold, explorer_url=explorer)
    filename = f"{_slug_basename(fold)}.json"
    return JSONResponse(
        content=payload,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/{fold_ref}/metrics", response_model=FoldMetricsResponse)
async def get_metrics(
    fold_ref: str, db: AsyncSession = Depends(get_db)
) -> FoldMetricsResponse:
    """Plot data for the Folding Metrics section."""

    fold = await _get_or_404(db, fold_ref)
    plot = _safe_json(fold.plot_data) or {}
    return FoldMetricsResponse(
        plddt_per_residue=plot.get("plddt_per_residue"),
        pae_matrix=plot.get("pae_matrix"),
        sequence_coverage=plot.get("sequence_coverage"),
        aggregation_window_scores=plot.get("aggregation_window_scores"),
        confidence_plddt=fold.confidence_plddt,
        confidence_ptm=fold.confidence_ptm,
        confidence_iptm=fold.confidence_iptm,
        chai_agreement=fold.chai_agreement,
        binding_probability=fold.binding_probability,
        binding_pic50=fold.binding_pic50,
    )
