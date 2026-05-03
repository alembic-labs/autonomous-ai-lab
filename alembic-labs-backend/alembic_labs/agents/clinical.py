"""Clinical agent — biohacker context, ChEMBL bioactivity, mechanism class."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import Fold, KnownPeptide
from ..logging_setup import get_logger
from ..tools import chembl, uniprot
from .base import (
    call_claude,
    extract_json,
    log_agent_run,
    update_agent_status,
)

log = get_logger(__name__)

AGENT_NAME = "CLINICAL"

SYSTEM_PROMPT = """You are the CLINICAL agent of ALEMBIC LABS.

Role: Provide clinical context for a peptide and target — biohacker use patterns, ChEMBL bioactivity data, mechanism class, known binders.

You receive:
- Peptide name, sequence, hypothesis
- Target protein info from UniProt (domains, binding sites)
- ChEMBL data on known binders to target
- Internal data on biohacker use of this peptide

Output valid JSON:
{
  "mechanism_class": "<concise mechanism class, e.g. 'AMPK activator' or 'GLP-1 receptor agonist'>",
  "biohacker_use_summary": "<2-3 paragraphs on how biohackers use this peptide — typical dosages, common stacks, reported effects, regulatory status>",
  "clinical_evidence_level": "STRONG" | "MODERATE" | "WEAK" | "ANECDOTAL",
  "known_activity_profile": {
    "primary_target": "<receptor/protein>",
    "mechanism": "<short mechanism description>",
    "typical_doses": "<typical biohacker dose range>",
    "administration_routes": ["<routes>"]
  },
  "domain_annotations_summary": "<which structural domains are most relevant to peptide-target interaction>",
  "ranked_binding_partners": ["<protein 1 (X experiments)>"]
}

