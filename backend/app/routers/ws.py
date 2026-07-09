from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.database import SessionLocal
from app.jobs import subscribe, unsubscribe
from app.models import Negotiation, Round
from app.schemas import RoundOut

router = APIRouter()


@router.websocket("/ws/negotiations/{negotiation_id}")
async def negotiation_ws(websocket: WebSocket, negotiation_id: str):
    await websocket.accept()

    # Replay whatever rounds already happened (covers reconnects and the
    # case where the client connects slightly after the job started).
    db = SessionLocal()
    try:
        neg = db.get(Negotiation, negotiation_id)
        if neg is None:
            await websocket.send_json({"type": "error", "message": "negotiation not found"})
            await websocket.close()
            return
        existing = db.execute(
            select(Round).where(Round.negotiation_id == negotiation_id).order_by(Round.sequence)
        ).scalars().all()
        for r in existing:
            await websocket.send_json({"type": "round", **RoundOut.model_validate(r).model_dump(mode="json")})
        already_done = neg.status in ("completed", "failed")
        if already_done:
            await websocket.send_json(
                {"type": "done", "outcome": neg.outcome, "total_cost_usd": neg.total_cost_usd, "error": neg.error}
            )
    finally:
        db.close()

    if already_done:
        await websocket.close()
        return

    queue = subscribe(negotiation_id)
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
            if event.get("type") == "done":
                break
    except WebSocketDisconnect:
        pass
    finally:
        unsubscribe(negotiation_id, queue)
