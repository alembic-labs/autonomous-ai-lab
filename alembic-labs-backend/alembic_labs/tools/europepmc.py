"""Europe PMC unified literature search.

Europe PMC (https://europepmc.org/RestfulWebService) indexes both PubMed and
preprint servers (bioRxiv, medRxiv, Research Square, etc.) under a single
relevance-ranked search API. We use it as a strict upgrade over the previous
bioRxiv client-side scan: one request, real ranking, source filtering.

Compared to ``biorxiv.py``:

- ``biorxiv.py`` downloads 600+ preprints per cycle and grep-filters them.
- ``europepmc`` issues a single full-text query with proper ranking and
  returns the top-N hits in <1s.

Returns the same compact shape as ``search_biorxiv`` so existing callers in
``literature.py`` can switch over with minimal changes.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..logging_setup import get_logger
from ._retry import with_retry

log = get_logger(__name__)

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
HTTP_TIMEOUT = 30.0
USER_AGENT = "alembic-labs/0.1 (https://alembic.bio)"


@with_retry(name="europepmc.search")
async def _search_raw(query: str, page_size: int) -> dict[str, Any]:
    params = {
        "query": query,
        "format": "json",
        "pageSize": str(page_size),
        "resultType": "core",
    }
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=headers) as client:
        resp = await client.get(f"{BASE}/search", params=params)
        resp.raise_for_status()
        return resp.json()


def _shape_result(item: dict[str, Any]) -> dict[str, Any]:
    """Normalise an Europe PMC result into the lab's compact paper schema."""
    authors_raw = item.get("authorString") or ""
    authors = [a.strip() for a in authors_raw.split(",") if a.strip()]
    year_text = item.get("pubYear") or ""
    try:
        year = int(year_text) if year_text.isdigit() else None
    except ValueError:
        year = None
    source = item.get("source") or ""
    pmid = item.get("pmid") or ""
    doi = item.get("doi") or ""
    is_preprint = source == "PPR"
    return {
        # The lab's literature agent uses ``pmid`` as the primary key when
        # available — preprints don't have one, so we emit the DOI instead and
        # mark them with ``preprint=True``.
        "pmid": pmid if pmid else "",
        "doi": doi,
        "title": (item.get("title") or "").strip(),
        "abstract": (item.get("abstractText") or "").strip(),
        "authors": authors,
        "year": year,
        "journal": (item.get("journalTitle") or item.get("source") or "").strip(),
        "source": source,
        "preprint": is_preprint,
    }


async def search_literature(
    query: str,
    *,
    max_results: int = 5,
    preprints_only: bool = False,
) -> list[dict[str, Any]]:
    """Search Europe PMC for relevant literature.

    Args:
        query: Free-text query (Lucene-style supported, but plain text works).
        max_results: Cap on results returned.
        preprints_only: If True, restrict to preprint sources (PPR).

    Returns: list of papers in the same compact shape used by ``pubmed.py``.
    """
    if not query.strip():
        return []
    full_query = f"({query}) AND SRC:PPR" if preprints_only else query
    try:
        data = await _search_raw(full_query, max_results)
    except httpx.HTTPError as err:
        log.warning("alembic.europepmc.search_failed", query=query, error=str(err))
        return []
    items = (data.get("resultList") or {}).get("result") or []
    return [_shape_result(it) for it in items[:max_results]]


async def search_preprints(
    query: str, *, max_results: int = 5
) -> list[dict[str, Any]]:
    """Backwards-compatible alias for the bioRxiv-only call site."""
    return await search_literature(
        query, max_results=max_results, preprints_only=True
    )
