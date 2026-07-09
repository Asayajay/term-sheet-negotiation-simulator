"""Central config: loads config.yaml, layers env var overrides on top.

Cost-control caps live here as constants the rest of the app imports --
nothing else should hardcode a round or batch limit.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


class ModelConfig(BaseModel):
    default: str
    allowed: list[str]


class RoundsConfig(BaseModel):
    default_max_rounds: int
    hard_cap: int


class BatchConfig(BaseModel):
    default_size_cap: int
    hard_cap: int


class PriceRate(BaseModel):
    input: float
    output: float


class EstimateConfig(BaseModel):
    avg_input_tokens_per_turn: int
    avg_output_tokens_per_turn: int


class Settings(BaseModel):
    model: ModelConfig
    rounds: RoundsConfig
    batch: BatchConfig
    pricing_usd_per_million_tokens: dict[str, PriceRate]
    estimate: EstimateConfig
    scenario_ranges: dict

    # Runtime-only settings (env vars, not in yaml)
    database_url: str = "sqlite:///./negotiations.db"
    anthropic_api_key: str | None = None
    mock_mode: bool = False


@lru_cache
def get_settings() -> Settings:
    with open(CONFIG_PATH) as f:
        raw = yaml.safe_load(f)

    return Settings(
        **raw,
        database_url=os.environ.get("DATABASE_URL", "sqlite:///./negotiations.db"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        mock_mode=os.environ.get("MOCK_MODE", "false").lower() in ("1", "true", "yes"),
    )
