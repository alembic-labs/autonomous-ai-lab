"""Lightweight peptide property heuristics.

These are simplified scoring functions used by the Structural agent to
populate the Peptide Profile section of the report (aggregation propensity,
stability, BBB penetration, half-life). Real predictions need wet-lab work
or specialised tools (TANGO, AGGRESCAN, ADMET-Lab, etc.) — these heuristics
just produce honest, ranked numbers good enough to compare variants.

Intentionally pure-Python with no scientific dependencies so they run on
any deployment, even when BioPython is unavailable.
"""

from __future__ import annotations

from typing import Any

# Kyte-Doolittle hydrophobicity scale.
KYTE_DOOLITTLE: dict[str, float] = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5,
    "Q": -3.5, "E": -3.5, "G": -0.4, "H": -3.2, "I": 4.5,
    "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8, "P": -1.6,
    "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2,
}

# Side-chain pK values (rough, used only for net charge at physiological pH 7.4).
PK_POSITIVE: dict[str, float] = {"K": 10.5, "R": 12.5, "H": 6.0}
PK_NEGATIVE: dict[str, float] = {"D": 3.65, "E": 4.25, "C": 8.3, "Y": 10.07}

PHYSIOLOGICAL_PH = 7.4


def _clean_sequence(sequence: str) -> str:
    """Strip whitespace and keep canonical AA letters only.

    Modified peptides may contain non-standard codes (e.g. ``Aib``, ``DBNal``).
    For the heuristics we just drop those — the caller knows the score is a
    proxy and wet-lab data is the ground truth.
    """

    cleaned = "".join(c for c in sequence.upper() if c in KYTE_DOOLITTLE)
    return cleaned


def compute_aggregation_propensity(sequence: str) -> dict[str, Any]:
    """Sliding-window hydrophobicity scan.

    Returns:
        {
          "overall_score": float in [0, 1] (higher = more aggregation-prone),
          "hotspots": [{"start", "end", "score"}],
          "window_scores": [float, ...]  // for plotting
        }

    Methodology
    -----------
    - 7-residue Kyte-Doolittle window (canonical for amyloid hotspot scans).
    - Window mean > 1.0 marks a hotspot.
    - Overall score = mean of positive windows / 4.5 (max KD), clipped to [0, 1].
    """

    seq = _clean_sequence(sequence)
    window = 7
    if len(seq) < window:
        return {"overall_score": 0.0, "hotspots": [], "window_scores": []}

    window_scores: list[float] = []
    for i in range(len(seq) - window + 1):
        chunk = seq[i : i + window]
        score = sum(KYTE_DOOLITTLE[c] for c in chunk) / window
        window_scores.append(round(score, 3))

    hotspots: list[dict[str, Any]] = []
    cur_start: int | None = None
    cur_max = 0.0
    threshold = 1.0
    for i, score in enumerate(window_scores):
        if score > threshold:
            if cur_start is None:
                cur_start = i
            cur_max = max(cur_max, score)
        elif cur_start is not None:
            hotspots.append(
                {
                    "start": cur_start + 1,
                    "end": i + window,
                    "score": round(cur_max, 3),
                }
            )
            cur_start = None
            cur_max = 0.0
    if cur_start is not None:
        hotspots.append(
            {
                "start": cur_start + 1,
                "end": len(seq),
                "score": round(cur_max, 3),
            }
        )

    positive = [s for s in window_scores if s > 0]
    overall = (sum(positive) / len(positive) / 4.5) if positive else 0.0
    return {
        "overall_score": round(min(max(overall, 0.0), 1.0), 3),
        "hotspots": hotspots,
        "window_scores": window_scores,
    }


def _net_charge(sequence: str) -> float:
    seq = _clean_sequence(sequence)
    pos = sum(
        1 / (1 + 10 ** (PHYSIOLOGICAL_PH - PK_POSITIVE[c])) for c in seq if c in PK_POSITIVE
    )
    neg = sum(
        1 / (1 + 10 ** (PK_NEGATIVE[c] - PHYSIOLOGICAL_PH)) for c in seq if c in PK_NEGATIVE
    )
    return round(pos - neg, 2)


def compute_stability_score(sequence: str) -> float:
    """Simple stability heuristic in [0, 1].

    Rewards balanced charge, presence of structure-forming residues (P, G in
    moderation, hydrophobic core) and penalises uninterrupted stretches of
    aggregation-prone residues.
    """

    seq = _clean_sequence(sequence)
    if not seq:
        return 0.0
    charge = abs(_net_charge(seq))
    charge_penalty = min(charge / 10, 0.4)  # cap at 0.4
    aggregation = compute_aggregation_propensity(sequence)["overall_score"]
    proline_bonus = min(seq.count("P") / max(len(seq), 1) * 1.5, 0.2)
    base = 0.7 - aggregation * 0.5 - charge_penalty + proline_bonus
    return round(min(max(base, 0.0), 1.0), 3)


def compute_bbb_penetration_score(sequence: str) -> float:
    """Rough blood-brain barrier penetration estimate in [0, 1].

    Smaller, more lipophilic, less polar peptides cross the BBB better.
    """

    seq = _clean_sequence(sequence)
    if not seq:
        return 0.0
    length_penalty = min(len(seq) / 30, 1.0)  # longer = harder to cross
    polar = sum(1 for c in seq if c in {"R", "K", "D", "E", "N", "Q", "H", "S", "T", "Y"})
    polar_fraction = polar / len(seq)
    hydrophobic = sum(1 for c in seq if c in {"A", "I", "L", "V", "F", "W", "M"})
    hydrophobic_fraction = hydrophobic / len(seq)
    base = 0.5 + hydrophobic_fraction * 0.5 - polar_fraction * 0.5 - length_penalty * 0.4
    return round(min(max(base, 0.0), 1.0), 3)


def estimate_half_life(sequence: str) -> str:
    """Crude half-life bucket. Returns a human string for the report.

    These ranges are deliberately approximate — anything more specific would
    overstate confidence given we have no sequence-specific protease data.
    """

    seq = _clean_sequence(sequence)
    n = len(seq)
    if n == 0:
        return "unknown"
    if n <= 5:
        return "very short (~5–15 minutes)"
    if n <= 10:
        return "short (~15–45 minutes)"
    if n <= 20:
        return "moderate (~30 minutes – 2 hours)"
    if n <= 35:
        return "moderate-to-long (~1–6 hours)"
    return "long (>6 hours, depends on modifications)"
