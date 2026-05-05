"""Researcher agent — picks a peptide, formulates a modification hypothesis.

The Researcher's output drives every downstream agent. Two design rules:

1. **Structured target IDs are required.** Free-text target names ("GHRH
   receptor") cannot be looked up in ChEMBL reliably, leaving the Clinical
   agent with empty data. The agent picks one entry from the curated
   ``canonical_targets`` list on the seed and emits its UniProt + ChEMBL +
   gene_symbol verbatim. If a peptide has no curated targets, the agent
   must call out the gap rather than invent IDs.

2. **The Researcher has memory.** Recent folds for the same peptide (and
   their outcomes) are injected into the user message. The agent is
   instructed not to repeat hypotheses with the same outcome and to build
   on REFINED ones.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import Fold, KnownPeptide
from ..logging_setup import get_logger
from ..tools import peptide_db
from ..tools.structural_limits import (
    RESEARCHER_TOOL_LIMITS_BLOCK,
    assess_predictability,
)
from .base import (
    call_claude,
    extract_json,
    log_agent_run,
    update_agent_status,
)

log = get_logger(__name__)

AGENT_NAME = "RESEARCHER"

RESEARCH_FOCUSES: tuple[str, ...] = (
    "STABILITY",
    "AFFINITY",
    "SELECTIVITY",
    "CONFORMATION",
    "DELIVERY",
    "PHARMACOKINETICS",
)

MODIFICATION_CATEGORIES: tuple[str, ...] = (
    "Single residue substitution",
    "Terminal modification",
    "D-amino acid replacement",
    "Non-canonical amino acid",
    "Cyclization",
    "Lipidation",
    "Fragment / truncation",
    "Hybrid / chimeric",
    "Stapled peptide",
)


SYSTEM_PROMPT = """You are the RESEARCHER agent of ALEMBIC LABS, an autonomous AI laboratory researching performance peptides.

Role: Given a peptide and recent research history, formulate a SPECIFIC, TESTABLE hypothesis about a modification that could improve some property (binding affinity, stability, half-life, target selectivity, conformation, BBB / oral / intranasal delivery, pharmacokinetics).

Output valid JSON:
{
  "title": "<short, max 100 chars>",
  "peptide_name": "<exact name>",
  "peptide_sequence": "<original sequence>",
  "modification_description": "<concrete, e.g. 'Lys-7 → Arg substitution'>",
  "modified_sequence": "<modified sequence>",
  "target_protein": "<human-readable target protein name>",
  "target_uniprot_id": "<UniProt accession, e.g. 'Q02643'>",
  "target_chembl_id": "<ChEMBL target id, e.g. 'CHEMBL2049', or null if not in canonical list>",
  "target_gene_symbol": "<HGNC gene symbol, e.g. 'GHRHR'>",
  "research_focus": "<one of: STABILITY | AFFINITY | SELECTIVITY | CONFORMATION | DELIVERY | PHARMACOKINETICS>",
  "modification_category": "<one of the nine MODIFICATION CATEGORIES below, copied verbatim>",
  "hypothesis": "<2-4 sentences explaining what we're testing and why>",
  "rationale": "<2-4 sentences scientific rationale grounded in mechanism>",
  "predicted_outcome": "<what we expect to see in structure prediction>"
}

TARGET IDENTIFICATION (CRITICAL):
You MUST pick the target from the CANONICAL TARGETS list provided in the user message.
- Copy the UniProt ID, ChEMBL ID and gene symbol VERBATIM from one of the entries.
- Do NOT invent UniProt or ChEMBL IDs from memory — the Clinical agent uses these
  to fetch real bioactivity data and a wrong ID silently breaks the report.
- If the canonical list is empty, set target_uniprot_id, target_chembl_id and
  target_gene_symbol to null and pick a target_protein name that's most likely to
  be the relevant binding partner — flag the missing IDs in your rationale so the
  Clinical agent can react.

RESEARCH DIRECTIONS — every fold targets ONE primary research focus:

  1. STABILITY        — protection against enzymatic degradation (proteases, peptidases, oxidation).
  2. AFFINITY         — improving binding strength to the primary target receptor.
  3. SELECTIVITY      — reducing off-target binding to related receptors.
  4. CONFORMATION     — stabilising the bioactive conformation (cyclisation, helix locks, disulfide bridges).
  5. DELIVERY         — improving BBB penetration, oral bioavailability, or intranasal absorption.
  6. PHARMACOKINETICS — extending plasma or CNS half-life via novel mechanisms beyond simple proteolysis blocks.

