"""Self-contained HTML / JSON report renderer for ``/api/folds/{id}/report.*``.

The HTML report is intentionally a *single file* — no external CSS / JS — so
it works offline, prints cleanly, and can be sent as a PDF attachment without
any conversion gymnastics. The styling mirrors the ALEMBIC LABS visual
language (black surface, plasma red accent, monospaced data) but tuned for
A4 print rather than the dark web UI.
"""

from __future__ import annotations

import html as _html
import json
from typing import Any

import markdown as md

from ..db.models import Fold


_REPORT_CSS = """
:root {
  color-scheme: light;
}
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-size: 14px;
  line-height: 1.55;
  color: #111;
  background: #fff;
  margin: 0;
  padding: 48px 56px;
  max-width: 820px;
  margin: 0 auto;
}
h1, h2, h3, h4 { font-weight: 700; letter-spacing: 0.01em; }
h1 { font-size: 28px; margin: 0 0 4px; text-transform: uppercase; }
h2 { font-size: 18px; margin: 32px 0 12px; text-transform: uppercase; border-bottom: 1px solid #ddd; padding-bottom: 6px; letter-spacing: 0.06em; }
h3 { font-size: 15px; margin: 18px 0 6px; text-transform: uppercase; color: #444; letter-spacing: 0.08em; }
p { margin: 0 0 12px; }
small, .meta { color: #777; font-size: 12px; }
.brand { color: #ef3a4d; font-weight: 700; }
.eyebrow {
  text-transform: uppercase; letter-spacing: 0.12em; font-size: 11px;
  color: #999; margin: 0 0 4px;
}
.hero {
  border: 1px solid #e3e3e3; padding: 18px 22px; margin: 18px 0 0;
  display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px;
  background: #fafafa;
}
.hero .cell .label {
  font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em;
  color: #888; margin: 0 0 4px;
}
.hero .cell .value { font-variant-numeric: tabular-nums; font-size: 15px; }
.hero .cell .big { font-size: 24px; font-weight: 700; color: #ef3a4d; }
.badges { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; }
.badge {
  border: 1px solid #ccc; padding: 2px 8px; font-size: 11px;
  text-transform: uppercase; letter-spacing: 0.08em; color: #555;
  border-radius: 2px;
}
pre.seq, code.seq {
  font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12px;
  background: #f4f4f4; padding: 10px 12px; overflow-x: auto;
  border-left: 2px solid #ef3a4d; white-space: pre-wrap; word-break: break-all;
}
.markdown h2, .markdown h3 { border: 0; padding: 0; }
.markdown ul { padding-left: 20px; margin: 8px 0 14px; }
.markdown li { margin: 3px 0; }
.markdown table { border-collapse: collapse; margin: 12px 0; font-size: 13px; }
.markdown th, .markdown td { border: 1px solid #ddd; padding: 6px 10px; text-align: left; }
.markdown th { background: #fafafa; }
.caveat-list { padding-left: 20px; }
.caveat-list li { color: #555; margin: 4px 0; }
.onchain {
  margin-top: 24px; padding: 12px 16px; border: 1px dashed #aaa;
  font-size: 12px; color: #555; word-break: break-all;
}
.onchain .label {
  text-transform: uppercase; letter-spacing: 0.12em; color: #999;
  font-size: 10px; margin-right: 6px;
}
footer {
  margin-top: 48px; padding-top: 16px; border-top: 1px solid #ddd;
  font-size: 11px; color: #888; text-align: center;
  text-transform: uppercase; letter-spacing: 0.12em;
}
@media print {
  body { padding: 24px; }
  .hero { background: transparent; }
}
""".strip()


def _esc(value: Any) -> str:
    """HTML-escape a value, returning ``—`` for None/empty."""
    if value is None or value == "":
        return "—"
    return _html.escape(str(value))


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "—"


def _fmt_num(value: float | None, *, digits: int = 3) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def _render_markdown(text: str | None) -> str:
    """Render the Communicator's markdown brief to HTML."""
    if not text:
        return "<p><em>no research brief recorded.</em></p>"
    return md.markdown(text, extensions=["extra", "tables", "sane_lists"])


