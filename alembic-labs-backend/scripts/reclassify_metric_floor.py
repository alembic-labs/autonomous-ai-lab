"""One-off: re-apply the metric floor to existing folds.

Use after shipping the structural-prompt + metric-floor fix to lift any
fold whose raw metrics permit at least PROMISING but which the LLM
discarded purely on chemistry-class grounds (D-AA, lipid, non-canonical).

Idempotent: only writes when the floor lifts the verdict; folds whose
verdict is already at or above the floor are left untouched.

Run inside the backend container:

    docker exec deploy-backend-1 python -m scripts.reclassify_metric_floor
"""

from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from alembic_labs.agents.structural import (
    _VERDICT_RANK,
    _compute_metric_floor,
    _normalise_plddt,
)
from alembic_labs.db.models import Fold
from alembic_labs.db.session import SessionLocal


async def main() -> None:
    async with SessionLocal() as session:
        folds = (
            (
                await session.execute(
                    select(Fold)
                    .where(Fold.fold_verdict.in_(["DISCARDED", "PROMISING", "REFINED"]))
                    .where(Fold.discard_reason.is_(None))
                    .order_by(Fold.id.asc())
                )
            )
            .scalars()
            .all()
        )

        lifted: list[tuple[int, str, str, str]] = []
        for f in folds:
            current = (f.fold_verdict or "").upper()
            if current not in _VERDICT_RANK:
                continue

            plddt = _normalise_plddt(f.confidence_plddt)
            floor = _compute_metric_floor(
                plddt=plddt,
                ptm=f.confidence_ptm,
                iptm=f.confidence_iptm,
                binding_probability=f.binding_probability,
                chai_agreement=f.chai_agreement,
            )

            if _VERDICT_RANK[floor] <= _VERDICT_RANK[current]:
                continue

            note = (
                f"Verdict reclassified: {current} → {floor}. Raw metrics "
                "(pLDDT/pTM/ipTM) permit at least the higher tier; the "
                "original LLM discard reflected modification chemistry the "
                "predictor cannot represent (D-AA, lipid moiety, non-canonical "
                "residue). Per the metric-floor rule this is a caveat, not a "
                "verdict downgrade. Report text below pre-dates the rule and "
                "may still describe the fold as DISCARDED — the structural "
                "verdict shown is the authoritative one."
            )
            existing = []
            if f.caveats:
                try:
                    existing = json.loads(f.caveats)
                    if not isinstance(existing, list):
                        existing = [str(existing)]
                except json.JSONDecodeError:
                    existing = [f.caveats]
            existing.append(note)

            f.fold_verdict = floor
            f.status = floor  # mirror — same logic as Communicator's _final_status
            f.caveats = json.dumps(existing)
            lifted.append((f.id, current, floor, f.peptide_name or "?"))

        await session.commit()

    print(f"Lifted {len(lifted)} folds:")
    for row in lifted:
        print(f"  #{row[0]:>3}  {row[3]:<14}  {row[1]} → {row[2]}")


if __name__ == "__main__":
    asyncio.run(main())
