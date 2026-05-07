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
from collections import defaultdict
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

PAIR-LEVEL AVOID LIST (HARD CONSTRAINT):
A peptide can bind multiple targets — and Boltz-2's resolvability is a
property of the (peptide, target) PAIR, not the peptide alone. The user
message includes a "BLOCKED PAIRS" block listing exact peptide × target
pairs that have produced 2+ DISCARDED outcomes with no REFINED across
the lab's full history.

Hard rule: do NOT propose a hypothesis whose ``(peptide_name,
target_protein)`` pair appears in the blocked list. The peptide on its
own may still be valid — pick a DIFFERENT canonical target for it.
Example: if (MOTS-c, AMPK alpha-2) is blocked, you may still propose
(MOTS-c, LARS1) because LARS1 is a separate binding partner with
distinct structural prospects.
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


def _normalize_target_key(target: str | None) -> str:
    """Lowercase + drop parenthetical qualifiers — pair matching needs to be
    insensitive to case and to descriptors like "(AMPK α2)" vs "AMPK alpha-2"."""
    if not target:
        return ""
    return target.split("(")[0].strip().lower()


def _normalize_peptide_key(name: str | None) -> str:
    if not name:
        return ""
    return name.strip().lower()


async def _blocked_pairs(
    db: AsyncSession, *, threshold: int = 2
) -> dict[tuple[str, str], dict[str, int]]:
    """Identify (peptide, target) pairs that fail repeatedly in lab history.

    Looks across the **entire** lab history (not just a recent window).
    Once a pair has accumulated ``threshold+`` DISCARDED outcomes and zero
    REFINED ones, it's effectively un-resolvable by the current toolchain
    (Boltz-2 has no co-crystal template, target is a class-B GPCR with
    non-canonical chemistry on the peptide, etc.) and should not be
    retried. Pair-level granularity preserves access to the same peptide
    against *different* targets — e.g. (MOTS-c, AMPK alpha-2) is blocked
    after 6 DISCARDED, but (MOTS-c, LARS1) — a different binding partner
    with published evidence — stays available.

    Returns a dict keyed by ``(peptide_lower, target_normalized_lower)``
    so callers can match candidate proposals consistently.
    """
    rows = (
        await db.execute(
            select(Fold)
            .where(Fold.fold_verdict.in_(["REFINED", "PROMISING", "DISCARDED"]))
            .where(Fold.peptide_name.is_not(None))
            .where(Fold.target_protein.is_not(None))
        )
    ).scalars().all()

    tally: dict[tuple[str, str], dict[str, int]] = {}
    for r in rows:
        pep = _normalize_peptide_key(r.peptide_name)
        tgt = _normalize_target_key(r.target_protein)
        if not pep or not tgt:
            continue
        bucket = tally.setdefault(
            (pep, tgt), {"REFINED": 0, "PROMISING": 0, "DISCARDED": 0}
        )
        verdict = (r.fold_verdict or "").upper()
        if verdict in bucket:
            bucket[verdict] += 1

    return {
        pair: counts
        for pair, counts in tally.items()
        if counts["DISCARDED"] >= threshold and counts["REFINED"] == 0
    }


def _is_pair_blocked(
    peptide_name: str | None,
    target_protein: str | None,
    blocked: dict[tuple[str, str], dict[str, int]],
) -> bool:
    """Check whether a candidate proposal lands on a blocked pair."""
    p = _normalize_peptide_key(peptide_name)
    t = _normalize_target_key(target_protein)
    if not p or not t:
        return False
    return (p, t) in blocked


def _peptide_canonical_unblocked_count(
    peptide: KnownPeptide,
    blocked_pairs: dict[tuple[str, str], dict[str, int]],
) -> int:
    """Count canonical targets for ``peptide`` that aren't pair-blocked.

    Used by the orchestrator to decide whether to re-roll the peptide
    when *every* curated target is blocked (i.e. the peptide is
    effectively dead even if the peptide-level threshold wasn't hit).
    """
    try:
        raw = json.loads(peptide.canonical_targets) if peptide.canonical_targets else []
    except json.JSONDecodeError:
        return 0
    if not raw:
        # No curated targets — the agent will free-text propose, so we
        # can't pre-check anything here. Treat as "1" (let it run).
        return 1
    pep_key = _normalize_peptide_key(peptide.name)
    unblocked = 0
    for t in raw:
        tname = (t or {}).get("name") or ""
        if (pep_key, _normalize_target_key(tname)) not in blocked_pairs:
            unblocked += 1
    return unblocked


