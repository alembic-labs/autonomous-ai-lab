"""Boltz-2 / Chai-1 inference via BioLM (https://biolm.ai).

BioLM exposes a uniform REST surface:
    POST {BIOLM_BASE_URL}{path}/   with header Authorization: Token <BIOLMAI_TOKEN>

We submit one item per request (Boltz-2 enforces batch_size = 1 anyway), then
normalise the response to the same dict shape produced by ``replicate_folding``
so downstream code (the structural agent, the API, the frontend) stays put.

Boltz-2 returns mmCIF — we convert it to PDB on the fly using biopython, since
the persistence layer and the React viewer expect PDB text.
"""

from __future__ import annotations

import io
import json
from typing import Any

import httpx
from Bio.PDB import MMCIFParser, PDBIO

from ..config import settings
from ..logging_setup import get_logger
from . import uniprot
from ._retry import with_retry

log = get_logger(__name__)


def _empty_result(error: str | None = None) -> dict[str, Any]:
    return {
        "success": False,
        "pdb_text": "",
        "plddt": None,
        "ptm": None,
        "iptm": None,
        "binding_score": None,
        # Boltz-2 affinity module — its headline feature.
        "binding_probability": None,  # 0..1, "this is a binder" probability
        "binding_pic50": None,         # predicted pIC50 (negative log10 of M Kd)
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


def _cif_to_pdb(cif_text: str) -> str:
    """Convert mmCIF text → PDB text. Returns "" on failure (logged)."""
    if not cif_text:
        return ""
    try:
        parser = MMCIFParser(QUIET=True)
        structure = parser.get_structure("model", io.StringIO(cif_text))
        buf = io.StringIO()
        writer = PDBIO()
        writer.set_structure(structure)
        writer.save(buf)
        return buf.getvalue()
    except Exception as err:  # noqa: BLE001
        log.warning("alembic.biolm.cif_to_pdb_failed", error=str(err))
        return ""


def _normalise_result(item: dict[str, Any]) -> dict[str, Any]:
    """Pull metrics + structure out of a single BioLM result entry."""

    cif_text = item.get("cif") or ""
    pdb_text = _cif_to_pdb(cif_text) if cif_text else ""

    confidence = item.get("confidence") or {}
    affinity = item.get("affinity") or {}

    plddt_complex = _coerce_float(confidence.get("complex_plddt"))
    plddt_per_token = item.get("plddt")
    if isinstance(plddt_per_token, list) and not plddt_per_token:
        plddt_per_token = None

    # Boltz-2 affinity module returns two distinct numbers:
    # 1. ``affinity_probability_binary`` — calibrated binder/non-binder probability (0..1)
    # 2. ``affinity_pred_value``         — predicted pIC50 (negative log10 of molar IC50)
    binding_probability = _coerce_float(affinity.get("affinity_probability_binary"))
    binding_pic50 = _coerce_float(affinity.get("affinity_pred_value"))
    # Keep the legacy ``binding_score`` field populated with whichever signal we
    # have (probability preferred) so older code paths don't break.
    binding_score = (
        binding_probability if binding_probability is not None else binding_pic50
    )

    return {
        "success": bool(pdb_text) or plddt_complex is not None,
        "pdb_text": pdb_text,
        "plddt": plddt_complex,
        "ptm": _coerce_float(confidence.get("ptm")),
        "iptm": _coerce_float(confidence.get("iptm")),
        "binding_score": binding_score,
        "binding_probability": binding_probability,
        "binding_pic50": binding_pic50,
        "plddt_per_residue": plddt_per_token,
        "pae_matrix": item.get("pae"),
        "sequence_coverage": None,
        "error": None,
    }


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


_AA_OK = set("ACDEFGHIKLMNPQRSTVWY")


def _sanitize_protein(seq: str) -> str:
    """Drop non-canonical residues — BioLM rejects sequences with X/U/B/Z/etc."""
    return "".join(c for c in seq.upper() if c in _AA_OK)


def _build_items(
    peptide_sequence: str,
    target_sequence: str | None,
) -> list[dict[str, Any]] | None:
    """One Boltz/Chai item. Both `id` and `name` are sent — Chai-1 requires `name`."""
    pep = _sanitize_protein(peptide_sequence)
    if not pep:
        return None
    molecules: list[dict[str, Any]] = [
        {"id": "A", "name": "peptide", "type": "protein", "sequence": pep},
    ]
    if target_sequence:
        tgt = _sanitize_protein(target_sequence)
        if tgt:
            molecules.append(
                {"id": "B", "name": "target", "type": "protein", "sequence": tgt}
            )
    return [{"molecules": molecules}]


@with_retry(max_attempts=3, backoff_base=3.0, max_backoff_seconds=20.0, name="biolm.post")
async def _post_raw(path: str, payload: dict[str, Any]) -> httpx.Response:
    """Internal: actually fire the request (with retry on 5xx/timeout)."""
    url = settings.BIOLM_BASE_URL.rstrip("/") + path
    headers = {
        "Authorization": f"Token {settings.BIOLMAI_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=settings.BIOLM_TIMEOUT_SECONDS) as client:
        resp = await client.post(url, headers=headers, content=json.dumps(payload))
    # Bubble up 5xx so the retry decorator can intercept; 4xx returned as-is.
    if 500 <= resp.status_code < 600:
        resp.raise_for_status()
    return resp


async def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Send a request to BioLM. Returns ``{ok, json|error}``."""
    if not settings.BIOLMAI_TOKEN:
        return {"ok": False, "error": "BIOLMAI_TOKEN not configured"}

    try:
        resp = await _post_raw(path, payload)
    except httpx.HTTPError as err:
        log.warning("alembic.biolm.transport_error", path=path, error=str(err))
        return {"ok": False, "error": f"transport: {err}"}

    if resp.status_code >= 400:
        body = resp.text[:500]
        log.warning(
            "alembic.biolm.http_error",
            path=path,
            status=resp.status_code,
            body=body,
        )
        return {"ok": False, "error": f"{resp.status_code}: {body}"}

    try:
        return {"ok": True, "json": resp.json()}
    except json.JSONDecodeError as err:
        return {"ok": False, "error": f"invalid JSON response: {err}"}


def _first_result(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        results = payload.get("results")
        if isinstance(results, list) and results:
            first = results[0]
            return first if isinstance(first, dict) else None
        if "cif" in payload or "confidence" in payload:
            return payload
    if isinstance(payload, list) and payload:
        first = payload[0]
        return first if isinstance(first, dict) else None
    return None


async def _run(
    path: str,
    peptide_sequence: str,
    target_sequence: str | None,
    params: dict[str, Any],
) -> dict[str, Any]:
    if not peptide_sequence:
        return _empty_result(error="empty peptide sequence")

    items = _build_items(peptide_sequence, target_sequence)
    if items is None:
        return _empty_result(error="peptide had no canonical residues")

    payload: dict[str, Any] = {"items": items, "params": params}

    response = await _post(path, payload)
    if not response.get("ok"):
        return _empty_result(error=response.get("error"))

    raw = response["json"]
    item = _first_result(raw)
    if item is None:
        return _empty_result(error="empty results from BioLM")

    normalised = _normalise_result(item)
    normalised["raw_output"] = raw
    return normalised


_BASE_BOLTZ2_PARAMS: dict[str, Any] = {
    "include": ["pae", "plddt"],
    "diffusion_samples": 1,
}


# Boltz-2's affinity head returns a binary binder probability and a
# log10(IC50)-style affinity value when ``params.affinity.binder`` names
# a chain. The head was trained on protein-ligand pairs (small molecules),
# so on protein-protein complexes the BioLM gateway sometimes returns a
# 400 "Boltz prediction did not produce an output structure" — the worker
# crashes silently. We still want the affinity numbers when they're
# available, so the call site below tries ONCE with affinity enabled and
# falls back to the structure-only request when BioLM rejects it. Sampling
# steps capped at 50 (vs default 200) — enough resolution for the binary
# classifier and keeps the per-call cost bounded. MW correction is OFF
# because peptides are 2-4 kDa, not drug-like small molecules.
_AFFINITY_PARAMS: dict[str, Any] = {
    "affinity": {"binder": "A"},
    "affinity_mw_correction": False,
    "sampling_steps_affinity": 50,
    "diffusion_samples_affinity": 5,
}


def _affinity_failure(result: dict[str, Any]) -> bool:
    """True if the Boltz-2 result looks like an affinity-related rejection.

    BioLM returns ``400 Boltz prediction did not produce an output
    structure`` when the affinity head crashes on a protein-only complex.
    The error string is stable enough to match — and we additionally
    require that the result has no PDB so we never throw away a partial
    success.
    """
    if result.get("success"):
        return False
    if result.get("pdb_text"):
        return False
    err = (result.get("error") or "").lower()
    return "did not produce" in err or "no output" in err


async def run_boltz2_fold(
    peptide_sequence: str,
    target_sequence: str | None = None,
    target_uniprot: str | None = None,
) -> dict[str, Any]:
    target = await _resolve_target_sequence(target_sequence, target_uniprot)

    # Try with affinity first. If BioLM 400s with the "no output" pattern
    # (almost certainly the affinity head choking on a protein-protein
    # complex), retry without affinity so the cycle still gets a structure.
    primary_params = {**_BASE_BOLTZ2_PARAMS, **_AFFINITY_PARAMS}
    result = await _run(
        settings.BIOLM_BOLTZ2_PATH, peptide_sequence, target, params=primary_params
    )
    if _affinity_failure(result):
        log.info(
            "alembic.biolm.affinity_fallback",
            error=(result.get("error") or "")[:200],
        )
        result = await _run(
            settings.BIOLM_BOLTZ2_PATH,
            peptide_sequence,
            target,
            params=_BASE_BOLTZ2_PARAMS,
        )
    return result


async def run_chai1_fold(
    peptide_sequence: str,
    target_sequence: str | None = None,
) -> dict[str, Any]:
    return await _run(
        settings.BIOLM_CHAI1_PATH,
        peptide_sequence,
        target_sequence,
        params={"num_diffn_samples": 1, "use_esm_embeddings": True, "include": []},
    )
