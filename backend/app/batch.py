"""Batch runner: generates N scenarios, enforces cost caps, and runs each
negotiation to completion, persisting results. Used by both the CLI script
(scripts/run_batch.py, with an interactive confirm prompt) and the API's
/batch endpoint (with an explicit confirm=true flag instead of a TTY prompt)."""
from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from app.cost import estimate_batch_cost_usd
from app.database import SessionLocal
from app.engine import NegotiationResult, run_negotiation
from app.limits import validate_batch_size, validate_max_rounds, validate_model
from app.models import Negotiation
from app.personas import random_founder_params, random_vc_params

ProgressCallback = Callable[[int, int, NegotiationResult], None]


@dataclass
class BatchEstimate:
    batch_size: int
    max_rounds: int
    model: str
    estimated_cost_usd: float


def estimate_batch(model: str, max_rounds: int, size: int) -> BatchEstimate:
    return BatchEstimate(
        batch_size=size,
        max_rounds=max_rounds,
        model=model,
        estimated_cost_usd=round(estimate_batch_cost_usd(model, max_rounds, size), 4),
    )


def _build_scenario(overrides: dict[str, Any] | None, rng: random.Random) -> tuple[dict, dict]:
    founder = random_founder_params(rng)
    vc = random_vc_params(rng)
    if overrides:
        founder.update(overrides.get("founder") or {})
        vc.update(overrides.get("vc") or {})
    return founder, vc


def run_batch(
    *,
    size: int,
    model: str,
    max_rounds: int,
    mock_mode: bool = False,
    override_caps: bool = False,
    api_key: str | None = None,
    scenario_overrides: dict[str, Any] | None = None,
    seed: int | None = None,
    batch_id: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> str:
    """Runs the whole batch synchronously and returns the batch_id. Caller
    is responsible for having already confirmed the cost estimate. Pass an
    explicit batch_id if the caller needs to know it before the run starts
    (e.g. to return it to an HTTP client immediately)."""
    validate_model(model)
    validate_max_rounds(max_rounds, override_caps)
    validate_batch_size(size, override_caps)

    batch_id = batch_id or uuid.uuid4().hex
    rng = random.Random(seed)

    for i in range(size):
        founder_params, vc_params = _build_scenario(scenario_overrides, rng)
        neg_seed = rng.randint(0, 2**31) if seed is not None else None

        db = SessionLocal()
        try:
            neg = Negotiation(
                model=model,
                max_rounds=max_rounds,
                mock_mode=mock_mode,
                batch_id=batch_id,
                founder_params=founder_params,
                vc_params=vc_params,
                status="running",
            )
            db.add(neg)
            db.commit()
            negotiation_id = neg.id
        finally:
            db.close()

        result = run_negotiation(
            model=model,
            max_rounds=max_rounds,
            founder_params=founder_params,
            vc_params=vc_params,
            mock_mode=mock_mode,
            api_key=api_key,
            seed=neg_seed,
        )
        _persist_result(negotiation_id, result)

        if on_progress is not None:
            on_progress(i + 1, size, result)

    return batch_id


def _persist_result(negotiation_id: str, result: NegotiationResult) -> None:
    from app.jobs import _final_terms_summary
    from app.models import Round
    from datetime import datetime, timezone

    db = SessionLocal()
    try:
        for r in result.rounds:
            db.add(
                Round(
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
        neg.completed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()
