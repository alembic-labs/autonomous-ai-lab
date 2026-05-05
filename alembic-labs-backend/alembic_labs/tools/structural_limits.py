"""Tool-limit registry — what the structural pipeline cannot adjudicate.

Used in two places:

1. **Researcher** consults this *before* writing the JSON proposal so it
   doesn't waste a cycle hypothesising a fold the predictors can't score.
   See ``agents.researcher`` for how the prompt is shaped.

2. **Cycle orchestrator** consults this *after* the Researcher commits a
   fold but *before* Structural runs. If the proposal slips through, the
   cycle marks the fold ``DISCARDED`` with an explicit ``discard_reason``
   and skips the (expensive) Structural step entirely. See
   ``orchestrator.cycle.run_distillation_cycle``.

Both surfaces share the same source of truth so the gate logic is
consistent and easy to bump as we learn new failure modes.

Calibration (May 2026, after auditing the first 51 folds):

- Short peptides (≤4aa) consistently land at pLDDT < 0.35; below the
  resolution floor of AlphaFold-family models (Boltz-2 included). 5/5
  Epitalon (AEDG, 4aa) attempts DISCARDED.
- Lipid / membrane targets give ipTM = 0.00 because Boltz-2 cannot model
  peptide-lipid interactions (cardiolipin, phospholipids, sphingolipids).
- Putative / uncharacterized receptors have no defined binding interface
  to predict (DSIP "unknown receptor" returned ipTM = 0).
- Class B GPCRs + non-canonical chemistry (Aib substitutions, hydrocarbon
  staples, hexenoyl caps on GHRHR / GLP-1R / GIPR / GCGR) is a known
  AlphaFold-family weak spot — the model wasn't trained on these
  combinations and produces low-confidence noise.
"""

from __future__ import annotations

from dataclasses import dataclass


# Below this length, structure prediction is below the model's resolution
# floor and returns random low-confidence noise. AlphaFold/Boltz-2/Chai-1
# all share this limitation — they need at least one structurally stable
# fragment, which doesn't exist for ≤4-residue peptides.
MIN_PEPTIDE_LENGTH = 5


# Substrings (lower-cased) that flag a target Boltz-2 cannot model. These
# match against ``target_protein`` (free-text). Order doesn't matter —
# any single hit blocks the fold.
LIPID_KEYWORDS: tuple[str, ...] = (
    "cardiolipin",
    "phospholipid",
    "membrane lipid",
    "ceramide",
    "sphingolipid",
    "sphingomyelin",
    "phosphatidyl",
    "lipid bilayer",
)


PUTATIVE_KEYWORDS: tuple[str, ...] = (
    "putative",
    "uncharacterized",
    "uncharacterised",
    "unknown receptor",
    "unknown target",
    "candidate receptor",
    "tentative interactor",
    "no validated receptor",
)


# Modification chemistry markers that AlphaFold-family models systematically
# under-perform on. Lower-cased substrings matched against
# ``modification_description``.
NON_CANONICAL_INDICATORS: tuple[str, ...] = (
    "aib",
    "2-aminoisobutyric",
    "norleucine",
    "nle",
    "naphthyl",
    "staple",
    "stapled",
    "s5",
    "s8",
    "i,i+4",
    "i,i+7",
    "hexenoyl",
    "pentenoyl",
    "octenoyl",
    "alpha-methyl",
    "α-methyl",
)


# Class B (secretin family) GPCR targets that struggle in combination with
# the non-canonical chemistry above. Lower-cased substrings.
CLASS_B_GPCR_TARGETS: tuple[str, ...] = (
    "ghrhr",
    "growth hormone-releasing hormone receptor",
    "glp-1r",
    "glp-1 receptor",
    "glucagon-like peptide-1 receptor",
    "gipr",
    "glucose-dependent insulinotropic",
    "gcgr",
    "glucagon receptor",
    "secretin receptor",
    "calcitonin receptor",
    "pth1r",
    "parathyroid hormone receptor",
    "vpac",
    "crhr",
    "corticotropin-releasing hormone receptor",
)


@dataclass(frozen=True)
class PredictabilityVerdict:
    """Result of running ``assess_predictability``.

    ``block`` is the hard signal — when True, neither the Researcher nor
    the orchestrator should proceed. ``warnings`` carries soft signals
    that get surfaced in the fold's caveats / report but don't abort
    the cycle.
    """

    predictable: bool
    block: bool
    block_reason: str | None
    warnings: tuple[str, ...]


def _matches_any(haystack: str, needles: tuple[str, ...]) -> str | None:
    """Return the first needle found in ``haystack``, or None."""
    if not haystack:
        return None
    lowered = haystack.lower()
    for needle in needles:
        if needle in lowered:
            return needle
    return None


