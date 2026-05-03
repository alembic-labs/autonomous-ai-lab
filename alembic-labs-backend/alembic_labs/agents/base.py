"""Shared utilities for the five agents.

Goals:
- One Anthropic client across all agents (avoid socket churn).
- A consistent ``call_claude`` shape that returns text + token counts + cost.
- Structured logging on every agent run.
- Resilient JSON extraction — Claude routinely wraps JSON in markdown fences.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import AgentRun, AgentStatus
from ..logging_setup import get_logger

log = get_logger(__name__)


# Anthropic list price per 1M tokens. Numbers track the public pricing page;
# the table is intentionally short — we only run on the five models below.
# Update these whenever Anthropic publishes new pricing.
ANTHROPIC_PRICES_PER_M: dict[str, dict[str, float]] = {
    # Opus class
    "claude-opus-4-7": {"input": 15.00, "output": 75.00},
    "claude-opus-4-1": {"input": 15.00, "output": 75.00},
    "claude-opus-4": {"input": 15.00, "output": 75.00},
    # Sonnet class
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
    # Haiku class
    "claude-haiku-4-5": {"input": 0.80, "output": 4.00},
}


def _model_price(model: str) -> dict[str, float]:
    """Lookup with a sane fallback so unknown models don't break the loop."""
    if model in ANTHROPIC_PRICES_PER_M:
        return ANTHROPIC_PRICES_PER_M[model]
    # Best-effort prefix match (e.g. ``claude-opus-4-7-20250101``).
    for known, price in ANTHROPIC_PRICES_PER_M.items():
        if model.startswith(known):
            return price
    return {"input": 0.0, "output": 0.0}


def estimate_cost_usd(model: str, input_tokens: int | None, output_tokens: int | None) -> float:
    """Return the predicted USD cost for a Claude call.

    Tokens are accepted as ``None`` because the Anthropic SDK doesn't always
    populate them on errors — we fall back to 0 in that case.
    """
    if not input_tokens and not output_tokens:
        return 0.0
    price = _model_price(model)
    cost = ((input_tokens or 0) / 1_000_000) * price["input"]
    cost += ((output_tokens or 0) / 1_000_000) * price["output"]
    return round(cost, 6)


def _build_client() -> AsyncAnthropic:
    """Build the Anthropic client lazily so tests can run without a real key."""
    return AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY or "missing")


client: AsyncAnthropic = _build_client()


async def call_claude(
    *,
    model: str,
    system: str,
    messages: list[dict[str, Any]],
    max_tokens: int = 4096,
    temperature: float = 0.4,
) -> dict[str, Any]:
    """Wrap ``messages.create`` with consistent shape.

    Returns ``{text, input_tokens, output_tokens, model, raw}``.
    Re-raises Anthropic errors so the orchestrator can mark the cycle as failed.
    """

    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    create_kwargs: dict[str, Any] = {
        "model": model,
        "system": system,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if temperature is not None and not _NO_TEMPERATURE_RE.match(model):
        create_kwargs["temperature"] = temperature

    response = await client.messages.create(**create_kwargs)

    # Claude returns content as a list of blocks; we want the concatenated text.
    text_parts: list[str] = []
    for block in response.content:
        # Type-safe access regardless of SDK version.
        block_text = getattr(block, "text", None)
        if isinstance(block_text, str):
            text_parts.append(block_text)
    text = "\n".join(text_parts).strip()

    usage = getattr(response, "usage", None)
    in_tok = getattr(usage, "input_tokens", None) if usage else None
    out_tok = getattr(usage, "output_tokens", None) if usage else None
    return {
        "text": text,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost_usd": estimate_cost_usd(model, in_tok, out_tok),
        "model": model,
        "raw": response,
    }


_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)
_OBJECT_RE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)

# Anthropic deprecated the `temperature` parameter for the 4.x model line and
# beyond. Older agents in this codebase still pass values like 0.2/0.7 — we
# silently drop them for these models so the API doesn't 400.
_NO_TEMPERATURE_RE = re.compile(
    r"^claude-(opus|sonnet|haiku)-(?:[4-9]|\d{2,})", re.IGNORECASE
)


_JSON_DECODER = json.JSONDecoder()


def _scan_for_balanced_json(text: str) -> dict[str, Any] | list[Any] | None:
    """Walk the text and try to JSON-decode at every `{`/`[` until something works."""
    for i, ch in enumerate(text):
        if ch not in "{[":
            continue
        try:
            obj, _ = _JSON_DECODER.raw_decode(text, i)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, (dict, list)):
            return obj
    return None


def extract_json(text: str) -> dict[str, Any] | list[Any]:
    """Pull JSON out of a Claude response.

    Handles four common cases:
    1. Plain JSON object/array.
    2. JSON wrapped in ```json ... ``` fences.
    3. JSON embedded in prose / after reasoning preamble.
    4. JSON when the model emitted multiple objects or trailing commentary.
    """

    if not text or not text.strip():
        raise ValueError("empty response from model")

    stripped = text.strip()
    if stripped[:1] in {"{", "["}:
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    fence_match = _FENCE_RE.search(text)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    scanned = _scan_for_balanced_json(text)
    if scanned is not None:
        return scanned

    obj_match = _OBJECT_RE.search(text)
    if obj_match:
        candidate = obj_match.group(1)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as err:
            raise ValueError(f"could not parse JSON from response: {err}") from err

    raise ValueError("no JSON object found in response")


async def update_agent_status(
    db: AsyncSession,
    agent_name: str,
    status: str,
    *,
    current_task: str | None = None,
    fold_id: int | None = None,
) -> None:
    """Upsert the AgentStatus row and commit immediately.

    The frontend polls /api/agents/status frequently — keeping this commit
    quick gives the UI live feedback during long-running cycles.
    """

    row = await db.get(AgentStatus, agent_name)
    now = datetime.now(timezone.utc)
    if row is None:
        row = AgentStatus(agent_name=agent_name)
        db.add(row)
    row.status = status
    row.current_task = current_task
    row.current_fold_id = fold_id
    row.last_active_at = now
    row.updated_at = now
    await db.commit()


async def log_agent_run(
    db: AsyncSession,
    *,
    fold_id: int,
    agent_name: str,
    model: str,
    summary: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
    status: str = "COMPLETED",
    error: str | None = None,
    started_at: datetime | None = None,
    tags: list[str] | None = None,
) -> AgentRun:
    """Record an AgentRun row and commit.

    Returns the persisted row so callers can compute timing externally.
    Cost is estimated on the fly from ``model + tokens`` if not supplied
    explicitly, so older callers that don't know about pricing keep working.
    """

    finished_at = datetime.now(timezone.utc)
    if cost_usd is None and (input_tokens or output_tokens):
        cost_usd = estimate_cost_usd(model, input_tokens, output_tokens)
    run = AgentRun(
        fold_id=fold_id,
        agent_name=agent_name,
        started_at=started_at or finished_at,
        finished_at=finished_at,
        status=status,
        model_used=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        summary=summary,
        error=error,
        tags=json.dumps(tags) if tags else None,
    )
    db.add(run)
    await db.commit()
    return run


async def list_agent_status(db: AsyncSession) -> list[AgentStatus]:
    """Fetch all five rows in stable order."""
    return list((await db.execute(select(AgentStatus))).scalars().all())
