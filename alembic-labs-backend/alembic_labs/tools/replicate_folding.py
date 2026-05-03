"""Boltz-2 / Chai-1 inference via Replicate.

CRITICAL: model IDs are passed via env vars (``BOLTZ2_MODEL_ID``,
``CHAI1_MODEL_ID``) because Replicate revisions change frequently. Look up
the current versions at https://replicate.com/explore before deploying.

The output format of structure-prediction Replicate models varies by version
(some return URLs to PDB files, others return JSON with metrics + a PDB URL).
We normalise everything to the same dict shape so downstream code doesn't
need to care which model version is in use.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import replicate

from ..config import settings
from ..logging_setup import get_logger
from . import uniprot

log = get_logger(__name__)

POLL_TIMEOUT_SECONDS = 600  # 10 minutes
HTTP_TIMEOUT = 60.0


def _empty_result(error: str | None = None) -> dict[str, Any]:
    return {
        "success": False,
        "pdb_text": "",
        "plddt": None,
        "ptm": None,
        "iptm": None,
        "binding_score": None,
        "plddt_per_residue": None,
        "pae_matrix": None,
        "sequence_coverage": None,
        "error": error,
        "raw_output": None,
    }


def _coerce_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


async def _fetch_text(url: str) -> str:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


def _normalise_output(raw: Any) -> dict[str, Any]:
    """Pull common metrics + PDB text out of a Replicate output payload."""

    result: dict[str, Any] = {
        "pdb_text": "",
        "plddt": None,
        "ptm": None,
        "iptm": None,
        "binding_score": None,
        "plddt_per_residue": None,
        "pae_matrix": None,
        "sequence_coverage": None,
    }

    # Replicate returns either a dict (new schema), a list of files, or a
    # single file URL. We handle each case best-effort.
    if isinstance(raw, dict):
        for key in ("plddt_mean", "plddt"):
            if key in raw:
                result["plddt"] = _coerce_float(raw[key])
                break
        result["ptm"] = _coerce_float(raw.get("ptm"))
        result["iptm"] = _coerce_float(raw.get("iptm"))
        result["binding_score"] = _coerce_float(raw.get("binding_score"))
        result["plddt_per_residue"] = raw.get("plddt_per_residue") or raw.get("plddt_residues")
        result["pae_matrix"] = raw.get("pae") or raw.get("pae_matrix")
        result["sequence_coverage"] = raw.get("sequence_coverage")
        # PDB might be inline text or a URL to download.
        pdb_value = raw.get("pdb") or raw.get("structure") or raw.get("pdb_file")
        if isinstance(pdb_value, str) and "ATOM " in pdb_value:
            result["pdb_text"] = pdb_value
        result["__pdb_url"] = (
            pdb_value
            if isinstance(pdb_value, str) and pdb_value.startswith("http")
            else None
        )
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item.startswith("http"):
                result["__pdb_url"] = item
                break
    elif isinstance(raw, str):
        if "ATOM " in raw:
            result["pdb_text"] = raw
        elif raw.startswith("http"):
            result["__pdb_url"] = raw

    return result


async def _resolve_target_sequence(
    target_sequence: str | None, target_uniprot: str | None
) -> str | None:
    if target_sequence:
        return target_sequence
    if target_uniprot:
        entry = await uniprot.get_protein_by_id(target_uniprot)
        if entry and entry.get("sequence"):
            return entry["sequence"]
    return None


async def _run_replicate_model(
    model_id: str, inputs: dict[str, Any]
) -> dict[str, Any]:
    """Submit a Replicate run and poll until done. Async via asyncio.to_thread."""

    if not settings.REPLICATE_API_TOKEN or not model_id:
        return _empty_result(
            error="REPLICATE_API_TOKEN or model id not configured",
        )

    def _run_blocking() -> Any:
        # The replicate SDK is synchronous — run it on a worker thread.
        return replicate.run(model_id, input=inputs)

    try:
        raw = await asyncio.wait_for(
            asyncio.to_thread(_run_blocking),
            timeout=POLL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        log.warning("alembic.replicate.timeout", model=model_id)
        return _empty_result(error=f"timeout after {POLL_TIMEOUT_SECONDS}s")
    except Exception as err:  # noqa: BLE001 — propagate as structured error
        log.warning("alembic.replicate.run_failed", model=model_id, error=str(err))
        return _empty_result(error=str(err))

    normalised = _normalise_output(raw)
    pdb_url = normalised.pop("__pdb_url", None)
    if not normalised["pdb_text"] and pdb_url:
        try:
            normalised["pdb_text"] = await _fetch_text(pdb_url)
        except httpx.HTTPError as err:
            log.warning("alembic.replicate.pdb_fetch_failed", url=pdb_url, error=str(err))

    return {
        "success": bool(normalised["pdb_text"]) or normalised["plddt"] is not None,
        "pdb_text": normalised["pdb_text"],
        "plddt": normalised["plddt"],
        "ptm": normalised["ptm"],
        "iptm": normalised["iptm"],
        "binding_score": normalised["binding_score"],
        "plddt_per_residue": normalised["plddt_per_residue"],
        "pae_matrix": normalised["pae_matrix"],
        "sequence_coverage": normalised["sequence_coverage"],
        "error": None,
        "raw_output": raw if isinstance(raw, (dict, list, str)) else str(raw),
    }


async def run_boltz2_fold(
    peptide_sequence: str,
    target_sequence: str | None = None,
    target_uniprot: str | None = None,
) -> dict[str, Any]:
    """Run Boltz-2 prediction. Returns normalised dict (see module docstring)."""

    if not peptide_sequence:
        return _empty_result(error="empty peptide sequence")
    target = await _resolve_target_sequence(target_sequence, target_uniprot)

    inputs: dict[str, Any] = {"peptide_sequence": peptide_sequence}
    if target:
        inputs["target_sequence"] = target

    return await _run_replicate_model(settings.BOLTZ2_MODEL_ID, inputs)


async def run_chai1_fold(
    peptide_sequence: str,
    target_sequence: str | None = None,
) -> dict[str, Any]:
    """Run Chai-1 prediction (used for cross-validation)."""

    if not peptide_sequence:
        return _empty_result(error="empty peptide sequence")
    inputs: dict[str, Any] = {"peptide_sequence": peptide_sequence}
    if target_sequence:
        inputs["target_sequence"] = target_sequence
    return await _run_replicate_model(settings.CHAI1_MODEL_ID, inputs)


async def cross_validate(
    peptide_sequence: str, target_sequence: str
) -> dict[str, Any]:
    """Run Boltz-2 + Chai-1 in parallel and compute an agreement score."""

    boltz_task = asyncio.create_task(
        run_boltz2_fold(peptide_sequence, target_sequence=target_sequence)
    )
    chai_task = asyncio.create_task(
        run_chai1_fold(peptide_sequence, target_sequence=target_sequence)
    )
    boltz_res, chai_res = await asyncio.gather(boltz_task, chai_task)

    agreement_score: float | None = None
    if boltz_res.get("plddt") is not None and chai_res.get("plddt") is not None:
        # Both models commonly report pLDDT either 0–1 or 0–100; normalise to %.
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