def _safe_load(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def render_report_html(fold: Fold, *, explorer_url: str | None) -> str:
    """Build a self-contained HTML report for ``fold``."""

    caveats = _safe_load(fold.caveats) or []
    if not isinstance(caveats, list):
        caveats = [str(caveats)]

    works = _safe_load(fold.works_cited) or []
    if not isinstance(works, list):
        works = []

    title = (
        f"DISTILLATION №{fold.id} — {fold.peptide_name or 'unknown'} · "
        f"{fold.modification_description or '—'}"
    )

    badges_html = "".join(
        f"<span class='badge'>{_esc(label)}</span>"
        for label in [
            fold.fold_verdict,
            fold.peptide_class,
            fold.modification_description,
            fold.target_protein,
        ]
        if label
    )

    works_html = ""
    if works:
        rows = []
        for w in works[:25]:
            pmid = _esc(w.get("pmid"))
            ttl = _esc(w.get("title"))
            yr = _esc(w.get("year"))
            jrn = _esc(w.get("journal"))
            rows.append(
                f"<li><strong>PMID {pmid}</strong> ({yr}) "
                f"<em>{jrn}</em> — {ttl}</li>"
            )
        works_html = (
            "<h2>Citations</h2><ol class='caveat-list'>"
            + "".join(rows)
            + "</ol>"
        )

    onchain_html = ""
    if fold.onchain_signature:
        onchain_html = f"""
        <div class='onchain'>
          <div><span class='label'>solana signature</span>{_esc(fold.onchain_signature)}</div>
          <div><span class='label'>data sha-256</span>{_esc(fold.onchain_data_hash or fold.onchain_hash)}</div>
          <div><span class='label'>verify</span>{_esc(explorer_url or '—')}</div>
        </div>
        """

    caveats_html = ""
    if caveats:
        caveats_html = (
            "<h2>Caveats</h2><ul class='caveat-list'>"
            + "".join(f"<li>{_esc(c)}</li>" for c in caveats)
            + "</ul>"
        )

    seq_html = ""
    if fold.peptide_sequence or fold.modified_sequence:
        seq_html = f"""
        <h2>Sequences</h2>
        <h3>Native</h3>
        <pre class='seq'>{_esc(fold.peptide_sequence)}</pre>
        <h3>Modified</h3>
        <pre class='seq'>{_esc(fold.modified_sequence or fold.peptide_sequence)}</pre>
        """

    hero_html = f"""
    <div class='hero'>
      <div class='cell'>
        <div class='label'>Average confidence</div>
        <div class='value big'>{_fmt_pct(fold.confidence_plddt)}</div>
      </div>
      <div class='cell'>
        <div class='label'>pTM / ipTM</div>
        <div class='value'>{_fmt_num(fold.confidence_ptm, digits=3)} / {_fmt_num(fold.confidence_iptm, digits=3)}</div>
      </div>
      <div class='cell'>
        <div class='label'>Verdict</div>
        <div class='value'>{_esc(fold.fold_verdict or fold.status)}</div>
      </div>
      <div class='cell'>
        <div class='label'>Target</div>
        <div class='value'>{_esc(fold.target_protein)}</div>
      </div>
      <div class='cell'>
        <div class='label'>UniProt</div>
        <div class='value'>{_esc(fold.target_uniprot_id)}</div>
      </div>
      <div class='cell'>
        <div class='label'>Binding probability</div>
        <div class='value'>{_fmt_num(fold.binding_probability, digits=3)}</div>
      </div>
    </div>
    """

    body = f"""
    <p class='eyebrow'>distillation №{fold.id} · alembic labs</p>
    <h1>{_esc(fold.peptide_name)} <span class='brand'>—</span> {_esc(fold.modification_description)}</h1>
    <p class='meta'>generated {_esc(fold.created_at.isoformat() if fold.created_at else '—')}</p>
    <div class='badges'>{badges_html}</div>

    {hero_html}

    <h2>TLDR</h2>
    <p>{_esc(fold.ai_analysis_tldr)}</p>

    <h2>Executive summary</h2>
    <p>{_esc(fold.executive_summary)}</p>

    <h2>Detailed analysis</h2>
    <div class='markdown'>{_render_markdown(fold.ai_analysis_detailed)}</div>

    <h2>Research brief</h2>
    <div class='markdown'>{_render_markdown(fold.research_brief_markdown)}</div>

    {seq_html}
    {caveats_html}
    {works_html}
    {onchain_html}

    <footer>
      ALEMBIC LABS · in silico exploration · not medical advice ·
      alembic.bio/folds/{fold.id}
    </footer>
    """

    return f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'/>
  <meta name='viewport' content='width=device-width,initial-scale=1'/>
  <title>{_esc(title)}</title>
  <style>{_REPORT_CSS}</style>
</head>
<body>
{body}
</body>
</html>"""


def render_report_pdf(fold: Fold, *, explorer_url: str | None) -> bytes:
    """Render the same HTML report to a PDF byte string via WeasyPrint.

    Imported lazily so that the rest of the API still works in environments
    where the WeasyPrint native deps (Pango / Cairo) aren't installed — the
    /report.pdf route would 500, but /report.html and /report.json keep
    working unaffected.
    """

    from weasyprint import HTML  # local import — heavy native deps

    body = render_report_html(fold, explorer_url=explorer_url)
    return HTML(string=body).write_pdf()


def render_report_json(fold: Fold, *, explorer_url: str | None) -> dict[str, Any]:
    """Build the canonical JSON dump for the fold's downloadable bundle.

    Mirrors the ``/api/folds/{id}`` response shape but resolves all the JSON
    text columns and includes a couple of fields (``onchain_explorer_url``)
    that the standard endpoint already exposes — kept here so the file is
    self-contained when downloaded as ``fold-N.json``.
    """

    return {
        "id": fold.id,
        "slug": fold.slug,
        "title": fold.title,
        "status": fold.status,
        "fold_verdict": fold.fold_verdict,
        "peptide": {
            "name": fold.peptide_name,
            "class": fold.peptide_class,
            "sequence": fold.peptide_sequence,
            "modified_sequence": fold.modified_sequence,
            "modification_description": fold.modification_description,
        },
        "target": {
            "protein": fold.target_protein,
            "uniprot_id": fold.target_uniprot_id,
            "chembl_id": fold.target_chembl_id,
            "gene_symbol": fold.target_gene_symbol,
        },
        "rationale": {
            "hypothesis": fold.hypothesis,
            "rationale": fold.rationale,
            "predicted_outcome": fold.predicted_outcome,
            "mechanism_class": fold.mechanism_class,
            "biohacker_use": fold.biohacker_use,
        },
        "confidence": {
            "plddt": fold.confidence_plddt,
            "ptm": fold.confidence_ptm,
            "iptm": fold.confidence_iptm,
            "chai_agreement": fold.chai_agreement,
            "chai1_gated_decision": fold.chai1_gated_decision,
            "binding_probability": fold.binding_probability,
            "binding_pic50": fold.binding_pic50,
            "predicted_binding_change": fold.predicted_binding_change,
        },
        "profile": {
            "aggregation_propensity": fold.aggregation_propensity,
            "stability_score": fold.stability_score,
            "bbb_penetration_score": fold.bbb_penetration_score,
            "half_life_estimate": fold.half_life_estimate,
        },
        "narrative": {
            "tldr": fold.ai_analysis_tldr,
            "detailed_analysis": fold.ai_analysis_detailed,
            "executive_summary": fold.executive_summary,
            "tweet_draft": fold.tweet_draft,
            "research_brief_markdown": fold.research_brief_markdown,
            "structural_caption": fold.structural_caption,
            "key_findings_summary": fold.key_findings_summary,
        },
        "structured": {
            "known_activity": _safe_load(fold.known_activity),
            "known_binders": _safe_load(fold.known_binders),
            "candidate_variants": _safe_load(fold.candidate_variants),
            "domain_annotations": _safe_load(fold.domain_annotations),
            "literature_context": _safe_load(fold.literature_context),
            "caveats": _safe_load(fold.caveats),
            "works_cited": _safe_load(fold.works_cited),
        },
        "onchain": {
            "hash": fold.onchain_hash,
            "signature": fold.onchain_signature,
            "data_hash": fold.onchain_data_hash,
            "logged_at": fold.onchain_logged_at.isoformat()
            if fold.onchain_logged_at
            else None,
            "explorer_url": explorer_url,
        },
        "ipfs_hash": fold.ipfs_hash,
        "created_at": fold.created_at.isoformat() if fold.created_at else None,
        "updated_at": fold.updated_at.isoformat() if fold.updated_at else None,
    }
