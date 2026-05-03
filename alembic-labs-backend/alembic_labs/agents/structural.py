"""Structural agent — runs Boltz-2 (+ Chai-1) and evaluates the fold.

Three big upgrades over the original:

1. **Numeric verdict tiers.** ``REFINED / PROMISING / DISCARDED / FAILED`` —
   FAILED is a *technical* failure (predictor returned nothing), DISCARDED
   is a biologically uninteresting result with usable metrics, and PROMISING
   captures moderate signals that previously got lumped into DISCARDED.

2. **Boltz-2 affinity in the loop.** The ``affinity_probability_binary`` and
   ``affinity_pred_value`` fields are persisted on the fold and shown to the
   LLM as a primary verdict input — they're Boltz-2's killer feature.

3. **Literature context.** The Literature agent's ``consensus_view`` and
   evidence summary are passed in so the verdict is grounded in published
   knowledge, not just raw confidence numbers.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import Fold
from ..logging_setup import get_logger
from ..tools import aggregation, structure_service, uniprot
from .base import (
    call_claude,
    extract_json,
    log_agent_run,
    update_agent_status,
)

log = get_logger(__name__)

AGENT_NAME = "STRUCTURAL"

SYSTEM_PROMPT = """You are the STRUCTURAL agent of ALEMBIC LABS.

Role: Given peptide + target structure prediction results, evaluate fold quality and produce a structural caption.

You receive:
- Hypothesis and predicted outcome
- Boltz-2 metrics: pLDDT, pTM, ipTM, complex confidence, AND the Boltz-2 affinity module (binder probability + predicted pIC50)
- Chai-1 cross-validation (if available)
- Heuristic peptide profile: aggregation propensity, stability, BBB, half-life
- Literature context from the LITERATURE agent

Output valid JSON:
{
  "fold_verdict": "REFINED" | "PROMISING" | "DISCARDED" | "FAILED",
  "confidence_assessment": "<2-3 sentences honest assessment of prediction quality>",
  "structural_caption": "<3-4 sentence summary of what the structure shows>",
  "result_summary": "<2-4 sentences summary of findings>",
  "key_structural_features": ["<feature 1>", "<feature 2>"],
  "agreement_with_hypothesis": "STRONG" | "MODERATE" | "WEAK" | "CONTRADICTS",
  "agreement_with_literature": "STRONG" | "MODERATE" | "WEAK" | "CONTRADICTS" | "NO_LITERATURE",
  "binding_interpretation": "<1-2 sentences interpreting the Boltz-2 affinity (e.g. 'predicted moderate-affinity binder, ~600nM Kd; consistent with native peptide')>",
  "predicted_binding_change_pct": <number or null>,
  "structural_caveats": ["<caveat 1>", "<caveat 2>"]
}

VERDICT CRITERIA — apply in order, top-down:

FAILED (technical failure — different from biological discarding):
- Both predictors returned errors / no PDB produced
- Use this when there is no usable structural signal because the *tools* failed

REFINED (high confidence, ready to share):
- pLDDT ≥ 0.70 AND
- pTM ≥ 0.50 AND
- ipTM ≥ 0.40 (if interface scored) AND
- Boltz-Chai pLDDT agreement ≥ 0.70 (if both available)
- Boltz-2 binder probability ≥ 0.60 (if available)

PROMISING (moderate signal, worth flagging but not headline):
- pLDDT 0.55–0.70 OR ipTM 0.30–0.40, AND
- No serious structural disagreement with literature
- Note this in caveats but still publish

DISCARDED (biologically uninformative, but the tools worked):
- pLDDT < 0.55 with no rescuing metric (low ipTM, low binder probability)
- OR sequence too long for reliable peptide-target prediction (>500 aa total)
- OR known failure mode (high disorder, etc.)

LITERATURE GROUNDING:
- If the literature consensus suggests a specific binding mode and the
  prediction contradicts it, set agreement_with_literature to CONTRADICTS
  and flag the disagreement in structural_caveats.
- If literature supports the prediction, mention it briefly in
  confidence_assessment.

