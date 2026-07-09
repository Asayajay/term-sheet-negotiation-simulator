from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Negotiation(Base):
    __tablename__ = "negotiations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|running|completed|failed
    model: Mapped[str] = mapped_column(String)
    max_rounds: Mapped[int] = mapped_column(Integer)
    mock_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    batch_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    founder_params: Mapped[dict] = mapped_column(JSON)
    vc_params: Mapped[dict] = mapped_column(JSON)

    outcome: Mapped[str | None] = mapped_column(String, nullable=True)  # deal|no_deal|walked_away
    final_terms: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Denormalized structured fields for fast correlation analysis / charting
    final_valuation: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_equity_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_liquidation_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_liquidation_participating: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rounds_to_close: Mapped[int | None] = mapped_column(Integer, nullable=True)

    total_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    rounds: Mapped[list["Round"]] = relationship(
        "Round", back_populates="negotiation", cascade="all, delete-orphan", order_by="Round.sequence"
    )


class Round(Base):
    __tablename__ = "rounds"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    negotiation_id: Mapped[str] = mapped_column(ForeignKey("negotiations.id"))
    sequence: Mapped[int] = mapped_column(Integer)  # global turn order, 0-indexed
    round_number: Mapped[int] = mapped_column(Integer)  # round-trip number, 1-indexed
    actor: Mapped[str] = mapped_column(String)  # founder|vc
    action: Mapped[str] = mapped_column(String)  # propose|accept|walk_away
    terms: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reasoning: Mapped[str] = mapped_column(Text)
    diff: Mapped[dict] = mapped_column(JSON, default=dict)

    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    negotiation: Mapped[Negotiation] = relationship("Negotiation", back_populates="rounds")
