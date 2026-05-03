"""ChEMBL REST client (https://www.ebi.ac.uk/chembl/api/data/).

Used by the Clinical agent to enrich folds with bioactivity context — known
binders, mechanism-of-action labels and reference compounds. We do not use
this to make medical claims; the data is published, but human relevance
varies and the Clinical agent must caveat appropriately.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..logging_setup import get_logger
from ._retry import with_retry

log = get_logger(__name__)

BASE = "https://www.ebi.ac.uk/chembl/api/data"
HTTP_TIMEOUT = 30.0
USER_AGENT = "alembic-labs/0.1 (https://alembic.bio)"


@with_retry(name="chembl.search_target")
async def _search_target_raw(
    name: str, limit: int
) -> list[dict[str, Any]]:
    headers = {"User-Agent": USER_AGENT}
    params = {
        "format": "json",
        "limit": str(limit),
        "pref_name__icontains": name,
    }
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=headers) as client:
        resp = await client.get(f"{BASE}/target.json", params=params)
        resp.raise_for_status()
        data = resp.json()
    return list(data.get("targets") or [])


async def search_target(name: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Search ChEMBL targets by free-text name (best-effort)."""

    if not name.strip():
        return []
    try:
        targets = await _search_target_raw(name, limit)
    except httpx.HTTPError as err:
        log.warning("alembic.chembl.target_search_failed", name=name, error=str(err))
        return []
    return [
        {
            "chembl_id": t.get("target_chembl_id"),
            "name": t.get("pref_name"),
            "type": t.get("target_type"),
            "organism": t.get("organism"),
        }
        for t in targets
    ]


@with_retry(name="chembl.target_by_uniprot")
async def _target_by_uniprot_raw(
    uniprot_id: str, limit: int
) -> list[dict[str, Any]]:
    headers = {"User-Agent": USER_AGENT}
    params = {
        "target_components__accession": uniprot_id,
        "format": "json",
        "limit": str(limit),
    }
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=headers) as client:
        resp = await client.get(f"{BASE}/target.json", params=params)
        resp.raise_for_status()
        data = resp.json()
    return list(data.get("targets") or [])


async def get_target_by_uniprot(
    uniprot_id: str, *, limit: int = 3
) -> list[dict[str, Any]]:
    """Resolve a ChEMBL target via its UniProt cross-reference.

    This is much more reliable than free-text name matching — the Researcher
    agent provides UniProt IDs from ``canonical_targets`` and we get the
    correct ChEMBL target every time.
    """
    if not uniprot_id.strip():
        return []
    try:
        targets = await _target_by_uniprot_raw(uniprot_id, limit)
    except httpx.HTTPError as err:
        log.warning(
            "alembic.chembl.target_by_uniprot_failed",
            uniprot_id=uniprot_id,
            error=str(err),
        )
        return []
    return [
        {
            "chembl_id": t.get("target_chembl_id"),
            "name": t.get("pref_name"),
            "type": t.get("target_type"),
            "organism": t.get("organism"),
        }
        for t in targets
    ]


async def get_known_binders(
    target_chembl_id: str, *, limit: int = 10
) -> list[dict[str, Any]]:
    """Fetch top bioactivities for a target, normalised to a compact shape.

    Returns ``[{chembl_id, kd_nm, pchembl_value, mechanism, smiles}, ...]``.
    Only entries with a numeric ``pchembl_value`` are returned, sorted descending.
    """

    if not target_chembl_id.strip():
        return []

    @with_retry(name="chembl.binders")
    async def _fetch() -> dict[str, Any]:
        params = {
            "target_chembl_id": target_chembl_id,
            "pchembl_value__isnull": "false",
            "format": "json",
            "limit": str(min(limit * 3, 30)),
            "order_by": "-pchembl_value",
        }
        headers = {"User-Agent": USER_AGENT}
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=headers) as client:
            resp = await client.get(f"{BASE}/activity.json", params=params)
            resp.raise_for_status()
            return resp.json()

    try:
        data = await _fetch()
    except httpx.HTTPError as err:
        log.warning(
            "alembic.chembl.binders_failed",
            target=target_chembl_id,
            error=str(err),
        )
        return []

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for activity in data.get("activities", []) or []:
        chembl_id = activity.get("molecule_chembl_id")
        if not chembl_id or chembl_id in seen:
            continue
        seen.add(chembl_id)
        try:
            pchembl = float(activity.get("pchembl_value") or "nan")
        except (TypeError, ValueError):
            continue
        try:
            kd_nm: float | None = float(activity.get("standard_value")) if activity.get(
                "standard_units"
            ) == "nM" else None
        except (TypeError, ValueError):
            kd_nm = None
        out.append(
            {
                "chembl_id": chembl_id,
                "kd_nm": kd_nm,
                "pchembl_value": pchembl,
                "mechanism": activity.get("standard_type"),
                "smiles": activity.get("canonical_smiles"),
            }
        )
        if len(out) >= limit:
            break
    return out


async def get_compound(chembl_id: str) -> dict[str, Any] | None:
    """Pull compact metadata for a ChEMBL compound."""

    if not chembl_id.strip():
        return None

    @with_retry(name="chembl.compound")
    async def _fetch() -> dict[str, Any] | None:
        params = {"format": "json"}
        headers = {"User-Agent": USER_AGENT}
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=headers) as client:
            resp = await client.get(f"{BASE}/molecule/{chembl_id}.json", params=params)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()

    try:
        data = await _fetch()
        if data is None:
            return None
    except httpx.HTTPError as err:
        log.warning(
            "alembic.chembl.compound_failed",
            chembl_id=chembl_id,
            error=str(err),
        )
        return None
    return {
        "chembl_id": chembl_id,
        "pref_name": data.get("pref_name"),
        "max_phase": data.get("max_phase"),
        "molecule_type": data.get("molecule_type"),
        "smiles": (data.get("molecule_structures") or {}).get("canonical_smiles"),
    }
