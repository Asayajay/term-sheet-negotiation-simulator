from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.batch import estimate_batch, run_batch
from app.config import get_settings
from app.database import SessionLocal
from app.limits import CapExceededError, validate_batch_size, validate_max_rounds, validate_model
from app.models import Negotiation
from app.schemas import BatchEstimateResponse, BatchRequest, NegotiationSummaryOut

router = APIRouter(prefix="/api/batch", tags=["batch"])

# batch_id -> {"completed": int, "total": int, "status": str}
_batch_progress: dict[str, dict] = {}


@router.post("", response_model=BatchEstimateResponse)
async def trigger_batch(req: BatchRequest):
    """Two-step confirm flow: call with confirm=false (default) to get the
    cost estimate without spending anything; call again with confirm=true
    to actually run the batch in the background."""
    settings = get_settings()
    mock_mode = req.mock_mode or settings.mock_mode

    try:
        validate_model(req.model)
        validate_max_rounds(req.max_rounds, req.override_caps)
        validate_batch_size(req.size, req.override_caps)
    except CapExceededError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    est = estimate_batch(req.model, req.max_rounds, req.size)
    estimated_cost = 0.0 if mock_mode else est.estimated_cost_usd

    if not req.confirm:
        return BatchEstimateResponse(
            batch_size=req.size,
            max_rounds=req.max_rounds,
            model=req.model,
            estimated_cost_usd=estimated_cost,
            requires_confirmation=True,
        )

    scenario_overrides = None
    if req.scenario:
        scenario_overrides = {"founder": req.scenario.founder, "vc": req.scenario.vc}

    batch_id = uuid.uuid4().hex
    _batch_progress[batch_id] = {"completed": 0, "total": req.size, "status": "running"}

    def _progress(done: int, total: int, _result) -> None:
        _batch_progress[batch_id] = {
            "completed": done,
            "total": total,
            "status": "running" if done < total else "completed",
        }

    def _run() -> None:
        run_batch(
            size=req.size,
            model=req.model,
            max_rounds=req.max_rounds,
            mock_mode=mock_mode,
            override_caps=req.override_caps,
            api_key=settings.anthropic_api_key,
            scenario_overrides=scenario_overrides,
            batch_id=batch_id,
            on_progress=_progress,
        )

    async def _run_in_background() -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _run)

    asyncio.create_task(_run_in_background())

    return BatchEstimateResponse(
        batch_size=req.size,
        max_rounds=req.max_rounds,
        model=req.model,
        estimated_cost_usd=estimated_cost,
        requires_confirmation=False,
    )


@router.get("/{batch_id}")
def get_batch_status(batch_id: str):
    progress = _batch_progress.get(batch_id, {"completed": None, "total": None, "status": "unknown"})
    db = SessionLocal()
    try:
        negs = (
            db.execute(select(Negotiation).where(Negotiation.batch_id == batch_id).order_by(Negotiation.created_at))
            .scalars()
            .all()
        )
        if not negs and progress["status"] == "unknown":
            raise HTTPException(status_code=404, detail="batch not found")
        summaries = [NegotiationSummaryOut.model_validate(n) for n in negs]
        return {"batch_id": batch_id, "progress": progress, "negotiations": summaries}
    finally:
        db.close()