def _format_blocked_pairs(
    blocked: dict[tuple[str, str], dict[str, int]], *, limit: int = 10
) -> str:
    """Render the blocked-pair list for the Researcher's user prompt.

    Only show the top ``limit`` pairs (sorted by DISCARDED count desc)
    so the prompt doesn't bloat as the lab ages. The agent only needs
    enough examples to internalize the rule.
    """
    if not blocked:
        return (
            "(none yet — every peptide × target pair has produced at most "
            "one DISCARDED outcome, or has at least one non-discarded run)"
        )
    items = sorted(
        blocked.items(),
        key=lambda kv: (-kv[1]["DISCARDED"], kv[0][0], kv[0][1]),
    )[:limit]
    lines = []
    for (pep, tgt), counts in items:
        lines.append(
            f"  ({pep}, {tgt}) — {counts['DISCARDED']} DISCARDED, "
            f"0 REFINED. Likely no co-crystal template / tool-limit "
            f"on this exact pair. Pick a different target for this "
            f"peptide if proposed."
        )
    return "\n".join(lines)


async def _diversity_summary(db: AsyncSession, *, window: int = 30) -> str:
    """Surface dominant peptide × target pairs in the recent fold window.

    The pair-AVOID block already hard-blocks pairs that *failed* repeatedly,
    but the Researcher can still over-exploit *winning* pairs (Semax × MC4R,
    Ipamorelin × GHSR-1a, TB-500 × β-actin in the May 2026 audit) and let
    diversity collapse — quality up, variety down. This helper flags any
    pair occupying ≥15% of the last ``window`` publishable folds so the
    Researcher's user prompt can ask for a different pair on the next pick.

    Returns an empty string when no pair is dominant — keeps the prompt
    quiet during healthy diversity instead of injecting noise on every
    cycle.
    """
    rows = (
        await db.execute(
            select(Fold)
            .where(Fold.fold_verdict.in_(["REFINED", "PROMISING", "DISCARDED"]))
            .order_by(Fold.id.desc())
            .limit(window)
        )
    ).scalars().all()
    if not rows:
        return ""

    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    for f in rows:
        pep = (f.peptide_name or "").strip()
        tgt = _normalize_target_key(f.target_protein) if f.target_protein else ""
        if pep and tgt:
            pair_counts[(pep, tgt)] += 1

    if not pair_counts:
        return ""

    total = sum(pair_counts.values())
    top_pairs = sorted(pair_counts.items(), key=lambda x: -x[1])[:3]
    dominant = [(pair, n) for pair, n in top_pairs if n / total >= 0.15]
    if not dominant:
        return ""

    lines = [f"DIVERSITY CONTEXT (last {total} publishable folds):"]
    for (pep, tgt), n in dominant:
        pct = n / total * 100
        lines.append(f"  - {pep} × {tgt}: {n} folds ({pct:.0f}%)")
    lines.append("")
    lines.append("Bias your next proposal toward, in priority order:")
    lines.append(
        "  1. A NEW peptide × target pair not in the dominant list above "
        "(strongly preferred — most lab signal comes from breadth)."
    )
    lines.append(
        "  2. A different modification CLASS on an existing winner "
        "(e.g. cyclization instead of D-amino swap on the same pair)."
    )
    lines.append(
        "  3. AVOID: another minor variant of the same modification class "
        "on a pair that's already dominant."
    )
    return "\n".join(lines)


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