RULES:
- Honest about limitations (in silico, single run, no wet lab).
- Don't overclaim — predicted ≠ real.
- Flag low-confidence clearly.
- Reference the Boltz-2 affinity numbers explicitly when available.
- If Chai-1 disagrees significantly with Boltz-2, flag this.
"""


def _normalise_plddt(value: float | None) -> float | None:
    """Normalise pLDDT to 0–1 regardless of source convention (0–1 or 0–100)."""
    if value is None:
        return None
    return value / 100 if value > 1.5 else value


def _format_affinity(boltz: dict[str, Any]) -> str:
    """Render the Boltz-2 affinity module output as a human-readable block."""
    prob = boltz.get("binding_probability")
    pic50 = boltz.get("binding_pic50")
    if prob is None and pic50 is None:
        return "  (Boltz-2 affinity module returned no values)"
    parts: list[str] = []
    if prob is not None:
        parts.append(f"  Binder probability: {prob:.3f}")
    if pic50 is not None:
        # pIC50 → IC50 conversion: IC50 = 10^(-pIC50) M; convert to nM.
        try:
            ic50_nm = (10 ** (-float(pic50))) * 1e9
            parts.append(
                f"  Predicted pIC50: {float(pic50):.2f} (~{ic50_nm:,.0f} nM IC50)"
            )
        except (TypeError, ValueError):
            parts.append(f"  Predicted pIC50: {pic50}")
    return "\n".join(parts)


def _format_literature(fold: Fold) -> str:
    """Pull a compact literature snippet for the Structural agent."""
    raw = fold.literature_context or ""
    if not raw:
        return "(no literature context available)"
    try:
        ctx = json.loads(raw)
    except json.JSONDecodeError:
        return "(literature context unparseable)"
    parts: list[str] = []
    consensus = ctx.get("consensus_view")
    if consensus:
        parts.append(f"Consensus view: {str(consensus)[:600]}")
    support = ctx.get("supporting_evidence")
    if support:
        parts.append(f"Supporting evidence: {str(support)[:400]}")
    challenge = ctx.get("challenging_evidence")
    if challenge:
        parts.append(f"Challenging evidence: {str(challenge)[:400]}")
    gaps = ctx.get("knowledge_gaps")
    if gaps:
        parts.append(f"Knowledge gaps: {str(gaps)[:300]}")
    return "\n".join(parts) if parts else "(literature context empty)"


def _build_user_message(
    fold: Fold,
    boltz: dict[str, Any],
    chai: dict[str, Any] | None,
    agreement: float | None,
    profile: dict[str, Any],
) -> str:
    chai_block = (
        (
            f"\n  pLDDT: {chai.get('plddt')}\n  pTM: {chai.get('ptm')}\n"
            f"  ipTM: {chai.get('iptm')}\n  Agreement (Boltz-Chai): {agreement}"
        )
        if chai
        else "(disabled or unavailable)"
    )
    return (
        f"Hypothesis: {fold.hypothesis}\n"
        f"Predicted outcome: {fold.predicted_outcome or '—'}\n"
        f"Modification: {fold.modification_description}\n\n"
        "BOLTZ-2 RESULTS:\n"
        f"  pLDDT: {boltz.get('plddt')}\n"
        f"  pTM: {boltz.get('ptm')}\n"
        f"  ipTM: {boltz.get('iptm')}\n"
        f"  Success: {boltz.get('success')}\n"
        f"  Error: {boltz.get('error') or '—'}\n"
        "BOLTZ-2 AFFINITY MODULE:\n"
        f"{_format_affinity(boltz)}\n\n"
        f"CHAI-1 RESULTS: {chai_block}\n\n"
        "HEURISTIC PEPTIDE PROFILE (sequence-based estimates):\n"
        f"  Aggregation propensity: {profile['aggregation']['overall_score']} "
        "(heuristic — Kyte-Doolittle hydrophobicity proxy)\n"
        f"  Hotspots: {profile['aggregation']['hotspots']}\n"
        f"  Stability score: {profile['stability']} (heuristic — charge/proline)\n"
        f"  BBB penetration: {profile['bbb']} (heuristic — hydrophobic fraction)\n"
        f"  Half-life estimate: {profile['half_life']} (heuristic — length bucket)\n\n"
        "LITERATURE CONTEXT (from LITERATURE agent):\n"
        f"{_format_literature(fold)}\n\n"
        "Apply the verdict criteria in order. Reference the Boltz-2 affinity "
        "numbers and the literature context in your assessment. Output the JSON "
        "object specified in your system prompt."
    )


def _classify_failure(boltz: dict[str, Any], chai: dict[str, Any] | None) -> bool:
    """True if both predictors produced no usable structural output.

    When Chai-1 was deliberately skipped by the adaptive gate we still want
    to count it as "no failure" — the absence of a Chai-1 result is by
    design, not a tooling problem. Pass ``chai=None`` only for the actual
    "skipped/disabled" path; the orchestrator separates this from "ran but
    errored" via the gating decision string.
    """
    boltz_failed = (
        not boltz.get("success") or not boltz.get("pdb_text") or boltz.get("plddt") is None
    )
    chai_failed = chai is not None and (
        not chai.get("success") or chai.get("plddt") is None
    )
    return boltz_failed and chai_failed


def _decide_chai1_gate(
    *,
    boltz_plddt: float | None,
    has_target_sequence: bool,
) -> str:
    """Decide whether to run Chai-1 cross-validation for this fold.

    Returns one of ``CHAI1_GATING_DECISIONS`` from ``db.models``. The string
    drives both the structural-agent flow (RAN_* → run Chai-1, SKIPPED_*/
    DISABLED → don't) and the persisted ``Fold.chai1_gated_decision`` column
    that the frontend renders as a transparency caption.

    Order of precedence:
    1. If creds aren't configured for the active provider → DISABLED.
    2. ``ENABLE_CHAI1=true`` (legacy) wins → RAN_FORCED, no matter the pLDDT.
    3. ``ENABLE_CHAI1_ADAPTIVE=true`` runs Chai-1 only inside the
       borderline band [GATE_LOW, GATE_HIGH]. Above GATE_HIGH the Boltz-2
       result is confident enough to publish; below GATE_LOW the structure
       is already too noisy for cross-val to clarify (it would just confirm
       "everything's bad" without adding scientific signal).
    4. Otherwise → DISABLED.

    A missing ``boltz_plddt`` (Boltz-2 itself failed) is treated as "below
    LOW" — we don't waste a Chai-1 call on a structure with no baseline.

    ``has_target_sequence=False`` short-circuits: Chai-1 cross-validation
    only makes sense for peptide-target complexes, never for solo peptide
    folding (Chai-1 would just regenerate Boltz-2's no-target output).
    """
    if not settings.chai1_credentials_available:
        return "DISABLED"
    if not has_target_sequence:
        # No interface = no meaningful cross-validation. Treat as DISABLED
        # so the UI doesn't claim "skipped due to high/low pLDDT" — the real
        # reason is structural (no second chain).
        return "DISABLED"
    if settings.ENABLE_CHAI1:
        return "RAN_FORCED"
    if not settings.ENABLE_CHAI1_ADAPTIVE:
        return "DISABLED"

    plddt = _normalise_plddt(boltz_plddt)
    if plddt is None:
        return "SKIPPED_LOW_CONFIDENCE"
    low = settings.CHAI1_GATE_PLDDT_LOW
    high = settings.CHAI1_GATE_PLDDT_HIGH
    if plddt > high:
        return "SKIPPED_HIGH_CONFIDENCE"
    if plddt < low:
        return "SKIPPED_LOW_CONFIDENCE"
    return "RAN_BORDERLINE"


def _coerce_verdict(raw: str | None, *, technical_failure: bool) -> str:
    """Coerce the LLM's verdict into one of the four canonical tiers."""
    candidate = (raw or "").strip().upper()
    valid = {"REFINED", "PROMISING", "DISCARDED", "FAILED"}
    if technical_failure:
        return "FAILED"
    if candidate in valid:
        return candidate
    if candidate == "PENDING":  # legacy verdict from earlier prompt versions
        return "PROMISING"
    return "DISCARDED"


async def run_structural(db: AsyncSession, fold: Fold) -> dict[str, Any]:
    """Run structure prediction + LLM verdict; populate fold structural fields."""

    started_at = datetime.now(timezone.utc)
    await update_agent_status(
        db,
        AGENT_NAME,
        "ACTIVE",
        current_task="Fetching target sequence",
        fold_id=fold.id,
    )

    error: str | None = None
    parsed: dict[str, Any] = {}
    try:
        if not fold.target_sequence and fold.target_uniprot_id:
            entry = await uniprot.get_protein_by_id(fold.target_uniprot_id)
            if entry:
                fold.target_sequence = entry.get("sequence")
                await db.commit()

        peptide_seq = fold.modified_sequence or fold.peptide_sequence

        await update_agent_status(
            db,
            AGENT_NAME,
            "ACTIVE",
            current_task="Submitting fold to Boltz-2",
            fold_id=fold.id,
        )
        boltz = await structure_service.run_boltz2_fold(
            peptide_seq,
            target_sequence=fold.target_sequence,
            target_uniprot=fold.target_uniprot_id,
        )

        chai: dict[str, Any] | None = None
        agreement: float | None = None
        # Adaptive gate: Boltz-2 has already run, so we have its pLDDT in
        # hand. Decide whether spending another Boltz-class call on Chai-1
        # actually adds signal. The decision is persisted on the fold for
        # transparency and counted in LabStat for the /lab metrics block.
        boltz_plddt_raw = boltz.get("plddt")
        chai1_decision = _decide_chai1_gate(
            boltz_plddt=boltz_plddt_raw,
            has_target_sequence=bool(fold.target_sequence),
        )
        log.info(
            "alembic.structural.chai1_decision",
            fold_id=fold.id,
            decision=chai1_decision,
            boltz_plddt=_normalise_plddt(boltz_plddt_raw),
            gate_low=settings.CHAI1_GATE_PLDDT_LOW,
            gate_high=settings.CHAI1_GATE_PLDDT_HIGH,
            adaptive=settings.ENABLE_CHAI1_ADAPTIVE,
            forced=settings.ENABLE_CHAI1,
        )
        fold.chai1_gated_decision = chai1_decision

        if chai1_decision in {"RAN_BORDERLINE", "RAN_FORCED"}:
            await update_agent_status(
                db,
                AGENT_NAME,
                "ACTIVE",
                current_task="Cross-validating with Chai-1",
                fold_id=fold.id,
            )
            chai = await structure_service.run_chai1_fold(
                peptide_seq, target_sequence=fold.target_sequence
            )
            if (
                boltz.get("plddt") is not None
                and chai.get("plddt") is not None
            ):
                b = boltz["plddt"] if boltz["plddt"] <= 1.5 else boltz["plddt"] / 100
                c = chai["plddt"] if chai["plddt"] <= 1.5 else chai["plddt"] / 100
                agreement = round(max(0.0, 1.0 - abs(b - c)), 3)

        if boltz.get("pdb_text"):
            fold.pdb_file_path = structure_service.save_pdb_to_file(
                boltz["pdb_text"], fold.id
            )

        agg = aggregation.compute_aggregation_propensity(peptide_seq)
        profile = {
            "aggregation": agg,
            "stability": aggregation.compute_stability_score(peptide_seq),
            "bbb": aggregation.compute_bbb_penetration_score(peptide_seq),
            "half_life": aggregation.estimate_half_life(peptide_seq),
        }

        await update_agent_status(
            db,
            AGENT_NAME,
            "ACTIVE",
            current_task="Evaluating fold quality",
            fold_id=fold.id,
        )
        completion = await call_claude(
            model=settings.STRUCTURAL_MODEL,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": _build_user_message(
                        fold, boltz, chai, agreement, profile
                    ),
                }
            ],
            max_tokens=2048,
            temperature=0.2,
        )
        try:
            raw = extract_json(completion["text"])
        except ValueError as parse_err:
            log.warning(
                "alembic.structural.llm_unparseable",
                error=str(parse_err),
                fold_id=fold.id,
            )
            raw = {
                "fold_verdict": "FAILED" if _classify_failure(boltz, chai) else "DISCARDED",
                "confidence_assessment": (
                    "Structure prediction failed (no usable output from "
                    "Boltz-2/Chai-1) and the model returned no JSON."
                ),
                "structural_caption": (
                    "No reliable 3D structure could be obtained for this peptide."
                ),
                "result_summary": (
                    "Both structure predictors failed to produce usable output "
                    "for this peptide. Marking as failed."
                ),
                "key_structural_features": [],
                "agreement_with_hypothesis": "WEAK",
                "agreement_with_literature": "NO_LITERATURE",
                "binding_interpretation": "no signal",
                "predicted_binding_change_pct": None,
                "structural_caveats": [
                    "no PDB produced",
                    "boltz/chai reported errors",
                ],
            }
        if not isinstance(raw, dict):
            raise ValueError("expected JSON object from Structural")

        technical_failure = _classify_failure(boltz, chai)
        parsed = raw
        parsed["fold_verdict"] = _coerce_verdict(
            parsed.get("fold_verdict"), technical_failure=technical_failure
        )

        fold.confidence_plddt = _normalise_plddt(boltz.get("plddt"))
        fold.confidence_ptm = boltz.get("ptm")
        fold.confidence_iptm = boltz.get("iptm")
        fold.binding_probability = boltz.get("binding_probability")
        fold.binding_pic50 = boltz.get("binding_pic50")
        fold.chai_agreement = agreement
        fold.structural_caption = parsed.get("structural_caption")
        fold.fold_verdict = parsed.get("fold_verdict")
        fold.predicted_binding_change = parsed.get("predicted_binding_change_pct")
        fold.aggregation_propensity = profile["aggregation"]["overall_score"]
        fold.stability_score = profile["stability"]
        fold.bbb_penetration_score = profile["bbb"]
        fold.half_life_estimate = profile["half_life"]
        fold.plot_data = json.dumps(
            {
                "plddt_per_residue": boltz.get("plddt_per_residue"),
                "pae_matrix": boltz.get("pae_matrix"),
                "sequence_coverage": boltz.get("sequence_coverage"),
                "aggregation_window_scores": profile["aggregation"]["window_scores"],
                "binding_probability": boltz.get("binding_probability"),
                "binding_pic50": boltz.get("binding_pic50"),
            }
        )
        await db.commit()

        await log_agent_run(
            db,
            fold_id=fold.id,
            agent_name=AGENT_NAME,
            model=settings.STRUCTURAL_MODEL,
            summary=(parsed.get("result_summary") or parsed.get("structural_caption"))[:500]
            if parsed.get("result_summary") or parsed.get("structural_caption")
            else None,
            input_tokens=completion["input_tokens"],
            output_tokens=completion["output_tokens"],
            cost_usd=completion.get("cost_usd"),
            status="COMPLETED",
            started_at=started_at,
            tags=[
                f"verdict:{parsed.get('fold_verdict')}",
                f"plddt:{round(fold.confidence_plddt, 2) if fold.confidence_plddt else 'n/a'}",
                f"chai1:{chai1_decision}",
            ],
        )
    except Exception as err:  # noqa: BLE001
        error = str(err)
        log.exception("alembic.structural.failed", error=error)
        await db.rollback()
        await log_agent_run(
            db,
            fold_id=fold.id,
            agent_name=AGENT_NAME,
            model=settings.STRUCTURAL_MODEL,
            summary=None,
            status="FAILED",
            error=error,
            started_at=started_at,
        )
        raise
    finally:
        await update_agent_status(db, AGENT_NAME, "IDLE", current_task=None, fold_id=None)

    return parsed
