"""Communicator agent — synthesises the fold report with branched templates and lab memory.

Key differences from the v1 Communicator:

1. **Branched markdown template per verdict.** REFINED, PROMISING, DISCARDED
   (biological), and FAILED (technical) folds each get a different
   research_brief_markdown structure. A failed prediction can't have a
   "Suggested next steps" section the same way a refined one can.

2. **Cross-fold memory.** The Communicator sees the most recent folds for
   the same peptide and the same peptide_class, so it can reference the
   lab's collective findings ("this builds on fold #11 where N-terminal
   acetylation worked"). This turns the lab from a CSV generator into a
   running narrative.

3. **executive_summary vs tweet_draft.** ``executive_summary`` is the
   short, sharable summary the frontend renders at the top of section 04.
   ``tweet_draft`` is a separate field reserved for an actual tweet
   (different format, different length).

4. **Cost monitoring.** All Anthropic calls now persist USD cost; this
   agent also rolls the running ``LabStat.total_cost_usd`` forward.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import AgentRun, Fold, LabStat
from ..logging_setup import get_logger
from .base import (
    call_claude,
    extract_json,
    log_agent_run,
    update_agent_status,
)

log = get_logger(__name__)

AGENT_NAME = "COMMUNICATOR"

SYSTEM_PROMPT = """You are the COMMUNICATOR agent of ALEMBIC LABS.

Role: Synthesize all agent work (Researcher, Literature, Structural, Clinical) into a comprehensive fold report.

Brand voice:
- Honest about in silico limitations always
- Use term "DISTILLATION" or "FOLD"
- Mandatory disclaimers
- Technical but accessible
- No overpromises (never "discovered new drug", always "predicted properties")

You receive: full context from all 4 prior agents, plus recent folds in this lab.

Output valid JSON:
{
  "ai_analysis_tldr": "<3-4 sentence TLDR of the entire fold>",
  "ai_analysis_detailed": "<5-8 paragraph detailed analysis covering: peptide background, target, modification rationale, structure prediction results, biological significance, limitations>",

  "research_brief_markdown": "<full markdown report — STRUCTURE DEPENDS ON VERDICT, see below>",

  "result_summary": "<2-3 sentences for fold list view>",

  "caveats": [
    "in silico prediction only — requires wet lab validation",
    "single-run prediction (not ensembled)",
    "predicted properties may not reflect real-world biological behavior",
    "this is research, not medical advice",
    "<additional fold-specific caveats — heuristic property estimates if relevant>"
  ],

  "executive_summary": "<2-3 sentence sharable summary, ≤300 chars, suitable for the report header>",

  "tweet_draft": "<single tweet, ≤280 chars, with DISTILLATION №X header — twitter format, distinct from executive_summary>"
}