MODIFICATION CATEGORIES — every fold also picks ONE category. Copy the
phrase EXACTLY (case-sensitive) into ``modification_category``:

  1. Single residue substitution
  2. Terminal modification
  3. D-amino acid replacement
  4. Non-canonical amino acid
  5. Cyclization
  6. Lipidation
  7. Fragment / truncation
  8. Hybrid / chimeric
  9. Stapled peptide

ROTATION RULE (HARD CONSTRAINT):
The user message includes a LAB-WIDE RECENT HISTORY block listing the last
folds across ALL peptides with their (focus, category) tags. Your hypothesis
MUST satisfy AT LEAST ONE of:

  - the chosen ``modification_category`` did NOT appear in the last 3 folds; OR
  - the chosen ``research_focus`` did NOT appear in the last 3 folds.

If both the focus and the category are repeats of any of the last three folds,
pick a different one. Do NOT propose three Terminal modifications in a row.
Do NOT propose three D-amino acid replacements in a row. Do NOT focus on
STABILITY three times in a row. Diversity across folds is part of the lab's
output value — repetitive findings have no scientific signal.

Briefly justify in your ``rationale`` how your choice diverges from the last
3 folds in the lab-wide history (one sentence is enough).

PEPTIDE-LEVEL HISTORY (still applies):
The user message also includes recent folds for THIS peptide (and similar
ones). On top of the rotation rule above:
- DO NOT propose a modification that's already been tested with the same outcome.
- If a strategy was REFINED for this peptide, propose a related-but-different variant.
- If a strategy was DISCARDED with a structural failure, do not repeat the exact
  same change — note it as a learned constraint and try a different position or
  chemistry.
- Build on the lab's collective findings — every fold should add a new data point.

RULES:
- Modification must be biologically plausible.
- Ground the hypothesis in known mechanism.
- Be specific (concrete amino acid changes, exact positions).
- Stay honest — in silico hypothesis generation, not drug discovery.
- Choose modifications relevant to performance biohacking (longevity, regeneration,
  cognition, metabolism, performance). We do NOT research disease pathogenic mutations.

""" + RESEARCHER_TOOL_LIMITS_BLOCK + """

PEPTIDE AVOID LIST (HARD CONSTRAINT):
The user message includes a "PEPTIDES TO AVOID THIS CYCLE" block listing
peptides where the lab has accumulated 3+ consecutive DISCARDED folds with
no REFINED. These are almost certainly tool-limit failures (sub-resolution
length, lipid target, AlphaFold-blind chemistry). Pick a different peptide
this cycle — do not propose ANY hypothesis for a peptide on the AVOID list.
"""


async def _recent_fold_peptide_ids(db: AsyncSession, limit: int = 5) -> list[int]:
    """Return KnownPeptide ids used in the most recent N folds."""
    stmt = (
        select(Fold.peptide_name)
        .order_by(Fold.created_at.desc())
        .limit(limit)
    )
    recent_names = [n for n in (await db.execute(stmt)).scalars().all() if n]
    if not recent_names:
        return []
    stmt2 = select(KnownPeptide.id).where(KnownPeptide.name.in_(recent_names))
    return list((await db.execute(stmt2)).scalars().all())


async def _lab_wide_history(
    db: AsyncSession,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Pull the lab's last N folds across ALL peptides for cross-fold rotation.

    Researcher reads this to honor the rotation rule (don't repeat the same
    research_focus / modification_category three folds in a row). Filters out
    PENDING / FAILED so we only count folds that actually contributed signal.
    """
    rows = (
        await db.execute(
            select(Fold)
            .where(Fold.status.in_(["REFINED", "PROMISING", "DISCARDED"]))
            .order_by(Fold.id.desc())
            .limit(limit)
        )
    ).scalars().all()

    return [
        {
            "id": r.id,
            "peptide": r.peptide_name or "—",
            "modification": r.modification_description or "—",
            "verdict": r.fold_verdict or r.status,
        }
        for r in rows
    ]


