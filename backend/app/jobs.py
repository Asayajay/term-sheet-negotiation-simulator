"""Runs a single negotiation in a background thread (the Anthropic SDK call
is synchronous) and fans out round-by-round events to any websocket/SSE
subscribers for that negotiation ID, then persists the final result."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import Any

from app.database import SessionLocal
from app.engine import RoundResult, run_negotiation
from app.models import Negotiation, Round

logger = logging.getLogger(__name__)

_subscribers: dict[str, list[asyncio.Queue]] = {}


def subscribe(negotiation_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(negotiation_id, []).append(q)
    return q


def unsubscribe(negotiation_id: str, q: asyncio.Queue) -> None:
    subs = _subscribers.get(negotiation_id, [])
    if q in subs:
        subs.remove(q)


def _publish_threadsafe(loop: asyncio.AbstractEventLoop, negotiation_id: str, event: dict[str, Any]) -> None:
    def _do_publish() -> None:
        for q in list(_subscribers.get(negotiation_id, [])):
            q.put_nowait(event)

    loop.call_soon_threadsafe(_do_publish)


def _final_terms_summary(final_terms: dict[str, Any] | None) -> dict[str, Any]:
    if not final_terms:
        return {}
    return {
        "final_valuation": final_terms.get("pre_money_valuation_usd"),
        "final_equity_pct": final_terms.get("equity_percentage"),
        "final_liquidation_multiple": final_terms.get("liquidation_preference_multiple"),
        "final_liquidation_participating": final_terms.get("liquidation_participating"),
    }


def _run_and_persist(negotiation_id: str, loop: asyncio.AbstractEventLoop, params: dict[str, Any]) -> None:
    def on_round(r: RoundResult) -> None:
        db = SessionLocal()
        try:
            row = Round(
                negotiation_id=negotiation_id,
                sequence=r.sequence,
                round_number=r.round_number,
                actor=r.actor,
                action=r.action,
                terms=r.terms,
                reasoning=r.reasoning,
                diff=r.diff,
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                cache_read_tokens=r.cache_read_tokens,
                cost_usd=r.cost_usd,
            )
            db.add(row)
            db.commit()
        finally:
            db.close()
        event = {"type": "round", **asdict(r)}
        event["created_at"] = None  # set client-side; DB timestamp isn't available yet here
        _publish_threadsafe(loop, negotiation_id, event)

    db = SessionLocal()
    try:
        neg = db.get(Negotiation, negotiation_id)
        neg.status = "running"
        db.commit()

        result = run_negotiation(
            model=params["model"],
            max_rounds=params["max_rounds"],
            founder_params=params["founder_params"],
            vc_params=params["vc_params"],
            mock_mode=params["mock_mode"],
            api_key=params.get("api_key"),
            seed=params.get("seed"),
            on_round=on_round,
        )

        neg = db.get(Negotiation, negotiation_id)
        neg.status = "failed" if result.outcome == "error" else "completed"
        neg.outcome = result.outcome
        neg.final_terms = result.final_terms
        summary = _final_terms_summary(result.final_terms)
        neg.final_valuation = summary.get("final_valuation")
        neg.final_equity_pct = summary.get("final_equity_pct")
        neg.final_liquidation_multiple = summary.get("final_liquidation_multiple")
        neg.final_liquidation_participating = summary.get("final_liquidation_participating")
        neg.rounds_to_close = result.rounds_to_close
        neg.total_input_tokens = result.total_input_tokens
        neg.total_output_tokens = result.total_output_tokens
        neg.total_cost_usd = result.total_cost_usd
        neg.error = result.error
        from datetime import datetime, timezone

        neg.completed_at = datetime.now(timezone.utc)
        db.commit()

        _publish_threadsafe(
            loop,
            negotiation_id,
            {"type": "done", "outcome": result.outcome, "total_cost_usd": result.total_cost_usd, "error": result.error},
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("negotiation %s crashed", negotiation_id)
        db2 = SessionLocal()
        try:
            neg = db2.get(Negotiation, negotiation_id)
            if neg:
                neg.status = "failed"
                neg.outcome = "error"
                neg.error = str(exc)
                db2.commit()
        finally:
            db2.close()
        _publish_threadsafe(loop, negotiation_id, {"type": "done", "outcome": "error", "error": str(exc)})
    finally:
        db.close()


async def start_negotiation_job(negotiation_id: str, params: dict[str, Any]) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _run_and_persist, negotiation_id, loop, params)
