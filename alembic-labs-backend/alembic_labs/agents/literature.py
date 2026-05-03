"""Literature agent — synthesises PubMed + Europe PMC preprint evidence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import Fold
from ..logging_setup import get_logger
from ..tools import europepmc, pubmed
from .base import (
    call_claude,
    extract_json,
    log_agent_run,
    update_agent_status,
)

log = get_logger(__name__)

AGENT_NAME = "LITERATURE"

SYSTEM_PROMPT = """You are the LITERATURE agent of ALEMBIC LABS.

Role: Read scientific literature about a peptide and synthesize relevant findings for the research team.

You receive: peptide name, target, hypothesis, ~10-15 paper abstracts from PubMed and Europe PMC (which indexes PubMed + bioRxiv + medRxiv).

Output valid JSON:
{
  "key_findings_summary": "<3-5 paragraph synthesis of what the literature says about this peptide and target, with focus on the hypothesis>",
  "papers_used": [
    {
      "pmid_or_doi": "<PMID for PubMed, DOI for bioRxiv>",
      "title": "<paper title>",
      "year": <year>,
      "relevance": "<1-2 sentences why this paper is relevant to our hypothesis>"
    }
  ],
  "consensus_view": "<what does the literature consensus say about this peptide and modification approach?>",
  "knowledge_gaps": "<what's NOT well-studied that our prediction could illuminate?>",
  "supporting_evidence": "<evidence supporting our hypothesis>",
  "challenging_evidence": "<evidence that challenges or complicates our hypothesis>"
}