async def _blocked_peptides(
    db: AsyncSession, *, lookback: int = 15, threshold: int = 3
) -> dict[str, dict[str, int]]:
    """Identify peptides systematically failing the predictors.

    Walks the last ``lookback`` publishable folds and returns
    ``{peptide_name: {"DISCARDED": n, "REFINED": m, "PROMISING": k}}`` for
    every peptide that has ``threshold+`` DISCARDED outcomes and zero
    REFINED ones in that window. These are almost always tool-limit
    failures (Epitalon AEDG hitting the resolution floor 5/5 times,
    Sermorelin × GHRHR with non-canonical residues, etc.) and should be
    filtered out of peptide selection rather than retried again.
    """
    rows = (
        await db.execute(
            select(Fold)
            .where(Fold.status.in_(["REFINED", "PROMISING", "DISCARDED"]))
            .where(Fold.peptide_name.is_not(None))
            .order_by(Fold.id.desc())
            .limit(lookback)
        )
    ).scalars().all()

    tally: dict[str, dict[str, int]] = {}
    for r in rows:
        name = r.peptide_name or ""
        if not name:
            continue
        bucket = tally.setdefault(
            name, {"REFINED": 0, "PROMISING": 0, "DISCARDED": 0}
        )
        verdict = (r.fold_verdict or r.status or "").upper()
        if verdict in bucket:
            bucket[verdict] += 1

    return {
        name: counts
        for name, counts in tally.items()
        if counts["DISCARDED"] >= threshold and counts["REFINED"] == 0
    }


def _format_blocked_peptides(blocked: dict[str, dict[str, int]]) -> str:
    """Render the AVOID block exposed to the Researcher."""
    if not blocked:
        return "(none — every peptide in recent history has at least one non-discarded outcome)"
    lines = []
    for name, counts in blocked.items():
        lines.append(
            f"  {name} — {counts['DISCARDED']} consecutive DISCARDED, "
            f"no REFINED. Likely a tool-limit failure (sub-resolution "
            f"peptide length, lipid/uncharacterized target, or AlphaFold-"
            f"blind chemistry). Pick a different peptide this cycle."
        )
    return "\n".join(lines)


def _format_lab_wide_history(rows: list[dict[str, Any]]) -> str:
    """Render the lab-wide history block exposed to Researcher."""
    if not rows:
        return (
            "No lab-wide history yet — this is one of the first folds. "
            "Pick any focus / category combination."
        )
    lines = [
        f"  Fold #{r['id']} — {r['peptide']} — {r['modification']} → {r['verdict']}"
        for r in rows
    ]
    return "\n".join(lines)


