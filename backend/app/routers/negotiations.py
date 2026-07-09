from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.cost import estimate_negotiation_cost_usd
from app.database import get_db
from app.jobs import start_negotiation_job
from app.limits import CapExceededError, validate_max_rounds, validate_model
from app.models import Negotiation
from app.personas import random_founder_params, random_vc_params
from app.schemas import NegotiationOut, NegotiationSummaryOut, TriggerRequest, TriggerResponse

router = APIRouter(prefix="/api/negotiations", tags=["negotiations"])


@router.post("", response_model=TriggerResponse)
async def trigger_negotiation(req: TriggerRequest, db: Session = Depends(get_db)):
    settings = get_settings()
    mock_mode = req.mock_mode or settings.mock_mode
    try:
        validate_model(req.model)
        validate_max_rounds(req.max_rounds, override=False)
    except CapExceededError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    founder_params = random_founder_params()
    vc_params = random_vc_params()
    if req.scenario:
        founder_params.update(req.scenario.founder or {})
        vc_params.update(req.scenario.vc or {})

    neg = Negotiation(
        model=req.model,
        max_rounds=req.max_rounds,
        mock_mode=mock_mode,
        founder_params=founder_params,
        vc_params=vc_params,
        status="pending",
    )
    db.add(neg)
    db.commit()

    estimated_cost = 0.0 if mock_mode else estimate_negotiation_cost_usd(req.model, req.max_rounds)

    params = {
        "model": req.model,
        "max_rounds": req.max_rounds,
        "founder_params": founder_params,
        "vc_params": vc_params,
        "mock_mode": mock_mode,
        "api_key": settings.anthropic_api_key,
        "seed": req.seed,
    }
    asyncio.create_task(start_negotiation_job(neg.id, params))

    return TriggerResponse(negotiation_id=neg.id, estimated_cost_usd=round(estimated_cost, 4), status="pending")


@router.get("", response_model=list[NegotiationSummaryOut])
def list_negotiations(batch_id: str | None = None, limit: int = 100, db: Session = Depends(get_db)):
    stmt = select(Negotiation).order_by(Negotiation.created_at.desc()).limit(limit)
    if batch_id:
        stmt = stmt.where(Negotiation.batch_id == batch_id)
    return db.execute(stmt).scalars().all()


@router.get("/{negotiation_id}", response_model=NegotiationOut)
def get_negotiation(negotiation_id: str, db: Session = Depends(get_db)):
    neg = db.get(Negotiation, negotiation_id)
    if not neg:
        raise HTTPException(status_code=404, detail="negotiation not found")
    return neg
