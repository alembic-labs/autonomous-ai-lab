"""UniProt REST client (https://rest.uniprot.org/).

We need three things from UniProt:
1. Search by name → list of candidate accessions.
2. Fetch full entry by accession → sequence + organism + function.
3. Domain annotations → structural domains, binding sites, GO terms.

All calls return ``None`` / empty on failure (logged as warning).
"""

from __future__ import annotations

from typing import Any

import httpx

from ..logging_setup import get_logger
from ._retry import with_retry

log = get_logger(__name__)

REST_BASE = "https://rest.uniprot.org/uniprotkb"
HTTP_TIMEOUT = 30.0
USER_AGENT = "alembic-labs/0.1 (https://alembic.bio)"


def _shape_entry(entry: dict[str, Any]) -> dict[str, Any]:
    accession = entry.get("primaryAccession", "")
    name = (
        entry.get("proteinDescription", {})
        .get("recommendedName", {})
        .get("fullName", {})
        .get("value", "")
    )
    sequence_obj = entry.get("sequence", {})
    sequence = sequence_obj.get("value", "")
    length = sequence_obj.get("length") or len(sequence)
    organism = entry.get("organism", {}).get("scientificName", "")
    function = ""
    for comment in entry.get("comments", []) or []:
        if comment.get("commentType") == "FUNCTION":
            texts = comment.get("texts", []) or []
            if texts:
                function = texts[0].get("value", "")
                break
    structures = []
    for x in entry.get("uniProtKBCrossReferences", []) or []:
        if x.get("database") == "PDB":
            structures.append(x.get("id", ""))
    return {
        "uniprot_id": accession,
        "name": name,
        "sequence": sequence,
        "length": length,
        "organism": organism,
        "function": function,
        "structures": structures,
    }


@with_retry(name="uniprot.search")
async def _search_raw(query: str, limit: int) -> dict[str, Any]:
    params = {
        "query": query,
        "format": "json",
        "size": str(limit),
        "fields": "accession,protein_name,organism_name,length",
    }
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=headers) as client:
        resp = await client.get(f"{REST_BASE}/search", params=params)
        resp.raise_for_status()
        return resp.json()


async def search_protein(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Search UniProtKB for proteins matching ``query``."""

    if not query.strip():
        return []
    try:
        data = await _search_raw(query, limit)
    except httpx.HTTPError as err:
        log.warning("alembic.uniprot.search_failed", query=query, error=str(err))
        return []
    return [_shape_entry(e) for e in (data.get("results") or [])]


@with_retry(name="uniprot.get_by_id")
async def _fetch_entry(uniprot_id: str) -> dict[str, Any] | None:
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=headers) as client:
        resp = await client.get(
            f"{REST_BASE}/{uniprot_id}", params={"format": "json"}
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()


async def get_protein_by_id(uniprot_id: str) -> dict[str, Any] | None:
    """Fetch a single UniProt entry by accession."""

    if not uniprot_id.strip():
        return None
    try:
        data = await _fetch_entry(uniprot_id)
    except httpx.HTTPError as err:
        log.warning("alembic.uniprot.get_failed", uniprot_id=uniprot_id, error=str(err))
        return None
    if data is None:
        return None
    return _shape_entry(data)


async def get_domain_annotations(uniprot_id: str) -> dict[str, Any]:
    """Pull structural domains, binding sites and GO terms.

    Returns:
        {
          "domains": [{"type", "start", "end", "description"}],
          "binding_sites": [{"position", "ligand", "description"}],
          "gene_ontology": [{"id", "term", "aspect"}]
        }
    """

    empty = {"domains": [], "binding_sites": [], "gene_ontology": []}
    if not uniprot_id.strip():
        return empty
    try:
        entry = await _fetch_entry(uniprot_id)
    except httpx.HTTPError as err:
        log.warning(
            "alembic.uniprot.domain_failed",
            uniprot_id=uniprot_id,
            error=str(err),
        )
        return empty
    if entry is None:
        return empty

    domains: list[dict[str, Any]] = []
    binding_sites: list[dict[str, Any]] = []
    DOMAIN_TYPES = {
        "DOMAIN",
        "REGION",
        "MOTIF",
        "REPEAT",
        "ZINC_FING",
        "DNA_BIND",
        "TRANSMEM",
        "TOPO_DOM",
        "COILED",
        "COMPBIAS",
    }
    for feat in entry.get("features", []) or []:
        ftype = (feat.get("type") or "").upper().replace(" ", "_")
        loc = feat.get("location") or {}
        start = (loc.get("start") or {}).get("value")
        end = (loc.get("end") or {}).get("value")
        description = feat.get("description") or feat.get("type") or ""
        if ftype in DOMAIN_TYPES:
            domains.append(
                {
                    "type": feat.get("type"),
                    "start": start,
                    "end": end,
                    "description": description,
                }
            )
        elif ftype in {"BINDING", "ACT_SITE", "SITE"}:
            ligand = (feat.get("ligand") or {}).get("name", "")
            binding_sites.append(
                {
                    "position": start if start == end or end is None else f"{start}-{end}",
                    "ligand": ligand,
                    "description": description,
                }
            )

    gene_ontology: list[dict[str, Any]] = []
    for x in entry.get("uniProtKBCrossReferences", []) or []:
        if x.get("database") != "GO":
            continue
        term = ""
        aspect = ""
        for prop in x.get("properties", []) or []:
            if prop.get("key") == "GoTerm":
                term = prop.get("value", "")
            elif prop.get("key") == "GoEvidenceType":
                aspect = prop.get("value", "")
        gene_ontology.append({"id": x.get("id", ""), "term": term, "aspect": aspect})

    return {
        "domains": domains,
        "binding_sites": binding_sites,
        "gene_ontology": gene_ontology,
    }
