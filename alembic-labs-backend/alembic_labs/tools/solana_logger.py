"""Solana on-chain logging for completed folds.

Every REFINED / DISCARDED / PROMISING fold gets a SHA-256 hash of its core
scientific data (peptide, modification, target, verdict, confidence) committed
to Solana through the SPL Memo program. The transaction signature is stored on
the fold and exposed in the UI as a Solscan link — anyone can verify that the
data we publish today matches what was committed at the on-chain timestamp.

Design notes:
- The hash payload is **deterministic**: keys sorted, datetimes ISO-formatted.
  Re-running ``compute_fold_hash`` with the same inputs produces the same
  hex digest, which is what makes "tamper-evident" a meaningful claim.
- Failure handling is **non-fatal by default** (``SOLANA_FAILURE_NON_FATAL``).
  If the RPC is flaky, the keypair is unfunded, or the network rejects the
  transaction, we log a warning and return ``None`` so the orchestrator
  publishes the fold anyway. The user can backfill later by reading the
  hash off the DB and re-submitting.
- The ``solders`` API churns between minor versions; this file is written
  against ``solders==0.23.0`` + ``solana==0.36.6``. Pin those versions in
  requirements.txt — bumping them without re-checking the ``Transaction(...)``
  / ``Message.new_with_blockhash(...)`` call shapes will break this module.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime
from typing import Any

from ..config import settings
from ..logging_setup import get_logger

log = get_logger(__name__)

# SPL Memo v2 program id — public, well-known, deployed on mainnet & devnet.
# Documented at https://spl.solana.com/memo. Memo bytes are stored verbatim
# in the transaction log and can be queried via any RPC by signature.
MEMO_PROGRAM_ID_STR = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"

# Soft cap for the memo body. Real on-chain limit is ~566 bytes; we keep ours
# well under so a long verdict string never breaks the transaction.
_MEMO_MAX_BYTES = 240


def compute_fold_hash(fold_data: dict[str, Any]) -> str:
    """Deterministic SHA-256 of a fold's core scientific data.

    Only fields that meaningfully change the result are included — agent
    timing, token counts, slug, etc. are excluded so a re-render of the same
    scientific claim produces the same hash. ``created_at`` IS included to
    bind the commitment to a specific cycle.
    """
    created = fold_data.get("created_at")
    payload = json.dumps(
        {
            "lab": "ALEMBIC LABS",
            "fold_id": fold_data.get("id"),
            "peptide_name": fold_data.get("peptide_name"),
            "peptide_sequence": fold_data.get("peptide_sequence"),
            "modification": fold_data.get("modification_description"),
            "modified_sequence": fold_data.get("modified_sequence"),
            "target_protein": fold_data.get("target_protein"),
            "target_uniprot_id": fold_data.get("target_uniprot_id"),
            "verdict": fold_data.get("fold_verdict"),
            "plddt": fold_data.get("confidence_plddt"),
            "ptm": fold_data.get("confidence_ptm"),
            "iptm": fold_data.get("confidence_iptm"),
            "created_at": (
                created.isoformat() if isinstance(created, datetime) else created
            ),
        },
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_memo_text(fold_id: int | None, verdict: str | None, fold_hash: str) -> str:
    """Human-skimmable memo body. Format: ``ALEMBIC#<id>|<VERDICT>|<hash[:32]>``."""
    safe_verdict = (verdict or "?").upper()[:16]
    short = fold_hash[:32]
    body = f"ALEMBIC#{fold_id or '?'}|{safe_verdict}|{short}"
    encoded = body.encode("utf-8")
    if len(encoded) > _MEMO_MAX_BYTES:
        body = body[:_MEMO_MAX_BYTES]
    return body


async def log_fold_onchain(fold_data: dict[str, Any]) -> dict[str, Any] | None:
    """Commit the fold hash to Solana via the SPL Memo program.

    Returns ``{signature, hash, memo_text}`` on success, ``None`` when:
    - on-chain logging is disabled,
    - no keypair is configured,
    - or any error occurred and ``SOLANA_FAILURE_NON_FATAL`` is true.

    Raises only if ``SOLANA_FAILURE_NON_FATAL`` is false (test mode).
    """
    if not settings.solana_ready:
        return None

    fold_id = fold_data.get("id")
    fold_hash = compute_fold_hash(fold_data)
    memo_text = build_memo_text(fold_id, fold_data.get("fold_verdict"), fold_hash)

    # Imports are local so a missing solana / solders install doesn't break
    # the rest of the codebase at import time. The orchestrator only calls
    # this function when ``solana_ready`` is true.
    try:
        from solana.rpc.async_api import AsyncClient
        from solders.instruction import Instruction
        from solders.keypair import Keypair
        from solders.message import Message
        from solders.pubkey import Pubkey
        from solders.transaction import Transaction
    except ImportError as imp_err:  # noqa: BLE001
        log.warning("alembic.onchain.import_failed", error=str(imp_err))
        if not settings.SOLANA_FAILURE_NON_FATAL:
            raise
        return None

    client: Any | None = None
    try:
        client = AsyncClient(settings.SOLANA_RPC_URL)
        keypair = Keypair.from_base58_string(settings.SOLANA_KEYPAIR_BASE58)

        memo_ix = Instruction(
            program_id=Pubkey.from_string(MEMO_PROGRAM_ID_STR),
            accounts=[],
            data=memo_text.encode("utf-8"),
        )

        recent = await client.get_latest_blockhash()
        blockhash = recent.value.blockhash
        message = Message.new_with_blockhash(
            [memo_ix],
            keypair.pubkey(),
            blockhash,
        )
        tx = Transaction([keypair], message, blockhash)

        send_result = await client.send_transaction(tx)
        signature = str(send_result.value)

        # Best-effort confirmation. Don't block the cycle longer than 30s.
        try:
            await asyncio.wait_for(
                client.confirm_transaction(send_result.value, "confirmed"),
                timeout=30,
            )
            confirmed = True
        except asyncio.TimeoutError:
            confirmed = False
            log.warning(
                "alembic.onchain.confirm_timeout",
                fold_id=fold_id,
                signature=signature,
            )

        log.info(
            "alembic.onchain.logged",
            fold_id=fold_id,
            signature=signature,
            hash_prefix=fold_hash[:16],
            confirmed=confirmed,
            network=settings.SOLANA_NETWORK,
        )
        return {
            "signature": signature,
            "hash": fold_hash,
            "memo_text": memo_text,
            "confirmed": confirmed,
        }
    except Exception as err:  # noqa: BLE001
        log.warning(
            "alembic.onchain.failed",
            fold_id=fold_id,
            error=str(err)[:240],
        )
        if not settings.SOLANA_FAILURE_NON_FATAL:
            raise
        return None
    finally:
        if client is not None:
            try:
                await client.close()
            except Exception:  # noqa: BLE001
                # AsyncClient.close() is normally safe but guard against
                # already-closed sessions when the RPC errored mid-flight.
                pass


def explorer_url_for(signature: str | None) -> str | None:
    """Build the Solscan link for ``signature`` on the active network."""
    if not signature:
        return None
    return settings.solana_explorer_base.format(sig=signature)