CROSS-FOLD CONTEXT (use it):
The user message may include "RECENT LAB FOLDS" — modifications already
explored on this peptide and on similar peptides. Reference these when
relevant in the research_brief_markdown ("This complements fold #11 where
N-terminal acetylation was tested..."). The lab is a running narrative,
not a series of disconnected experiments.

RESEARCH BRIEF STRUCTURE depends on fold_verdict:

If REFINED (high-confidence success):
## Mechanism of action
## Performance applications
## Modification rationale
## Predicted properties (favourable changes from native)
## Suggested next steps (further variants, validation experiments)

If PROMISING (moderate signal — interesting but not headline):
## Mechanism of action
## Performance applications
## Modification rationale
## Predicted properties (where signal is moderate)
## What would strengthen this signal (additional predictions / experiments)

If DISCARDED (biologically uninformative — predictors worked, signal weak):
## Mechanism of action (background)
## Modification hypothesis (what we tested)
## Why the prediction was uninformative (technical analysis of the metrics)
## What this tells us (negative results are data — what does it rule out?)
## Alternative hypotheses to test (avoid the failure mode)

If FAILED (technical failure — predictors didn't produce usable output):
## Mechanism of action (background)
## Modification hypothesis (what we tested)
## What went wrong technically (analyse pLDDT, agreement, sequence length issues)
## What would be needed (better tools, different approach, ensemble)
## Honest assessment (don't dress up a tool failure as a discovery)

Tweet format example:
"DISTILLATION №247 — refined.
MOTS-c, Lys-7 → Arg substitution.
Predicted binding probability: 0.78.
Confidence pLDDT 0.87.
In silico exploration. Full report on alembic.bio."

executive_summary example:
"Sermorelin D-Ala2 substitution: pLDDT 0.49 on the GHRHR complex — too low for a
confident verdict, but the heuristic stability profile suggests modest gains.
DPP-IV resistance hypothesis remains plausible but needs better tools."
"""


def _safe_json(payload: str | None) -> Any:
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def _format_affinity_for_communicator(fold: Fold) -> str:
    """Render the Boltz-2 affinity numbers in plain language for the agent."""
    parts: list[str] = []
    if fold.binding_probability is not None:
        parts.append(f"Boltz-2 binder probability: {fold.binding_probability:.3f}")
    if fold.binding_pic50 is not None:
        try:
            ic50_nm = (10 ** (-float(fold.binding_pic50))) * 1e9
            parts.append(
                f"Boltz-2 predicted pIC50: {float(fold.binding_pic50):.2f} "
                f"(~{ic50_nm:,.0f} nM IC50)"
            )
        except (TypeError, ValueError):
            parts.append(f"Boltz-2 predicted pIC50: {fold.binding_pic50}")
    if not parts:
        return "Boltz-2 affinity module: no values"
    return "; ".join(parts)


async def _related_folds(
    db: AsyncSession,
    fold: Fold,
    *,
    same_peptide_limit: int = 5,
    same_class_limit: int = 4,
) -> list[Fold]:
    """Gather recent folds relevant for the lab-narrative context."""
    rows: list[Fold] = []

    if fold.peptide_name:
        same = (
            await db.execute(
                select(Fold)
                .where(Fold.peptide_name == fold.peptide_name)
                .where(Fold.id != fold.id)
                .order_by(Fold.created_at.desc())
                .limit(same_peptide_limit)
            )
        ).scalars().all()
        rows.extend(same)

    if fold.peptide_class:
        same_class = (
            await db.execute(
                select(Fold)
                .where(Fold.peptide_class == fold.peptide_class)
                .where(Fold.peptide_name != fold.peptide_name)
                .where(Fold.id != fold.id)
                .order_by(Fold.created_at.desc())
                .limit(same_class_limit)
            )
        ).scalars().all()
        rows.extend(same_class)
    return rows


def _format_related(folds: list[Fold]) -> str:
    if not folds:
        return "(no related folds yet — this is one of the lab's first runs in its niche)"
    out: list[str] = []
    for r in folds:
        verdict = r.fold_verdict or r.status or "PENDING"
        plddt = (
            f", pLDDT {round(r.confidence_plddt, 2)}"
            if r.confidence_plddt is not None
            else ""
        )
        mod = r.modification_description or "—"
        tldr = (r.ai_analysis_tldr or r.result_summary or "")[:200]
        out.append(
            f"  Fold #{r.id} — {r.peptide_name} ({r.peptide_class}) — "
            f"{mod} → {verdict}{plddt}.\n    {tldr}"
        )
    return "\n".join(out)


def _build_user_message(fold: Fold, related: list[Fold]) -> str:
    lit = _safe_json(fold.literature_context) or {}
    works_cited = _safe_json(fold.works_cited) or []
    activity = _safe_json(fold.known_activity) or {}
    binders = _safe_json(fold.known_binders) or []
    domain_summary = (
        (_safe_json(fold.domain_annotations) or {}).get("summary")
        if fold.domain_annotations
        else None
    )

    return (
        f"FOLD №{fold.id}\n"
        f"Title: {fold.title}\n"
        f"Verdict (from Structural agent): {fold.fold_verdict or 'unknown'}\n\n"
        "RESEARCHER OUTPUT:\n"
        f"  Peptide: {fold.peptide_name} ({fold.peptide_sequence})\n"
        f"  Class: {fold.peptide_class}\n"
        f"  Target: {fold.target_protein} "
        f"(UniProt {fold.target_uniprot_id or '—'}, "
        f"ChEMBL {fold.target_chembl_id or '—'}, "
        f"gene {fold.target_gene_symbol or '—'})\n"
        f"  Modification: {fold.modification_description}\n"
        f"  Modified sequence: {fold.modified_sequence or '—'}\n"
        f"  Hypothesis: {fold.hypothesis}\n"
        f"  Rationale: {fold.rationale or '—'}\n"
        f"  Predicted outcome: {fold.predicted_outcome or '—'}\n\n"
        "LITERATURE OUTPUT:\n"
        f"  Key findings summary: {fold.key_findings_summary or '—'}\n"
        f"  Consensus: {lit.get('consensus_view') or '—'}\n"
        f"  Knowledge gaps: {lit.get('knowledge_gaps') or '—'}\n"
        f"  Supporting evidence: {lit.get('supporting_evidence') or '—'}\n"
        f"  Challenging evidence: {lit.get('challenging_evidence') or '—'}\n"
        f"  Works cited: {len(works_cited)} papers\n\n"
        "STRUCTURAL OUTPUT:\n"
        f"  Verdict: {fold.fold_verdict or '—'}\n"
        f"  Caption: {fold.structural_caption or '—'}\n"
        f"  pLDDT: {fold.confidence_plddt}\n"
        f"  pTM: {fold.confidence_ptm} | ipTM: {fold.confidence_iptm}\n"
        f"  Chai-1 agreement: {fold.chai_agreement}\n"
        f"  {_format_affinity_for_communicator(fold)}\n"
        f"  Predicted binding change: {fold.predicted_binding_change}\n"
        "  HEURISTIC peptide profile (sequence-based, not real wet-lab numbers):\n"
        f"    Aggregation propensity: {fold.aggregation_propensity}\n"
        f"    Stability score: {fold.stability_score}\n"
        f"    BBB penetration: {fold.bbb_penetration_score}\n"
        f"    Half-life estimate: {fold.half_life_estimate}\n\n"
        "CLINICAL OUTPUT:\n"
        f"  Mechanism class: {fold.mechanism_class or '—'}\n"
        f"  Biohacker use: {fold.biohacker_use or '—'}\n"
        f"  Activity profile: {json.dumps(activity)[:1000]}\n"
        f"  Known binders ({len(binders)}): top pChEMBL = "
        f"{binders[0].get('pchembl_value') if binders else '—'}\n"
        f"  Domain annotations summary: {domain_summary or '—'}\n\n"
        "RECENT LAB FOLDS (cross-fold memory):\n"
        f"{_format_related(related)}\n\n"
        "Choose the appropriate research_brief_markdown structure based on the "
        "verdict. Reference recent lab folds where they meaningfully connect to "
        "this work. Output the JSON object specified in your system prompt."
    )


async def _bump_lab_stats(db: AsyncSession, fold: Fold) -> None:
    """Recompute the singleton LabStat row after a fold completes."""
    stats = await db.get(LabStat, 1)
    if stats is None:
        return

    from sqlalchemy import func

    stats.total_folds = (
        await db.execute(select(func.count(Fold.id)))
    ).scalar_one() or 0
    stats.refined_count = (
        await db.execute(select(func.count(Fold.id)).where(Fold.status == "REFINED"))
    ).scalar_one() or 0
    stats.promising_count = (
        await db.execute(select(func.count(Fold.id)).where(Fold.status == "PROMISING"))
    ).scalar_one() or 0
    stats.pending_count = (
        await db.execute(select(func.count(Fold.id)).where(Fold.status == "PENDING"))
    ).scalar_one() or 0
    stats.discarded_count = (
        await db.execute(select(func.count(Fold.id)).where(Fold.status == "DISCARDED"))
    ).scalar_one() or 0
    stats.failed_count = (
        await db.execute(select(func.count(Fold.id)).where(Fold.status == "FAILED"))
    ).scalar_one() or 0
    stats.peptides_explored_count = (
        await db.execute(select(func.count(func.distinct(Fold.peptide_name))))
    ).scalar_one() or 0

    # Roll up cost/tokens straight from agent_runs — single SQL pass keeps
    # this cheap even at thousands of folds.
    cost_total = (
        await db.execute(select(func.coalesce(func.sum(AgentRun.cost_usd), 0.0)))
    ).scalar_one() or 0.0
    in_tokens = (
        await db.execute(select(func.coalesce(func.sum(AgentRun.input_tokens), 0)))
    ).scalar_one() or 0
    out_tokens = (
        await db.execute(select(func.coalesce(func.sum(AgentRun.output_tokens), 0)))
    ).scalar_one() or 0
    stats.total_cost_usd = float(cost_total)
    stats.total_tokens_used = int(in_tokens) + int(out_tokens)

    stats.total_cycles = (stats.total_cycles or 0) + 1
    stats.updated_at = datetime.now(timezone.utc)
    await db.commit()


def _final_status(verdict: str | None) -> str:
    """Map the structural verdict to the user-facing fold status."""
    if not verdict:
        return "PENDING"
    v = verdict.upper()
    if v == "REFINED":
        return "REFINED"
    if v == "PROMISING":
        return "PROMISING"
    if v == "FAILED":
        return "FAILED"
    if v == "DISCARDED":
        return "DISCARDED"
    return "PENDING"


def _ensure_heuristic_caveat(caveats: list[str]) -> list[str]:
    """Auto-inject the standard heuristic caveat if the agent forgot it."""
    text = "\n".join(c.lower() for c in caveats)
    if "heuristic" in text or "tango" in text:
        return caveats
    caveats.append(
        "peptide profile metrics (aggregation, stability, BBB, half-life) are "
        "sequence-based heuristics — real values require TANGO/Aggrescan, "
        "QSAR models and PK studies"
    )
    return caveats


async def run_communicator(db: AsyncSession, fold: Fold) -> dict[str, Any]:
    """Generate the full report and finalise the fold status."""

    started_at = datetime.now(timezone.utc)
    await update_agent_status(
        db,
        AGENT_NAME,
        "ACTIVE",
        current_task="Synthesizing fold report",
        fold_id=fold.id,
    )

    error: str | None = None
    parsed: dict[str, Any] = {}
    try:
        related = await _related_folds(db, fold)
        completion = await call_claude(
            model=settings.COMMUNICATOR_MODEL,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_message(fold, related)}],
            max_tokens=6000,
            temperature=0.45,
        )
        raw = extract_json(completion["text"])
        if not isinstance(raw, dict):
            raise ValueError("expected JSON object from Communicator")
        parsed = raw

        caveats = parsed.get("caveats") or []
        if not isinstance(caveats, list):
            caveats = [str(caveats)]
        caveats = _ensure_heuristic_caveat([str(c) for c in caveats])

        fold.ai_analysis_tldr = parsed.get("ai_analysis_tldr")
        fold.ai_analysis_detailed = parsed.get("ai_analysis_detailed")
        fold.research_brief_markdown = parsed.get("research_brief_markdown")
        fold.result_summary = parsed.get("result_summary")
        fold.caveats = json.dumps(caveats)
        # ``executive_summary`` is the new short-form sharable summary; we still
        # accept ``tweet_draft`` as a fallback for older prompt outputs to keep
        # the renderer happy during the transition.
        fold.executive_summary = (
            parsed.get("executive_summary")
            or parsed.get("tweet_draft")
            or fold.result_summary
        )
        fold.tweet_draft = parsed.get("tweet_draft") or fold.executive_summary
        fold.status = _final_status(fold.fold_verdict)
        await db.commit()

        await _bump_lab_stats(db, fold)

        await log_agent_run(
            db,
            fold_id=fold.id,
            agent_name=AGENT_NAME,
            model=settings.COMMUNICATOR_MODEL,
            summary=fold.result_summary or fold.ai_analysis_tldr,
            input_tokens=completion["input_tokens"],
            output_tokens=completion["output_tokens"],
            cost_usd=completion.get("cost_usd"),
            status="COMPLETED",
            started_at=started_at,
            tags=[
                f"verdict:{fold.fold_verdict or 'unknown'}",
                f"related:{len(related)}",
            ],
        )
    except Exception as err:  # noqa: BLE001
        error = str(err)
        log.exception("alembic.communicator.failed", error=error)
        await db.rollback()
        await log_agent_run(
            db,
            fold_id=fold.id,
            agent_name=AGENT_NAME,
            model=settings.COMMUNICATOR_MODEL,
            summary=None,
            status="FAILED",
            error=error,
            started_at=started_at,
        )
    finally:
        await update_agent_status(db, AGENT_NAME, "IDLE", current_task=None, fold_id=None)

    return parsed
