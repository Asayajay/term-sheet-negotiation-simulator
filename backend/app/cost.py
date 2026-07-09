"""Token cost calculation, used both for real per-turn logging and for the
pre-flight batch cost estimate."""
from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


def turn_cost_usd(model: str, usage: TokenUsage) -> float:
    """Actual cost of one API call given real usage counters.

    Cache reads are billed at ~0.1x input price, cache writes at ~1.25x --
    both already reflected in Anthropic's per-model input rate; we apply the
    published multipliers here rather than assuming the base rate covers it.
    """
    rates = get_settings().pricing_usd_per_million_tokens[model]
    input_cost = usage.input_tokens * rates.input
    cache_read_cost = usage.cache_read_tokens * rates.input * 0.1
    cache_write_cost = usage.cache_creation_tokens * rates.input * 1.25
    output_cost = usage.output_tokens * rates.output
    return (input_cost + cache_read_cost + cache_write_cost + output_cost) / 1_000_000


def estimate_negotiation_cost_usd(model: str, max_rounds: int) -> float:
    """Rough pre-flight estimate: max_rounds round-trips x 2 turns/round x
    average tokens/turn from config. Assumes worst case (no early accept),
    which is the right bias for a pre-flight ceiling estimate."""
    settings = get_settings()
    rates = settings.pricing_usd_per_million_tokens[model]
    turns = max_rounds * 2
    input_tokens = turns * settings.estimate.avg_input_tokens_per_turn
    output_tokens = turns * settings.estimate.avg_output_tokens_per_turn
    return (input_tokens * rates.input + output_tokens * rates.output) / 1_000_000


def estimate_batch_cost_usd(model: str, max_rounds: int, batch_size: int) -> float:
    return estimate_negotiation_cost_usd(model, max_rounds) * batch_size
