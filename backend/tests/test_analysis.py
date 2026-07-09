from app.analysis import starting_condition_correlations, term_volatility


def _fake_negotiation(valuations, founder_runway=10, outcome="deal"):
    """valuations: list of pre_money_valuation_usd across successive proposal
    rounds, used to synthesize a fake transcript for volatility testing."""
    rounds = [{"terms": {"pre_money_valuation_usd": v, "equity_percentage": 20.0}} for v in valuations]
    return {
        "outcome": outcome,
        "final_valuation": valuations[-1] if valuations else None,
        "final_equity_pct": 20.0,
        "rounds_to_close": len(valuations),
        "founder_params": {"runway_months": founder_runway, "competing_offers": 1},
        "vc_params": {"deal_enthusiasm": 0.5, "fund_size_musd": 100, "investment_amount_musd": 1.0},
        "rounds": rounds,
    }


def test_term_volatility_detects_moving_field():
    negs = [_fake_negotiation([5_000_000, 6_000_000, 7_000_000]) for _ in range(5)]
    result = term_volatility(negs)
    assert result["pre_money_valuation_usd"]["avg_absolute_change_per_round"] > 0
    # equity_percentage never changes in this fixture -> zero volatility
    assert result["equity_percentage"]["avg_absolute_change_per_round"] == 0


def test_term_volatility_handles_no_data():
    result = term_volatility([])
    assert result["pre_money_valuation_usd"]["avg_absolute_change_per_round"] == 0
    assert result["pre_money_valuation_usd"]["n_changes_observed"] == 0


def test_correlations_detect_relationship():
    # Construct a clean positive relationship: more runway -> higher final valuation
    negs = [
        _fake_negotiation([3_000_000 + i * 1_000_000, 3_000_000 + i * 1_000_000], founder_runway=i + 1)
        for i in range(10)
    ]
    result = starting_condition_correlations(negs)
    corr = result["founder.runway_months"]["final_valuation"]
    assert corr > 0.9


def test_correlations_handle_no_data():
    result = starting_condition_correlations([])
    assert result["founder.runway_months"] == {}