async def _research_history(
    db: AsyncSession,
    peptide_name: str,
    *,
    same_peptide_limit: int = 6,
    same_class_limit: int = 4,
    peptide_class: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Pull recent fold history relevant to the peptide for the Researcher's memory.

    Returns ``{"same_peptide": [...], "same_class": [...]}`` — each row is a
    compact dict with ``id, peptide, modification, hypothesis, status, plddt``.
    """
    same_peptide_rows = (
        await db.execute(
            select(Fold)
            .where(Fold.peptide_name == peptide_name)
            .order_by(Fold.created_at.desc())
            .limit(same_peptide_limit)
        )
    ).scalars().all()

    same_class_rows: list[Fold] = []
    if peptide_class:
        same_class_rows = (
            await db.execute(
                select(Fold)
                .where(Fold.peptide_class == peptide_class)
                .where(Fold.peptide_name != peptide_name)
                .order_by(Fold.created_at.desc())
                .limit(same_class_limit)
            )
        ).scalars().all()

    def _shape(rows: list[Fold]) -> list[dict[str, Any]]:
        return [
            {
                "id": r.id,
                "peptide": r.peptide_name,
                "modification": r.modification_description or "",
                "hypothesis": (r.hypothesis or "")[:280],
                "status": r.status,
                "verdict": r.fold_verdict,
                "plddt": round(r.confidence_plddt, 2) if r.confidence_plddt else None,
            }
            for r in rows
        ]

    return {
        "same_peptide": _shape(same_peptide_rows),
        "same_class": _shape(same_class_rows),
    }


def _format_history_block(history: dict[str, list[dict[str, Any]]]) -> str:
    """Render the research history into a readable text block."""

    def _row(row: dict[str, Any]) -> str:
        plddt = f", pLDDT {row['plddt']}" if row.get("plddt") is not None else ""
        verdict = row.get("verdict") or row.get("status") or "PENDING"
        mod = row.get("modification") or "—"
        hypo = row.get("hypothesis") or ""
        snippet = f" Hypothesis: {hypo}" if hypo else ""
        return (
            f"  Fold #{row['id']} — {row['peptide']} — {mod} → {verdict}{plddt}.{snippet}"
        )

    same = history.get("same_peptide") or []
    other = history.get("same_class") or []
    parts: list[str] = []
    if same:
        parts.append("Same peptide (most recent first):")
        parts.extend(_row(r) for r in same)
    else:
        parts.append("Same peptide: no prior folds — this is the first hypothesis.")
    if other:
        parts.append("\nSame peptide class (for cross-reference):")
        parts.extend(_row(r) for r in other)
    return "\n".join(parts)


def _format_canonical_targets(peptide: KnownPeptide) -> tuple[str, list[dict[str, Any]]]:
    """Render the curated canonical_targets as a numbered block.

    Returns (text, structured_list). The list is what we attach to the agent
    log so the orchestrator can verify the agent picked from it.
    """
    try:
        raw = json.loads(peptide.canonical_targets) if peptide.canonical_targets else []
    except json.JSONDecodeError:
        raw = []
    if not raw:
        return (
            "(no curated targets — output null IDs and explain in rationale)",
            [],
        )
    lines: list[str] = []
    for i, t in enumerate(raw, start=1):
        cid = t.get("chembl_id") or "—"
        lines.append(
            f"  {i}. {t.get('name', '?')} | UniProt {t.get('uniprot_id', '?')} | "
            f"ChEMBL {cid} | gene {t.get('gene_symbol', '?')} | "
            f"role: {t.get('mechanism_role', '—')}"
        )
    return ("\n".join(lines), raw)


def _build_user_message(
    peptide: KnownPeptide,
    history_block: str,
    canonical_block: str,
    lab_wide_block: str,
    avoid_block: str,
) -> str:
    """Render KnownPeptide + history + canonical targets into a prompt."""
    try:
        targets = json.loads(peptide.known_targets) if peptide.known_targets else []
    except json.JSONDecodeError:
        targets = []

    return (
        f"Peptide: {peptide.name}\n"
        f"Aliases: {peptide.aliases or '—'}\n"
        f"Sequence: {peptide.sequence}\n"
        f"Length: {peptide.length}\n"
        f"Class: {peptide.peptide_class}\n"
        f"Known targets (free-text): {', '.join(targets) if targets else '—'}\n"
        f"Mechanism: {peptide.mechanism_brief}\n"
        f"Biohacker use: {peptide.biohacker_use}\n\n"
        "CANONICAL TARGETS — pick exactly one and copy its IDs verbatim:\n"
        f"{canonical_block}\n\n"
        "PEPTIDES TO AVOID THIS CYCLE (3+ consecutive DISCARDED, no REFINED):\n"
        f"{avoid_block}\n\n"
        "LAB-WIDE RECENT HISTORY (last folds across ALL peptides — for the "
        "rotation rule):\n"
        f"{lab_wide_block}\n\n"
        "PEPTIDE-LEVEL RESEARCH HISTORY (for THIS peptide and its class):\n"
        f"{history_block}\n\n"
        "Propose ONE biologically plausible modification with rationale. Vary "
        "BOTH research_focus AND modification_category vs. the last 3 folds — "
        "do not repeat the same focus or category three folds in a row. Output "
        "the JSON object specified in your system prompt — no preamble, no markdown."
    )


async def run_researcher(db: AsyncSession, fold: Fold) -> dict[str, Any]:
    """Populate the Researcher fields on ``fold`` and return the parsed JSON."""

    started_at = datetime.now(timezone.utc)
    # Cache the int id eagerly so we never lazy-load through a possibly-
    # expired session after rollback() / errors.
    fold_id_cached = fold.id
    await update_agent_status(
        db,
        AGENT_NAME,
        "ACTIVE",
        current_task="Selecting peptide and formulating hypothesis",
        fold_id=fold_id_cached,
    )

    error: str | None = None
    parsed: dict[str, Any] = {}
    try:
        recent_ids = await _recent_fold_peptide_ids(db)
        blocked = await _blocked_peptides(db)
        peptide = await peptide_db.get_random_peptide(
            db,
            exclude_recent_ids=recent_ids,
            blocked_names=list(blocked.keys()),
        )
        if peptide is None:
            raise RuntimeError("no KnownPeptide rows in DB — seed not run?")

        history = await _research_history(
            db,
            peptide.name,
            peptide_class=peptide.peptide_class,
        )
        history_block = _format_history_block(history)
        canonical_block, canonical_list = _format_canonical_targets(peptide)
        lab_wide_rows = await _lab_wide_history(db, limit=10)
        lab_wide_block = _format_lab_wide_history(lab_wide_rows)
        avoid_block = _format_blocked_peptides(blocked)

        user_msg = _build_user_message(
            peptide,
            history_block,
            canonical_block,
            lab_wide_block,
            avoid_block,
        )

        # Up to 3 attempts:
        #   - JSON parse failure → retry at lower temp with explicit reminder
        #   - assess_predictability blocks → retry with a tool-limit reminder
        # Both share the same loop so the temperature and ``user_msg``
        # mutations compose correctly. Capped at 3 to bound worst-case cost
        # to ~$0.30 (Opus); after that we accept the proposal even if it
        # tripped the gate so the cycle's downstream gate can still mark
        # the fold DISCARDED with a clean discard_reason.
        last_err: Exception | None = None
        completion: dict[str, Any] | None = None
        raw: dict[str, Any] | list[Any] | None = None
        gate_warnings: tuple[str, ...] = ()
        for attempt in (1, 2, 3):
            try:
                completion = await call_claude(
                    model=settings.RESEARCHER_MODEL,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_msg}],
                    max_tokens=2048,
                    temperature=0.5 if attempt == 1 else 0.2,
                )
                raw = extract_json(completion["text"])
            except ValueError as parse_err:
                last_err = parse_err
                log.warning(
                    "alembic.researcher.json_parse_retry",
                    fold_id=fold_id_cached,
                    attempt=attempt,
                    error=str(parse_err),
                )
                user_msg = (
                    user_msg
                    + "\n\nReturn ONLY a single valid JSON object with no "
                    "trailing commentary or markdown fences."
                )
                continue

            if not isinstance(raw, dict):
                last_err = ValueError("expected JSON object from Researcher")
                continue

            # Pre-flight predictability check on the freshly proposed fold.
            # Hard blocks → regenerate. Soft warnings → keep them and let
            # them flow into the AgentRun.tags + Communicator caveats.
            verdict = assess_predictability(
                peptide_sequence=raw.get("modified_sequence")
                or raw.get("peptide_sequence")
                or peptide.sequence,
                target_protein=raw.get("target_protein"),
                modification=raw.get("modification_description"),
                target_uniprot=raw.get("target_uniprot_id"),
            )
            gate_warnings = verdict.warnings
            if verdict.block and attempt < 3:
                log.warning(
                    "alembic.researcher.predictability_retry",
                    fold_id=fold_id_cached,
                    attempt=attempt,
                    reason=verdict.block_reason,
                )
                user_msg = (
                    user_msg
                    + "\n\n⚠️  PREVIOUS PROPOSAL REJECTED — tool-limit gate:\n"
                    f"  {verdict.block_reason}\n"
                    "Pick a different peptide / target / modification that "
                    "the structure prediction pipeline can adjudicate."
                )
                continue

            # Either passed, or 3rd attempt — accept and let downstream gate
            # produce a clean DISCARDED with discard_reason if it still
            # tripped the limits.
            break

        if raw is None or completion is None or not isinstance(raw, dict):
            raise last_err or ValueError("researcher: no JSON after retries")
        parsed = raw

        # If the agent chose a target and the canonical list is non-empty, we
        # cross-check the IDs match one of the curated entries. This catches
        # silent ID drift (Claude hallucinating accession numbers).
        chosen_uniprot = (parsed.get("target_uniprot_id") or "").strip() or None
        chosen_chembl = (parsed.get("target_chembl_id") or "").strip() or None
        if canonical_list and chosen_uniprot:
            valid = any(
                t.get("uniprot_id") == chosen_uniprot for t in canonical_list
            )
            if not valid:
                log.warning(
                    "alembic.researcher.uniprot_off_canonical_list",
                    fold_id=fold.id,
                    chose=chosen_uniprot,
                    expected=[t.get("uniprot_id") for t in canonical_list],
                )

        # Defensive caps — values must fit ``String(N)`` columns on Fold.
        # Without these, a verbose Researcher response (long ``target_protein``
        # like the DSIP "no validated receptor; tentative interactor: ..."
        # phrasing) raises StringDataRightTruncationError mid-cycle.
        def _clip(value: Any, limit: int) -> str | None:
            if value is None:
                return None
            s = str(value).strip()
            if not s:
                return None
            return s[:limit]

        fold.title = (parsed.get("title") or f"{peptide.name} hypothesis")[:200]
        fold.peptide_name = (
            _clip(parsed.get("peptide_name"), 100) or peptide.name[:100]
        )
        fold.peptide_sequence = (
            parsed.get("peptide_sequence") or peptide.sequence
        )
        fold.peptide_class = peptide.peptide_class[:50]
        fold.modification_description = parsed.get("modification_description") or ""
        fold.modified_sequence = parsed.get("modified_sequence")
        fold.target_protein = _clip(parsed.get("target_protein"), 100)
        fold.target_uniprot_id = (
            chosen_uniprot[:20] if chosen_uniprot else None
        )
        fold.target_chembl_id = (
            chosen_chembl[:20] if chosen_chembl else None
        )
        fold.target_gene_symbol = _clip(parsed.get("target_gene_symbol"), 40)
        fold.hypothesis = parsed.get("hypothesis") or ""
        fold.rationale = parsed.get("rationale")
        fold.predicted_outcome = parsed.get("predicted_outcome")
        await db.commit()

        # Validate the new rotation enums; warn but never fail the cycle on
        # an off-list value. We persist the validated picks on the AgentRun's
        # tags column so we can build per-focus / per-category analytics
        # without a schema migration.
        focus_raw = (parsed.get("research_focus") or "").strip().upper() or None
        if focus_raw and focus_raw not in RESEARCH_FOCUSES:
            log.warning(
                "alembic.researcher.focus_off_enum",
                fold_id=fold_id_cached,
                got=focus_raw,
                expected=list(RESEARCH_FOCUSES),
            )
            focus_raw = None
        category_raw = (parsed.get("modification_category") or "").strip() or None
        if category_raw and category_raw not in MODIFICATION_CATEGORIES:
            log.warning(
                "alembic.researcher.category_off_enum",
                fold_id=fold_id_cached,
                got=category_raw,
                expected=list(MODIFICATION_CATEGORIES),
            )
            category_raw = None

        # Tag the agent run so we can analyse memory effectiveness later.
        tags: list[str] = []
        if history["same_peptide"]:
            tags.append(f"history:{len(history['same_peptide'])}")
        if canonical_list:
            tags.append("canonical_target")
        if focus_raw:
            tags.append(f"focus:{focus_raw}")
        if category_raw:
            tags.append(f"category:{category_raw}")
        if gate_warnings:
            tags.append(f"gate_warnings:{len(gate_warnings)}")
        if blocked:
            tags.append(f"avoid_peptides:{len(blocked)}")
        log.info(
            "alembic.researcher.rotation",
            fold_id=fold_id_cached,
            focus=focus_raw,
            category=category_raw,
            recent_count=len(lab_wide_rows),
            blocked_peptides=list(blocked.keys()),
            gate_warnings=list(gate_warnings),
        )
        await log_agent_run(
            db,
            fold_id=fold.id,
            agent_name=AGENT_NAME,
            model=settings.RESEARCHER_MODEL,
            summary=fold.modification_description or fold.title,
            input_tokens=completion["input_tokens"],
            output_tokens=completion["output_tokens"],
            cost_usd=completion.get("cost_usd"),
            status="COMPLETED",
            started_at=started_at,
            tags=tags,
        )
    except Exception as err:  # noqa: BLE001 — recorded on AgentRun
        error = str(err)
        log.exception("alembic.researcher.failed", error=error)
        await db.rollback()
        await log_agent_run(
            db,
            fold_id=fold_id_cached,
            agent_name=AGENT_NAME,
            model=settings.RESEARCHER_MODEL,
            summary=None,
            status="FAILED",
            error=error,
            started_at=started_at,
        )
        raise
    finally:
        await update_agent_status(db, AGENT_NAME, "IDLE", current_task=None, fold_id=None)

    return parsed
