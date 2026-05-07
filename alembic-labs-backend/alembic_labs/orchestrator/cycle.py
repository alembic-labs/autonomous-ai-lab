"""End-to-end distillation cycle.

Pipeline:
1. Researcher (sequential — needed by everyone else)
2. Literature ‖ Clinical (parallel via asyncio.gather)
3. Structural (after researcher)
4. Communicator (after structural + lit + clinical)

Failure policy:
- Researcher failure → fold marked FAILED, cycle aborted.
- Structural failure → fold marked FAILED, cycle aborted.
- Literature / Clinical / Communicator failures are tolerated; the fold is
  saved with whatever data was produced and Communicator is still attempted.
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone

from ..agents import clinical, communicator, literature, researcher, structural
from ..config import settings
from ..db.models import Fold, LabStat
from ..db.session import SessionLocal
from ..logging_setup import get_logger
from ..tools import solana_logger
from ..tools.structural_limits import target_is_predictable

log = get_logger(__name__)

# Verdicts/statuses that warrant an on-chain commitment. We deliberately log
# DISCARDED folds too — being honest about negative results in public is the
# whole point of the lab. We skip FAILED (technical failure, no real signal)
# and PENDING (unfinished) so we don't pollute the chain with noise.
_ONCHAIN_ELIGIBLE_STATUSES: frozenset[str] = frozenset(
    {"REFINED", "PROMISING", "DISCARDED"}
)


async def _create_fold(session) -> Fold:
    fold = Fold(status="PENDING")
    session.add(fold)
    await session.commit()
    await session.refresh(fold)
    return fold


async def _mark_failed(session, fold_id: int | None, reason: str) -> None:
    """Mark a fold as failed.

    Takes the fold ``id`` as a plain int (cached by the caller) so we never
    touch a possibly-expired ORM attribute after the original error. The old
    implementation read ``fold.id`` here, which triggered SQLAlchemy lazy-
    load on a broken async session and raised ``MissingGreenlet`` — masking
    the real error and leaving the row stuck in PENDING.
    """
    try:
        await session.rollback()
    except Exception:  # noqa: BLE001
        pass
    if not fold_id:
        return
    try:
        async with SessionLocal() as fresh:
            target = await fresh.get(Fold, fold_id)
            if target is None:
                return
            target.status = "FAILED"
            if not target.title:
                target.title = "Cycle failed"
            if not target.result_summary:
                target.result_summary = reason[:500]
            await fresh.commit()
    except Exception as err:  # noqa: BLE001
        log.warning(
            "alembic.cycle.mark_failed_failed", fold_id=fold_id, error=str(err)
        )


_SLUG_TRIM_RE = re.compile(r"[^a-z0-9]+")


def build_fold_slug(fold: Fold) -> str:
    """Derive a stable, SEO-friendly slug for a fold.

    Format: ``{id}-{peptide}-{modification}``, lowercased, ASCII-only, dashes,
    capped at 150 chars. Falls back to ``{id}-fold`` when no peptide name is
    known yet (e.g. on a Researcher failure).
    """
    parts: list[str] = [str(fold.id)]
    if fold.peptide_name:
        parts.append(_SLUG_TRIM_RE.sub("-", fold.peptide_name.lower()).strip("-"))
    if fold.modification_description:
        # Compact mod description to avoid noisy URLs; cap each token.
        mod = _SLUG_TRIM_RE.sub("-", fold.modification_description.lower()).strip("-")
        if mod:
            parts.append(mod[:60])
    if len(parts) == 1:
        parts.append("fold")
    slug = "-".join(parts)
    return slug[:150]


async def _ensure_slug(session, fold: Fold) -> None:
    if fold.slug:
        return
    fold.slug = build_fold_slug(fold)
    await session.commit()


async def _update_avg_cycle_seconds(session, elapsed: float) -> None:
    stats = await session.get(LabStat, 1)
    if stats is None:
        return
    n = max(stats.total_cycles or 0, 1)
    prev = stats.avg_cycle_seconds or 0.0
    # Running average without storing all samples.
    stats.avg_cycle_seconds = round(prev + (elapsed - prev) / n, 2)
    stats.updated_at = datetime.now(timezone.utc)
    await session.commit()


async def _log_onchain(session, fold: Fold) -> None:
    """Commit the fold hash to Solana and persist the resulting signature.

    Runs only if Solana logging is enabled and the fold reached a terminal
    "scientific" status (REFINED / PROMISING / DISCARDED). Skips folds that
    already have a signature so re-running the cycle is idempotent. Failures
    are swallowed by the logger — we never block the orchestrator on RPC
    weather or unfunded keypairs.
    """
    if not settings.solana_ready:
        return
    if fold.status not in _ONCHAIN_ELIGIBLE_STATUSES:
        return
    if fold.onchain_signature:
        return  # idempotent — don't double-log on cycle retries

    payload = {
        "id": fold.id,
        "peptide_name": fold.peptide_name,
        "peptide_sequence": fold.peptide_sequence,
        "modification_description": fold.modification_description,
        "modified_sequence": fold.modified_sequence,
        "target_protein": fold.target_protein,
        "target_uniprot_id": fold.target_uniprot_id,
        "fold_verdict": fold.fold_verdict,
        "confidence_plddt": fold.confidence_plddt,
        "confidence_ptm": fold.confidence_ptm,
        "confidence_iptm": fold.confidence_iptm,
        "created_at": fold.created_at,
    }
    result = await solana_logger.log_fold_onchain(payload)
    if not result:
        return
    fold.onchain_signature = result["signature"]
    fold.onchain_data_hash = result["hash"]
    fold.onchain_logged_at = datetime.now(timezone.utc)
    # Mirror into the legacy ``onchain_hash`` column so older API consumers
    # (and the existing fold detail page) keep working unchanged.
    if not fold.onchain_hash:
        fold.onchain_hash = result["signature"]
    await session.commit()

    stats = await session.get(LabStat, 1)
    if stats is not None:
        stats.total_onchain_logged = (stats.total_onchain_logged or 0) + 1
        stats.updated_at = datetime.now(timezone.utc)
        await session.commit()


async def _bump_chai1_counters(session, decision: str | None) -> None:
    """Increment the LabStat Chai-1 telemetry based on the gating decision.

    DISABLED is intentionally not counted — it represents folds where the
    adaptive logic isn't even applicable (no creds, no target sequence) and
    including them would distort the "X / Y folds" ratio shown on /lab.
    """
    if not decision:
        return
    stats = await session.get(LabStat, 1)
    if stats is None:
        return
    if decision in {"RAN_BORDERLINE", "RAN_FORCED"}:
        stats.total_chai1_runs = (stats.total_chai1_runs or 0) + 1
    elif decision in {"SKIPPED_HIGH_CONFIDENCE", "SKIPPED_LOW_CONFIDENCE"}:
        stats.total_chai1_skipped = (stats.total_chai1_skipped or 0) + 1
    else:
        return
    stats.updated_at = datetime.now(timezone.utc)
    await session.commit()


async def run_distillation_cycle() -> Fold | None:
    """Run one end-to-end research cycle. Returns the persisted fold (or None)."""

    started = time.monotonic()
    log.info("alembic.cycle.start")

    async with SessionLocal() as session:
        fold = await _create_fold(session)
        # Cache the int id eagerly. After a downstream error the ORM attribute
        # may be expired and reading it would trigger an async lazy-load on a
        # broken session (MissingGreenlet).
        fold_id = fold.id
        cycle_log = log.bind(fold_id=fold_id)
        cycle_log.info("alembic.cycle.fold_created")

        # 1. RESEARCHER — fatal on failure.
        try:
            t0 = time.monotonic()
            await researcher.run_researcher(session, fold)
            cycle_log.info(
                "alembic.cycle.researcher.done",
                seconds=round(time.monotonic() - t0, 2),
            )
        except Exception as err:  # noqa: BLE001
            cycle_log.warning("alembic.cycle.researcher.failed", error=str(err))
            await _mark_failed(session, fold_id, f"researcher: {err}")
            return fold

        # 2. LITERATURE ‖ CLINICAL — non-fatal.
        t0 = time.monotonic()
        lit_task = asyncio.create_task(literature.run_literature(session, fold))
        clin_task = asyncio.create_task(clinical.run_clinical(session, fold))
        await asyncio.gather(lit_task, clin_task, return_exceptions=True)
        cycle_log.info(
            "alembic.cycle.lit_clin.done",
            seconds=round(time.monotonic() - t0, 2),
        )

        # 2.5. PREDICTABILITY GATE — refuse folds Boltz-2/Chai-1 cannot
        # adjudicate (lipid targets, missing UniProt, sub-resolution
        # peptides) BEFORE we burn the structural budget on them. Folds
        # that hit the gate skip Structural entirely and go straight to
        # the Communicator (which renders the DISCARDED tool-limit
        # template). Saves ~$1.50-2.00 per refused fold.
        ok, reason = target_is_predictable(
            target_protein=fold.target_protein,
            target_uniprot=fold.target_uniprot_id,
            modification=fold.modification_description,
        )
        gate_skipped_structural = False
        if not ok:
            cycle_log.warning(
                "alembic.cycle.predictability_gate.blocked",
                reason=reason,
            )
            fold.fold_verdict = "DISCARDED"
            fold.status = "DISCARDED"
            fold.discard_reason = f"target_not_predictable: {reason}"
            # Surface a placeholder structural caption so the report has
            # *something* to render in the structure section even though
            # we never actually ran Boltz-2.
            if not fold.structural_caption:
                fold.structural_caption = (
                    "Structure prediction was not attempted — the orchestrator's "
                    "predictability gate refused this fold (see discard_reason)."
                )
            await session.commit()
            gate_skipped_structural = True

        # 3. STRUCTURAL — fatal on failure (skipped if gated).
        if not gate_skipped_structural:
            try:
                t0 = time.monotonic()
                await structural.run_structural(session, fold)
                cycle_log.info(
                    "alembic.cycle.structural.done",
                    seconds=round(time.monotonic() - t0, 2),
                    chai1_decision=fold.chai1_gated_decision,
                )
                await _bump_chai1_counters(session, fold.chai1_gated_decision)
            except Exception as err:  # noqa: BLE001
                cycle_log.warning(
                    "alembic.cycle.structural.failed", error=str(err)
                )
                await _mark_failed(session, fold_id, f"structural: {err}")
                return fold

        # 4. COMMUNICATOR — non-fatal (fold has useful data without it).
        communicator_failed = False
        try:
            t0 = time.monotonic()
            await communicator.run_communicator(session, fold)
            cycle_log.info(
                "alembic.cycle.communicator.done",
                seconds=round(time.monotonic() - t0, 2),
            )
        except Exception as err:  # noqa: BLE001
            cycle_log.warning("alembic.cycle.communicator.failed", error=str(err))
            communicator_failed = True

        # Communicator's internal handler rolls back the session on failure,
        # which expires every loaded ORM attribute on ``fold``. The slug /
        # on-chain / stats steps that follow would then trigger an async
        # lazy-load on the broken session and raise MissingGreenlet,
        # masking the real Communicator error. When this happens, run the
        # rest of the cycle in a *fresh* session against a re-fetched fold
        # so the cycle still produces a slug + on-chain commit.
        if communicator_failed:
            async with SessionLocal() as recover:
                recovered = await recover.get(Fold, fold_id)
                if recovered is None:
                    cycle_log.warning(
                        "alembic.cycle.fold_disappeared", fold_id=fold_id
                    )
                    return None
                if not recovered.status or recovered.status == "PENDING":
                    recovered.status = "PENDING"
                    await recover.commit()
                await _ensure_slug(recover, recovered)
                try:
                    await _log_onchain(recover, recovered)
                except Exception as err:  # noqa: BLE001
                    cycle_log.warning(
                        "alembic.cycle.onchain.failed", error=str(err)
                    )
                elapsed = time.monotonic() - started
                await _update_avg_cycle_seconds(recover, elapsed)
                cycle_log.info(
                    "alembic.cycle.done",
                    status=recovered.status,
                    seconds=round(elapsed, 2),
                )
                return recovered

        await _ensure_slug(session, fold)

        # 5. ON-CHAIN — best-effort SHA-256 commit to Solana via SPL Memo.
        # Runs after the slug exists so the published commitment can include
        # a stable URL slug for verification. Failures are silent.
        try:
            await _log_onchain(session, fold)
        except Exception as err:  # noqa: BLE001
            cycle_log.warning("alembic.cycle.onchain.failed", error=str(err))

        elapsed = time.monotonic() - started
        await _update_avg_cycle_seconds(session, elapsed)
        cycle_log.info(
            "alembic.cycle.done",
            status=fold.status,
            seconds=round(elapsed, 2),
        )
        return fold
