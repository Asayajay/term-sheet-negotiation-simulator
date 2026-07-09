from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis import negotiation_to_analysis_dict, starting_condition_correlations, term_volatility
from app.database import get_db
from app.models import Negotiation
from app.schemas import StatsOut

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    negs = db.execute(select(Negotiation)).scalars().all()
    completed = [n for n in negs if n.status == "completed"]
    deals = [n for n in completed if n.outcome == "deal"]
    no_deals = [n for n in completed if n.outcome == "no_deal"]
    errors = [n for n in negs if n.status == "failed"]

    valuations = [n.final_valuation for n in deals if n.final_valuation is not None]
    equities = [n.final_equity_pct for n in deals if n.final_equity_pct is not None]
    rounds_to_close = [n.rounds_to_close for n in deals if n.rounds_to_close is not None]

    return StatsOut(
        total_negotiations=len(negs),
        completed=len(completed),
        deals=len(deals),
        no_deals=len(no_deals),
        errors=len(errors),
        total_cost_usd=round(sum(n.total_cost_usd for n in negs), 4),
        total_input_tokens=sum(n.total_input_tokens for n in negs),
        total_output_tokens=sum(n.total_output_tokens for n in negs),
        avg_rounds_to_close=(sum(rounds_to_close) / len(rounds_to_close)) if rounds_to_close else None,
        avg_final_valuation=(sum(valuations) / len(valuations)) if valuations else None,
        avg_final_equity_pct=(sum(equities) / len(equities)) if equities else None,
    )


@router.get("/analysis/term-volatility")
def get_term_volatility(db: Session = Depends(get_db)):
    negs = db.execute(select(Negotiation).where(Negotiation.status == "completed")).scalars().all()
    for n in negs:
        _ = n.rounds  # force-load relationship before session closes
    return term_volatility([negotiation_to_analysis_dict(n) for n in negs])


@router.get("/analysis/correlations")
def get_correlations(db: Session = Depends(get_db)):
    negs = db.execute(select(Negotiation).where(Negotiation.status == "completed")).scalars().all()
    for n in negs:
        _ = n.rounds
    return starting_condition_correlations([negotiation_to_analysis_dict(n) for n in negs])
