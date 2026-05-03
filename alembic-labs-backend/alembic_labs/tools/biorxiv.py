"""bioRxiv preprint search.

bioRxiv's public API (https://api.biorxiv.org/) doesn't expose a free-text
search endpoint — only DOI/date queries. To stay reasonable for an MVP we
use ``api.biorxiv.org/details/biorxiv/{interval}`` to fetch recent preprints
and then filter client-side by simple keyword match. This isn't a great
search but it costs nothing and is rate-limit friendly.

Note: when bioRxiv is unreachable, we degrade to an empty list — the
literature agent uses PubMed as the primary source and treats bioRxiv as a
nice-to-have signal.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx

from ..logging_setup import get_logger

log = get_logger(__name__)

BASE = "https://api.biorxiv.org/details/biorxiv"
HTTP_TIMEOUT = 30.0
USER_AGENT = "alembic-labs/0.1 (https://alembic.bio)"


def _term_matches(text: str, terms: list[str]) -> bool:
    text_lower = text.lower()
    return all(term.lower() in text_lower for term in terms if term)


async def search_biorxiv(
    query: str,
    *,
    max_results: int = 5,
    days_window: int = 730,
) -> list[dict[str, Any]]:
    """Pull a recent batch of preprints and filter by ``query`` keywords.

    Returns ``[{doi, title, abstract, authors, posted_date}, ...]``.
    """

    if not query.strip():
        return []
    terms = [t for t in query.split() if t.strip()]
    end = date.today()
    start = end - timedelta(days=days_window)
    interval = f"{start.isoformat()}/{end.isoformat()}"

    out: list[dict[str, Any]] = []
    headers = {"User-Agent": USER_AGENT}
    cursor = 0
    # Hard cap on pagination to keep latency bounded.
    page_count = 0
    max_pages = 6

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=headers) as client:
            while page_count < max_pages and len(out) < max_results:
                resp = await client.get(f"{BASE}/{interval}/{cursor}")
                resp.raise_for_status()
                data = resp.json()
                items = data.get("collection", []) or []
                if not items:
                    break
                for item in items:
                    title = (item.get("title") or "").strip()
                    abstract = (item.get("abstract") or "").strip()
                    haystack = f"{title}\n{abstract}"
                    if not _term_matches(haystack, terms):
                        continue
                    out.append(
                        {
                            "doi": item.get("doi", ""),
                            "title": title,
                            "abstract": abstract,
                            "authors": [
                                a.strip()
                                for a in (item.get("authors") or "").split(";")
                                if a.strip()
                            ],
                            "posted_date": item.get("date", ""),
                        }
                    )
                    if len(out) >= max_results:
                        break
                cursor += len(items)
                page_count += 1
                # bioRxiv responses include a ``cursor`` we could trust, but the
                # safer pattern is to advance by the page size we observed.
    except httpx.HTTPError as err:
        log.warning("alembic.biorxiv.search_failed", query=query, error=str(err))
        return out

    return out[:max_results]
