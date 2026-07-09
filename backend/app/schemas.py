from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings


class ScenarioOverrides(BaseModel):
    """Optional overrides for scenario parameters; anything omitted is
    randomized within the configured ranges."""

    founder: dict[str, Any] | None = None
    vc: dict[str, Any] | None = None


class TriggerRequest(BaseModel):
    model: str = Field(default_factory=lambda: get_settings().model.default)
    max_rounds: int = Field(default_factory=lambda: get_settings().rounds.default_max_rounds)
    mock_mode: bool = False
    scenario: ScenarioOverrides | None = None
    seed: int | None = None


class TriggerResponse(BaseModel):
    negotiation_id: str
    estimated_cost_usd: float
    status: str


class BatchRequest(BaseModel):
    size: int = Field(default_factory=lambda: get_settings().batch.default_size_cap)
    model: str = Field(default_factory=lambda: get_settings().model.default)
    max_rounds: int = Field(default_factory=lambda: get_settings().rounds.default_max_rounds)
    mock_mode: bool = False
    override_caps: bool = False
    confirm: bool = False
    scenario: ScenarioOverrides | None = None


class BatchEstimateResponse(BaseModel):
    batch_size: int
    max_rounds: int
    model: str
    estimated_cost_usd: float
    requires_confirmation: bool


class RoundOut(BaseModel):
    sequence: int
    round_number: int
    actor: str
    action: str
    terms: dict[str, Any] | None
    reasoning: str
    diff: dict[str, Any]
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cost_usd: float
    created_at: datetime

    class Config:
        from_attributes = True


class NegotiationOut(BaseModel):
    id: str
    status: str
    model: str
    max_rounds: int
    mock_mode: bool
    batch_id: str | None
    founder_params: dict[str, Any]
    vc_params: dict[str, Any]
    outcome: str | None
    final_terms: dict[str, Any] | None
    final_valuation: float | None
    final_equity_pct: float | None
    final_liquidation_multiple: float | None
    final_liquidation_participating: bool | None
    rounds_to_close: int | None
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    error: str | None
    created_at: datetime
    completed_at: datetime | None
    rounds: list[RoundOut] = []

    class Config:
        from_attributes = True


class NegotiationSummaryOut(BaseModel):
    id: str
    status: str
    model: str
    outcome: str | None
    batch_id: str | None
    final_valuation: float | None
    final_equity_pct: float | None
    rounds_to_close: int | None
    total_cost_usd: float
    created_at: datetime

    class Config:
        from_attributes = True


class StatsOut(BaseModel):
    total_negotiations: int
    completed: int
    deals: int
    no_deals: int
    errors: int
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    avg_rounds_to_close: float | None
    avg_final_valuation: float | None
    avg_final_equity_pct: float | None
