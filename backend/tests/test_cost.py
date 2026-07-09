import pytest

from app.cost import TokenUsage, estimate_batch_cost_usd, estimate_negotiation_cost_usd, turn_cost_usd
from app.limits import CapExceededError, validate_batch_size, validate_max_rounds, validate_model


def test_turn_cost_uses_configured_rates():
    usage = TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)
    cost = turn_cost_usd("claude-haiku-4-5", usage)
    assert cost == pytest.approx(1.00 + 5.00)


def test_cache_read_is_cheaper_than_full_input():
    full = turn_cost_usd("claude-haiku-4-5", TokenUsage(input_tokens=1000))
    cached = turn_cost_usd("claude-haiku-4-5", TokenUsage(cache_read_tokens=1000))
    assert cached < full


def test_estimate_scales_with_rounds_and_batch_size():
    one_round = estimate_negotiation_cost_usd("claude-haiku-4-5", max_rounds=1)
    six_rounds = estimate_negotiation_cost_usd("claude-haiku-4-5", max_rounds=6)
    assert six_rounds == pytest.approx(one_round * 6)

    batch = estimate_batch_cost_usd("claude-haiku-4-5", max_rounds=6, batch_size=10)
    assert batch == pytest.approx(six_rounds * 10)


def test_validate_max_rounds_refuses_above_hard_cap_without_override():
    with pytest.raises(CapExceededError):
        validate_max_rounds(13, override=False)
    validate_max_rounds(13, override=True)  # should not raise
    validate_max_rounds(6, override=False)  # default is fine


def test_validate_batch_size_refuses_above_hard_cap_without_override():
    with pytest.raises(CapExceededError):
        validate_batch_size(101, override=False)
    validate_batch_size(101, override=True)


def test_validate_model_rejects_unknown_model():
    with pytest.raises(CapExceededError):
        validate_model("gpt-4o")
    validate_model("claude-haiku-4-5")