RULES:
- Distinguish clinical evidence from biohacker anecdotal evidence
- Don't endorse use — describe patterns
- Note regulatory grey area honestly
- Be specific about doses (cite ranges from literature/community when known)
- Flag risks if relevant
"""


async def _get_known_peptide(db: AsyncSession, name: str) -> KnownPeptide | None:
    if not name.strip():
        return None
    stmt = select(KnownPeptide).where(KnownPeptide.name.ilike(name))
    return (await db.execute(stmt)).scalars().first()


def _format_chembl(binders: list[dict[str, Any]]) -> str:
    if not binders:
        return "(no ChEMBL data found)"
    rows = []
    for b in binders:
        kd = f"{b['kd_nm']:.1f} nM" if b.get("kd_nm") else "—"
        rows.append(
            f"  {b.get('chembl_id')}: pChEMBL={b.get('pchembl_value')}, Kd={kd}, "
            f"type={b.get('mechanism') or '—'}"
        )
    return "\n".join(rows)


def _format_domains(annot: dict[str, Any]) -> str:
    if not annot:
        return "(no UniProt annotations)"
    domains = annot.get("domains") or []
    sites = annot.get("binding_sites") or []
    out = []
    for d in domains[:8]:
        out.append(
            f"  DOMAIN {d.get('start')}-{d.get('end')}: {d.get('description') or d.get('type')}"
        )
    for s in sites[:8]:
        out.append(
            f"  SITE {s.get('position')}: {s.get('ligand') or '—'} ({s.get('description')})"
        )
    return "\n".join(out) if out else "(none)"


async def run_clinical(db: AsyncSession, fold: Fold) -> dict[str, Any]:
    """Populate Clinical-related fields on ``fold``."""

    started_at = datetime.now(timezone.utc)
    await update_agent_status(
        db,
        AGENT_NAME,
        "ACTIVE",
        current_task="Fetching ChEMBL data",
        fold_id=fold.id,
    )

    error: str | None = None
    parsed: dict[str, Any] = {}
    try:
        # 1. ChEMBL: prefer the Researcher-provided ID, fall back to UniProt
        # cross-reference, and only resort to free-text search if both fail.
        binders: list[dict[str, Any]] = []
        target_chembl_id: str | None = (fold.target_chembl_id or "").strip() or None
        target_lookup_path = "researcher" if target_chembl_id else None

        if not target_chembl_id and fold.target_uniprot_id:
            xref = await chembl.get_target_by_uniprot(fold.target_uniprot_id, limit=1)
            if xref:
                target_chembl_id = xref[0].get("chembl_id")
                if target_chembl_id:
                    target_lookup_path = "uniprot_xref"

        if not target_chembl_id and fold.target_protein:
            results = await chembl.search_target(fold.target_protein, limit=3)
            if results:
                target_chembl_id = results[0].get("chembl_id")
                if target_chembl_id:
                    target_lookup_path = "name_search"

        if target_chembl_id:
            binders = await chembl.get_known_binders(target_chembl_id, limit=10)
        log.info(
            "alembic.clinical.target_resolved",
            fold_id=fold.id,
            target_chembl_id=target_chembl_id,
            path=target_lookup_path,
            binders=len(binders),
        )

        # Backfill the fold's chembl_id field if the Researcher couldn't supply
        # it but we resolved one — saves work in future cycles.
        if target_chembl_id and not fold.target_chembl_id:
            fold.target_chembl_id = target_chembl_id

        # 2. UniProt domain annotations.
        await update_agent_status(
            db,
            AGENT_NAME,
            "ACTIVE",
            current_task="Fetching domain annotations",
            fold_id=fold.id,
        )
        annotations: dict[str, Any] = {}
        if fold.target_uniprot_id:
            annotations = await uniprot.get_domain_annotations(fold.target_uniprot_id)

        # 3. Pull internal biohacker context.
        peptide_row = await _get_known_peptide(db, fold.peptide_name)
        biohacker_use = peptide_row.biohacker_use if peptide_row else ""
        peptide_targets = (
            json.loads(peptide_row.known_targets)
            if peptide_row and peptide_row.known_targets
            else []
        )

        user_message = (
            f"Peptide: {fold.peptide_name} (sequence: {fold.peptide_sequence})\n"
            f"Target protein: {fold.target_protein or '—'} (UniProt: {fold.target_uniprot_id or '—'})\n"
            f"Hypothesis: {fold.hypothesis}\n\n"
            f"INTERNAL BIOHACKER USE NOTES: {biohacker_use or '(none)'}\n"
            f"INTERNAL KNOWN TARGETS: {', '.join(peptide_targets) if peptide_targets else '(none)'}\n\n"
            "CHEMBL TARGET MATCH: "
            + (target_chembl_id or "(none)")
            + "\nCHEMBL KNOWN BINDERS:\n"
            + _format_chembl(binders)
            + "\n\nUNIPROT DOMAIN ANNOTATIONS:\n"
            + _format_domains(annotations)
            + "\n\nProduce the JSON object specified in your system prompt."
        )

        completion = await call_claude(
            model=settings.CLINICAL_MODEL,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=3072,
            temperature=0.3,
        )
        raw = extract_json(completion["text"])
        if not isinstance(raw, dict):
            raise ValueError("expected JSON object from Clinical")
        parsed = raw

        fold.mechanism_class = parsed.get("mechanism_class")
        fold.biohacker_use = parsed.get("biohacker_use_summary") or biohacker_use
        fold.known_activity = json.dumps(
            {
                "profile": parsed.get("known_activity_profile") or {},
                "evidence_level": parsed.get("clinical_evidence_level"),
                "ranked_binding_partners": parsed.get("ranked_binding_partners") or [],
                "internal_targets": peptide_targets,
            }
        )
        fold.known_binders = json.dumps(binders)
        fold.domain_annotations = json.dumps(
            {
                "annotations": annotations,
                "summary": parsed.get("domain_annotations_summary"),
            }
        )
        await db.commit()

        await log_agent_run(
            db,
            fold_id=fold.id,
            agent_name=AGENT_NAME,
            model=settings.CLINICAL_MODEL,
            summary=parsed.get("mechanism_class") or "clinical context",
            input_tokens=completion["input_tokens"],
            output_tokens=completion["output_tokens"],
            cost_usd=completion.get("cost_usd"),
            status="COMPLETED",
            started_at=started_at,
            tags=[
                f"chembl_path:{target_lookup_path or 'none'}",
                f"binders:{len(binders)}",
            ],
        )
    except Exception as err:  # noqa: BLE001
        error = str(err)
        log.exception("alembic.clinical.failed", error=error)
        await db.rollback()
        await log_agent_run(
            db,
            fold_id=fold.id,
            agent_name=AGENT_NAME,
            model=settings.CLINICAL_MODEL,
            summary=None,
            status="FAILED",
            error=error,
            started_at=started_at,
        )
        # Clinical failure is non-fatal — orchestrator decides.
    finally:
        await update_agent_status(db, AGENT_NAME, "IDLE", current_task=None, fold_id=None)

    return parsed