RULES:
- Be honest about literature quality (some papers may be weak)
- Distinguish established findings from preliminary/preprint
- Don't cherry-pick — include challenging evidence
- Cite specific findings, not vague summaries
- Performance peptides have less literature than disease — note when evidence is thin
"""


def _format_papers(papers: list[dict[str, Any]], source: str) -> str:
    """Compact rendering of paper abstracts for the prompt.

    ``source`` is one of ``pubmed`` / ``preprints``. Both shapes share the
    common fields ``pmid``, ``doi``, ``year``, ``title``, ``abstract``,
    ``authors`` (the Europe PMC client normalises into the PubMed shape).
    """
    out: list[str] = []
    for p in papers:
        pmid = p.get("pmid") or ""
        doi = p.get("doi") or ""
        ident = f"PMID:{pmid}" if pmid else f"DOI:{doi}"
        year = p.get("year") or ""
        authors = ", ".join((p.get("authors") or [])[:3])
        title = p.get("title") or ""
        abstract = (p.get("abstract") or "").strip()
        if len(abstract) > 1500:
            abstract = abstract[:1500] + "…"
        out.append(
            f"[{ident}] ({year}) {title}\n"
            f"  Authors: {authors}\n"
            f"  Abstract: {abstract or '—'}"
        )
    return "\n\n".join(out) if out else "(none returned)"


async def run_literature(db: AsyncSession, fold: Fold) -> dict[str, Any]:
    """Populate Literature-related fields on ``fold``."""

    started_at = datetime.now(timezone.utc)
    await update_agent_status(
        db,
        AGENT_NAME,
        "ACTIVE",
        current_task=f"Searching PubMed for {fold.peptide_name}",
        fold_id=fold.id,
    )

    error: str | None = None
    parsed: dict[str, Any] = {}
    try:
        peptide_query = fold.peptide_name or ""
        target_query = fold.target_protein or ""

        pm_primary = await pubmed.search_pubmed(peptide_query, max_results=8)
        pm_secondary: list[dict[str, Any]] = []
        if peptide_query and target_query:
            pm_secondary = await pubmed.search_pubmed(
                f"{peptide_query} {target_query}", max_results=4
            )

        await update_agent_status(
            db,
            AGENT_NAME,
            "ACTIVE",
            current_task="Searching Europe PMC preprints",
            fold_id=fold.id,
        )
        # Europe PMC's ranked search replaces the older bioRxiv client-side
        # filter. Single request, real relevance scoring, preprint-only filter.
        preprint_query_primary = peptide_query
        preprint_query_secondary = (
            f"{peptide_query} {target_query}"
            if peptide_query and target_query
            else ""
        )
        preprints_primary = await europepmc.search_preprints(
            preprint_query_primary, max_results=3
        )
        preprints_secondary: list[dict[str, Any]] = []
        if preprint_query_secondary:
            preprints_secondary = await europepmc.search_preprints(
                preprint_query_secondary, max_results=2
            )

        # De-duplicate by PMID/DOI.
        seen: set[str] = set()
        pm_papers: list[dict[str, Any]] = []
        for p in pm_primary + pm_secondary:
            key = p.get("pmid", "")
            if key and key not in seen:
                seen.add(key)
                pm_papers.append(p)

        seen_doi: set[str] = set()
        preprint_papers: list[dict[str, Any]] = []
        for p in preprints_primary + preprints_secondary:
            key = (p.get("doi") or p.get("pmid") or "").strip()
            if key and key not in seen_doi:
                seen_doi.add(key)
                preprint_papers.append(p)

        user_message = (
            f"Peptide: {fold.peptide_name}\n"
            f"Target: {fold.target_protein or '—'}\n"
            f"Hypothesis: {fold.hypothesis}\n"
            f"Modification: {fold.modification_description}\n\n"
            "PUBMED ABSTRACTS:\n"
            f"{_format_papers(pm_papers, 'pubmed')}\n\n"
            "PREPRINTS (bioRxiv / medRxiv via Europe PMC):\n"
            f"{_format_papers(preprint_papers, 'preprints')}\n\n"
            "Synthesise the literature into the JSON object specified in your system prompt."
        )

        completion = await call_claude(
            model=settings.LITERATURE_MODEL,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=4096,
            temperature=0.3,
        )
        raw = extract_json(completion["text"])
        if not isinstance(raw, dict):
            raise ValueError("expected JSON object from Literature")
        parsed = raw

        fold.literature_context = json.dumps(
            {
                "pubmed": pm_papers,
                # The DB column is keyed historically — keep "biorxiv" here so
                # any frontend or tool that reads ``literature_context.biorxiv``
                # keeps working. The actual source is Europe PMC preprints.
                "biorxiv": preprint_papers,
                "preprints": preprint_papers,
                "consensus_view": parsed.get("consensus_view"),
                "knowledge_gaps": parsed.get("knowledge_gaps"),
                "supporting_evidence": parsed.get("supporting_evidence"),
                "challenging_evidence": parsed.get("challenging_evidence"),
            }
        )
        fold.works_cited = json.dumps(parsed.get("papers_used") or [])
        fold.key_findings_summary = parsed.get("key_findings_summary")
        await db.commit()

        await log_agent_run(
            db,
            fold_id=fold.id,
            agent_name=AGENT_NAME,
            model=settings.LITERATURE_MODEL,
            summary=(
                f"{len(pm_papers)} PubMed + {len(preprint_papers)} preprints "
                "synthesised"
            ),
            input_tokens=completion["input_tokens"],
            output_tokens=completion["output_tokens"],
            cost_usd=completion.get("cost_usd"),
            status="COMPLETED",
            started_at=started_at,
        )
    except Exception as err:  # noqa: BLE001
        error = str(err)
        log.exception("alembic.literature.failed", error=error)
        await db.rollback()
        await log_agent_run(
            db,
            fold_id=fold.id,
            agent_name=AGENT_NAME,
            model=settings.LITERATURE_MODEL,
            summary=None,
            status="FAILED",
            error=error,
            started_at=started_at,
        )
        # Literature failure is non-fatal — orchestrator decides.
    finally:
        await update_agent_status(db, AGENT_NAME, "IDLE", current_task=None, fold_id=None)

    return parsed
