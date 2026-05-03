"""Provider-agnostic facade for structure prediction.

Picks BioLM (default) or Replicate (legacy fallback) based on
``settings.STRUCTURE_PROVIDER``. Always returns the same dict shape so the
structural agent stays unchanged regardless of provider.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from ..config import settings
from . import biolm_folding, replicate_folding


def _provider() -> str:
    return settings.structure_provider_normalised


async def run_boltz2_fold(
    peptide_sequence: str,
    target_sequence: str | None = None,
    target_uniprot: str | None = None,
) -> dict[str, Any]:
    if _provider() == "biolm":
        return await biolm_folding.run_boltz2_fold(
            peptide_sequence,
            target_sequence=target_sequence,
            target_uniprot=target_uniprot,
        )
    return await replicate_folding.run_boltz2_fold(
        peptide_sequence,
        target_sequence=target_sequence,
        target_uniprot=target_uniprot,
    )


async def run_chai1_fold(
    peptide_sequence: str,
    target_sequence: str | None = None,
) -> dict[str, Any]:
    if _provider() == "biolm":
        return await biolm_folding.run_chai1_fold(
            peptide_sequence, target_sequence=target_sequence
        )
    return await replicate_folding.run_chai1_fold(
        peptide_sequence, target_sequence=target_sequence
    )


async def cross_validate(
    peptide_sequence: str, target_sequence: str
) -> dict[str, Any]:
    """Run Boltz-2 + Chai-1 in parallel via the active provider."""
    boltz_task = asyncio.create_task(
        run_boltz2_fold(peptide_sequence, target_sequence=target_sequence)
    )
    chai_task = asyncio.create_task(
        run_chai1_fold(peptide_sequence, target_sequence=target_sequence)
    )
    boltz_res, chai_res = await asyncio.gather(boltz_task, chai_task)

    agreement_score: float | None = None
    if boltz_res.get("plddt") is not None and chai_res.get("plddt") is not None:
        def _pct(v: float) -> float:
            return v if v > 1.5 else v * 100

        diff = abs(_pct(boltz_res["plddt"]) - _pct(chai_res["plddt"]))
        agreement_score = round(max(0.0, 1.0 - diff / 100.0), 3)

    return {
        "boltz2": boltz_res,
        "chai1": chai_res,
        "agreement_score": agreement_score,
    }


def save_pdb_to_file(pdb_text: str, fold_id: int) -> str:
    """Persist PDB to ``settings.PDB_STORAGE_DIR`` and return the absolute path."""
    directory: Path = settings.PDB_STORAGE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"fold_{fold_id}.pdb"
    target.write_text(pdb_text or "", encoding="utf-8")
    return str(target.resolve())