def _format_canonical_targets(
    peptide: KnownPeptide,
    *,
    blocked_pairs: dict[tuple[str, str], dict[str, int]] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Render the curated canonical_targets as a numbered block.

    Returns (text, structured_list). The structured_list contains ONLY
    unblocked targets so post-LLM validation can confirm the agent picked
    from this filtered pool. Blocked entries are still RENDERED in the
    text (with a ⚠️ AVOID marker) so the agent understands the policy
    rather than seeing a mysterious gap.
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

    pep_key = _normalize_peptide_key(peptide.name)
    blocked_pairs = blocked_pairs or {}

    lines: list[str] = []
    unblocked_list: list[dict[str, Any]] = []
    for i, t in enumerate(raw, start=1):
        cid = t.get("chembl_id") or "—"
        tname = t.get("name", "?")
        is_blocked = (pep_key, _normalize_target_key(tname)) in blocked_pairs
        marker = "  ⚠️  AVOID — pair has 2+ DISCARDED, 0 REFINED" if is_blocked else ""
        lines.append(
            f"  {i}. {tname} | UniProt {t.get('uniprot_id', '?')} | "
            f"ChEMBL {cid} | gene {t.get('gene_symbol', '?')} | "
            f"role: {t.get('mechanism_role', '—')}{marker}"
        )
        if not is_blocked:
            unblocked_list.append(t)
    return ("\n".join(lines), unblocked_list)


def _build_user_message(
    peptide: KnownPeptide,
    history_block: str,
    canonical_block: str,
    lab_wide_block: str,
    avoid_block: str,
    blocked_pairs_block: str,
    diversity_block: str,
) -> str:
    """Render KnownPeptide + history + canonical targets into a prompt."""
    try:
        targets = json.loads(peptide.known_targets) if peptide.known_targets else []
    except json.JSONDecodeError:
        targets = []

    # Diversity is opt-in: ``_diversity_summary`` returns "" when no pair
    # is dominant, in which case we drop the section entirely instead of
    # rendering an empty header. Keeps the prompt tight during healthy
    # diversity and only adds friction when the lab is actually skewing.
    diversity_section = (
        f"{diversity_block}\n\n" if diversity_block.strip() else ""
    )

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
        "BLOCKED (PEPTIDE × TARGET) PAIRS — full lab history, 2+ DISCARDED, "
        "0 REFINED. Do NOT propose any of these pairs even if both the "
        "peptide and the target individually look reasonable:\n"
        f"{blocked_pairs_block}\n\n"
        f"{diversity_section}"
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
        blocked_pairs = await _blocked_pairs(db)

        # Re-roll peptide selection if every canonical target for the chosen
        # peptide is pair-blocked (effectively dead). Cap at 5 attempts so we
        # don't spin forever in a degenerate seed state — after that, accept
        # the last peptide and let the LLM either pick a non-canonical
        # target or fall through to the predictability gate downstream.
        peptide: KnownPeptide | None = None
        skip_names: list[str] = list(blocked.keys())
        for attempt in range(5):
            cand = await peptide_db.get_random_peptide(
                db,
                exclude_recent_ids=recent_ids,
                blocked_names=skip_names,
            )
            if cand is None:
                break
            unblocked = _peptide_canonical_unblocked_count(cand, blocked_pairs)
            if unblocked > 0:
                peptide = cand
                if attempt > 0:
                    log.info(
                        "alembic.researcher.peptide_reroll",
                        fold_id=fold_id_cached,
                        attempts=attempt + 1,
                        chose=cand.name,
                    )
                break
            log.info(
                "alembic.researcher.peptide_all_targets_blocked",
                fold_id=fold_id_cached,
                peptide=cand.name,
                attempt=attempt,
            )
            skip_names = skip_names + [cand.name]
        if peptide is None:
            # Final fallback: take whatever peptide is available even if all
            # targets are blocked. The downstream gate will catch it.
            peptide = await peptide_db.get_random_peptide(
                db, exclude_recent_ids=recent_ids
            )
        if peptide is None:
            raise RuntimeError("no KnownPeptide rows in DB — seed not run?")

        history = await _research_history(
            db,
            peptide.name,
            peptide_class=peptide.peptide_class,
        )
        history_block = _format_history_block(history)
        canonical_block, canonical_list = _format_canonical_targets(
            peptide, blocked_pairs=blocked_pairs
        )
        lab_wide_rows = await _lab_wide_history(db, limit=10)
        lab_wide_block = _format_lab_wide_history(lab_wide_rows)
        avoid_block = _format_blocked_peptides(blocked)
        blocked_pairs_block = _format_blocked_pairs(blocked_pairs)
        diversity_block = await _diversity_summary(db, window=30)

        user_msg = _build_user_message(
            peptide,
            history_block,
            canonical_block,
            lab_wide_block,
            avoid_block,
            blocked_pairs_block,
            diversity_block,
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

            # Pair-level AVOID gate — checked BEFORE predictability so a
            # historically-failing pair gets a regen with the right
            # diagnostic, not a generic tool-limit one.
            proposed_pep = raw.get("peptide_name") or peptide.name
            proposed_tgt = raw.get("target_protein") or ""
            if (
                _is_pair_blocked(proposed_pep, proposed_tgt, blocked_pairs)
                and attempt < 3
            ):
                pair_count = blocked_pairs.get(
                    (
                        _normalize_peptide_key(proposed_pep),
                        _normalize_target_key(proposed_tgt),
                    ),
                    {"DISCARDED": 0},
                )
                log.warning(
                    "alembic.researcher.pair_block_retry",
                    fold_id=fold_id_cached,
                    attempt=attempt,
                    peptide=proposed_pep,
                    target=proposed_tgt,
                    discarded_count=pair_count.get("DISCARDED", 0),
                )
                user_msg = (
                    user_msg
                    + "\n\n⚠️  PREVIOUS PROPOSAL REJECTED — pair-level AVOID:\n"
                    f"  ({proposed_pep}, {proposed_tgt}) has "
                    f"{pair_count.get('DISCARDED', 0)} prior DISCARDED "
                    "with 0 REFINED. Pick a DIFFERENT canonical target for "
                    "this peptide. The peptide on its own is not blocked — "
                    "only this exact pair."
                )
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
        if blocked_pairs:
            tags.append(f"avoid_pairs:{len(blocked_pairs)}")
        if diversity_block:
            tags.append("diversity_nudge")
        log.info(
            "alembic.researcher.rotation",
            fold_id=fold_id_cached,
            focus=focus_raw,
            category=category_raw,
            recent_count=len(lab_wide_rows),
            blocked_peptides=list(blocked.keys()),
            blocked_pairs_count=len(blocked_pairs),
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