def assess_predictability(
    *,
    peptide_sequence: str | None,
    target_protein: str | None,
    modification: str | None,
    target_uniprot: str | None = None,
) -> PredictabilityVerdict:
    """Hard + soft predictability check for a proposed fold.

    Hard blocks (``block=True``):
    - peptide shorter than ``MIN_PEPTIDE_LENGTH``
    - target name matches a lipid keyword
    - target name matches a putative/uncharacterized keyword
    - missing UniProt ID (when one was expected — i.e. the canonical list
      had options); see ``target_is_predictable`` for the full check

    Soft warnings (``block=False`` but flagged):
    - non-canonical residue + class B GPCR combination
    """

    warnings: list[str] = []
    block_reason: str | None = None

    seq = (peptide_sequence or "").strip()
    if len(seq) < MIN_PEPTIDE_LENGTH:
        block_reason = (
            f"peptide is {len(seq)} aa — below the structure-prediction "
            f"resolution floor (Boltz-2/Chai-1 need ≥{MIN_PEPTIDE_LENGTH} aa)"
        )

    target_name = (target_protein or "").strip()
    if block_reason is None:
        lipid = _matches_any(target_name, LIPID_KEYWORDS)
        if lipid:
            block_reason = (
                f"target is a lipid ('{lipid}') — Boltz-2 does not model "
                "peptide-lipid interactions"
            )

    if block_reason is None:
        putative = _matches_any(target_name, PUTATIVE_KEYWORDS)
        if putative:
            block_reason = (
                f"target is putative/uncharacterized ('{putative}') — "
                "no defined binding interface to predict"
            )

    # Soft warning: non-canonical chemistry + class B GPCR is a known
    # weak spot. The fold can still be useful as a negative-result data
    # point (and the user might want to test it anyway), so we don't
    # block — just attach a caveat the Communicator must surface.
    mod_name = (modification or "").strip()
    if mod_name and target_name:
        has_non_canonical = bool(
            _matches_any(mod_name, NON_CANONICAL_INDICATORS)
        )
        is_class_b = bool(_matches_any(target_name, CLASS_B_GPCR_TARGETS))
        if has_non_canonical and is_class_b:
            warnings.append(
                "non-canonical residue / chemistry on a class B GPCR — "
                "AlphaFold-family models systematically underperform on "
                "this combination; expect lower pLDDT/ipTM"
            )

    block = block_reason is not None
    return PredictabilityVerdict(
        predictable=not block,
        block=block,
        block_reason=block_reason,
        warnings=tuple(warnings),
    )


def target_is_predictable(
    *,
    target_protein: str | None,
    target_uniprot: str | None,
) -> tuple[bool, str | None]:
    """Pre-flight check used by the orchestrator before Structural runs.

    Returns ``(is_predictable, reason_if_not)``. Distinct from
    ``assess_predictability`` because at this point we already have the
    canonical IDs (or know they're missing) and want a stricter "no
    UniProt = skip" rule.
    """

    name = (target_protein or "").strip()
    uniprot = (target_uniprot or "").strip()

    if not uniprot:
        return False, "no UniProt ID resolved — target identity unconfirmed"

    lipid = _matches_any(name, LIPID_KEYWORDS)
    if lipid:
        return False, (
            f"target is a lipid ('{lipid}') — Boltz-2 cannot model "
            "peptide-lipid interactions"
        )

    putative = _matches_any(name, PUTATIVE_KEYWORDS)
    if putative:
        return False, (
            f"target is putative/uncharacterized ('{putative}') — "
            "no defined binding interface to predict"
        )

    return True, None


# Human-readable summary block for the Researcher's system prompt.
# Bumped from this single source so the prompt and the gate stay aligned.
RESEARCHER_TOOL_LIMITS_BLOCK = """
TOOL LIMITATIONS YOU MUST RESPECT:

The structure prediction pipeline (Boltz-2 + Chai-1) has known limits.
Avoid proposing folds that fall in these categories:

  1. Peptides shorter than 5 amino acids (below resolution floor — will
     return random low-confidence noise).
  2. Targets that are lipids, putative receptors, or uncharacterized
     binding sites — no interpretable interface possible (cardiolipin,
     phospholipids, "putative receptor", "tentative interactor", etc.).
  3. Non-canonical amino acid substitutions on class B GPCRs (Aib,
     hydrocarbon staples, hexenoyl caps, α-methyl AAs on GHRHR/GLP-1R/
     GIPR/GCGR) — AlphaFold-family models systematically underperform
     here. If you want to test such a combination, prefer a class A GPCR
     target instead.

Before proposing any fold, mentally check it against these limits. If
your hypothesis falls in one, propose a DIFFERENT modification or a
DIFFERENT peptide instead. Do not waste compute on folds the tool
cannot adjudicate.
""".strip()
