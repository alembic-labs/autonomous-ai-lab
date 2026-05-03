"""Async PubMed E-utilities client.

NCBI doesn't require an API key for low-volume requests, but applies a soft
3 req/s rate limit. We sleep 0.4s between calls to stay well below it. All
errors degrade gracefully to empty results — the agent loop should keep
running even if PubMed is slow or unreachable.
"""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from ..logging_setup import get_logger
from ._retry import with_retry

log = get_logger(__name__)

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
HTTP_TIMEOUT = 30.0
RATE_DELAY_S = 0.4
USER_AGENT = "alembic-labs/0.1 (https://alembic.bio)"


@with_retry(name="pubmed.esearch")
async def _esearch(client: httpx.AsyncClient, query: str, retmax: int) -> list[str]:
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": str(retmax),
        "retmode": "json",
        "sort": "relevance",
    }
    resp = await client.get(ESEARCH_URL, params=params)
    resp.raise_for_status()
    data = resp.json()
    return list(data.get("esearchresult", {}).get("idlist", []) or [])


@with_retry(name="pubmed.efetch")
async def _efetch(client: httpx.AsyncClient, pmids: list[str]) -> str:
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
    }
    resp = await client.get(EFETCH_URL, params=params)
    resp.raise_for_status()
    return resp.text


def _parse_articles(xml_text: str) -> list[dict[str, Any]]:
    """Parse PubMed efetch XML into a list of compact dicts."""

    out: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as err:
        log.warning("alembic.pubmed.xml_parse_failed", error=str(err))
        return out

    for art in root.findall(".//PubmedArticle"):
        pmid_node = art.find(".//PMID")
        title_node = art.find(".//ArticleTitle")
        journal_node = art.find(".//Journal/Title")
        year_node = art.find(".//PubDate/Year")
        if year_node is None:
            year_node = art.find(".//PubDate/MedlineDate")

        abstract_parts: list[str] = []
        for ab in art.findall(".//Abstract/AbstractText"):
            label = ab.attrib.get("Label")
            text = "".join(ab.itertext()).strip()
            if not text:
                continue
            abstract_parts.append(f"{label}: {text}" if label else text)

        authors: list[str] = []
        for a in art.findall(".//AuthorList/Author"):
            last = a.findtext("LastName")
            first = a.findtext("ForeName")
            initials = a.findtext("Initials")
            if last and (first or initials):
                authors.append(f"{last} {first or initials}")
            elif last:
                authors.append(last)

        year_text = (year_node.text or "").strip() if year_node is not None else ""
        try:
            year_int: int | None = int(year_text[:4]) if year_text[:4].isdigit() else None
        except ValueError:
            year_int = None

        out.append(
            {
                "pmid": (pmid_node.text or "").strip() if pmid_node is not None else "",
                "title": (title_node.text or "").strip() if title_node is not None else "",
                "abstract": "\n\n".join(abstract_parts),
                "authors": authors,
                "year": year_int,
                "journal": (journal_node.text or "").strip()
                if journal_node is not None
                else "",
            }
        )
    return out


async def search_pubmed(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    """Run an esearch+efetch pair against PubMed.

    Returns a list of ``{pmid, title, abstract, authors, year, journal}`` dicts.
    Empty list on any error (logged as warning).
    """

    headers = {"User-Agent": USER_AGENT}
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=headers) as client:
            pmids = await _esearch(client, query, max_results)
            if not pmids:
                return []
            await asyncio.sleep(RATE_DELAY_S)
            xml_text = await _efetch(client, pmids)
        return _parse_articles(xml_text)
    except (httpx.HTTPError, RuntimeError) as err:
        log.warning("alembic.pubmed.search_failed", query=query, error=str(err))
        return []


async def get_paper_by_pmid(pmid: str) -> dict[str, Any] | None:
    """Fetch a single paper by PMID. Returns ``None`` if not found."""

    headers = {"User-Agent": USER_AGENT}
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=headers) as client:
            xml_text = await _efetch(client, [pmid])
    except httpx.HTTPError as err:
        log.warning("alembic.pubmed.fetch_failed", pmid=pmid, error=str(err))
        return None
    parsed = _parse_articles(xml_text)
    return parsed[0] if parsed else None
