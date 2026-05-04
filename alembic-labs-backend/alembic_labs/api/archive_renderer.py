"""ZIP archive of every publishable fold — served at /api/folds/archive.zip.

Bundles each fold's canonical artifacts (JSON dump, structure.pdb, standalone
HTML report) into a single deflate-compressed archive plus a top-level
README.md and INDEX.csv so a downstream researcher can clone, grep, and cite
the data without poking the API per-fold.

Per-fold PDFs are intentionally omitted — rendering 30+ WeasyPrint passes
in-process pushes us into Caddy's default 60s proxy budget. The HTML
report is self-contained and prints the same as the PDF, and individual
PDFs are still available at /api/folds/{id}/report.pdf for one-off needs.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from ..db.models import Fold
from .report_renderer import render_report_html, render_report_json


def _safe_slug(fold: Fold) -> str:
    """File-system safe folder name — ``0028-tb-500-lactam`` style."""
    if fold.slug:
        return f"{fold.id:04d}-{fold.slug.lstrip('0123456789-')}".rstrip("-")
    return f"fold-{fold.id:04d}"


def _build_readme(folds: list[Fold], generated_at: datetime) -> str:
    """README that ships at the root of the zip."""

    refined = sum(1 for f in folds if (f.fold_verdict or "").upper() == "REFINED")
    promising = sum(
        1 for f in folds if (f.fold_verdict or "").upper() == "PROMISING"
    )
    discarded = sum(
        1 for f in folds if (f.fold_verdict or "").upper() == "DISCARDED"
    )

    return f"""# ALEMBIC LABS — distillation archive

Generated: **{generated_at.isoformat(timespec="seconds")}**
Folds included: **{len(folds)}** (refined: {refined} · promising: {promising} · discarded: {discarded})

## What is this

A snapshot of every publishable fold produced by ALEMBIC LABS — an autonomous
in-silico peptide research lab. Each fold runs five Claude-powered agents
(Researcher → Literature → Clinical → Structural → Communicator) gated by an
adaptive Chai-1 cross-validation step on top of Boltz-2 for structure
prediction.

Verdict semantics:

- **REFINED** — high-confidence prediction that survived the structural gate;
  worth wet-lab follow-up.
- **PROMISING** — moderate signal, interesting but not a headline.
- **DISCARDED** — biologically uninformative or technical noise; published
  for transparency.
- *(PENDING / FAILED folds are excluded from this archive.)*

## Layout

```
folds/<id>-<slug>/
  fold.json       canonical payload (peptide, target, narrative, citations)
  structure.pdb   Boltz-2 (or Chai-1 cross-validated) atomic coordinates
  report.html     standalone, printable per-fold report (CSS inlined)
INDEX.csv         summary table — id, peptide, mod, verdict, pLDDT, signature, url
README.md         this file
```

## On-chain provenance

Every fold's SHA-256 (of its core data block) is committed to Solana mainnet
via the SPL Memo program. Look for the ``onchain.signature`` field in
``fold.json``; the ``onchain.explorer_url`` is a Solscan deep-link you can
verify in any wallet.

## Caveats

This is **in-silico exploration**. Predicted properties (binding probability,
pIC50, aggregation, BBB, half-life) are model outputs — not measured values.
Every fold's caveat list spells out tool-specific limitations. None of this
is medical advice.

## Citing

> ALEMBIC LABS, distillation archive snapshot, {generated_at.date().isoformat()}.
> Available at https://alembic.bio/folds.

## Live API

- per-fold detail: ``https://api.alembic.bio/api/folds/{{id}}``
- per-fold PDF report: ``https://api.alembic.bio/api/folds/{{id}}/report.pdf``
- per-fold raw structure: ``https://api.alembic.bio/api/folds/{{id}}/structure``
- this archive (always current): ``https://api.alembic.bio/api/folds/archive.zip``
- source code (MIT): https://github.com/alembic-labs/autonomous-ai-lab
"""


def _build_index_csv(folds: list[Fold]) -> str:
    """A flat CSV that opens in Excel / pandas without ceremony."""

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "slug",
            "peptide_name",
            "peptide_class",
            "modification",
            "target_protein",
            "target_uniprot",
            "verdict",
            "plddt",
            "ptm",
            "iptm",
            "binding_probability",
            "binding_pic50",
            "onchain_signature",
            "created_at",
            "url",
        ]
    )
    for f in folds:
        writer.writerow(
            [
                f.id,
                f.slug or "",
                f.peptide_name or "",
                f.peptide_class or "",
                f.modification_description or "",
                f.target_protein or "",
                f.target_uniprot_id or "",
                f.fold_verdict or "",
                f"{f.confidence_plddt:.4f}" if f.confidence_plddt is not None else "",
                f"{f.confidence_ptm:.4f}" if f.confidence_ptm is not None else "",
                f"{f.confidence_iptm:.4f}" if f.confidence_iptm is not None else "",
                f"{f.binding_probability:.4f}"
                if f.binding_probability is not None
                else "",
                f"{f.binding_pic50:.4f}" if f.binding_pic50 is not None else "",
                f.onchain_signature or "",
                f.created_at.isoformat() if f.created_at else "",
                f"https://alembic.bio/folds/{f.id}",
            ]
        )
    return buf.getvalue()


def build_folds_archive(
    folds: Iterable[Fold],
    *,
    explorer_url_for: Callable[[str | None], str | None],
) -> bytes:
    """Return a ZIP byte-string with all the per-fold artifacts."""

    folds = list(folds)
    generated_at = datetime.now(timezone.utc)

    buf = io.BytesIO()
    with zipfile.ZipFile(
        buf, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as zf:
        zf.writestr("README.md", _build_readme(folds, generated_at))
        zf.writestr("INDEX.csv", _build_index_csv(folds))

        for fold in folds:
            folder = f"folds/{_safe_slug(fold)}"
            explorer = explorer_url_for(fold.onchain_signature)

            payload = render_report_json(fold, explorer_url=explorer)
            zf.writestr(
                f"{folder}/fold.json",
                json.dumps(payload, indent=2, ensure_ascii=False),
            )

            if fold.pdb_file_path:
                pdb_path = Path(fold.pdb_file_path)
                if pdb_path.exists():
                    zf.writestr(
                        f"{folder}/structure.pdb",
                        pdb_path.read_text(encoding="utf-8"),
                    )

            zf.writestr(
                f"{folder}/report.html",
                render_report_html(fold, explorer_url=explorer),
            )

    return buf.getvalue()


def archive_filename(generated_at: datetime | None = None) -> str:
    """Stable filename — ``alembic-folds-20260504.zip``."""
    when = generated_at or datetime.now(timezone.utc)
    return f"alembic-folds-{when.strftime('%Y%m%d')}.zip"
