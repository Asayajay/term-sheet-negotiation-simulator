"""Engine tests run entirely in mock mode -- zero API cost."""
from app.engine import run_negotiation
from app.personas import random_founder_params, random_vc_params


def test_negotiation_terminates_within_max_rounds():
    result = run_negotiation(
        model="claude-haiku-4-5",
        max_rounds=6,
        founder_params=random_founder_params(),
        vc_params=random_vc_params(),
        mock_mode=True,
        seed=42,
    )
    assert result.outcome in ("deal", "no_deal", "error")
    assert result.error is None
    # at most 2 turns per round
    assert len(result.rounds) <= 6 * 2
    assert result.total_cost_usd == 0.0  # mock mode never calls the API


def test_opening_turn_is_always_a_proposal():
    result = run_negotiation(
        model="claude-haiku-4-5",
        max_rounds=3,
        founder_params=random_founder_params(),
        vc_params=random_vc_params(),
        mock_mode=True,
        seed=1,
    )
    opening = result.rounds[0]
    assert opening.actor == "vc"
    assert opening.action == "propose"
    assert opening.terms is not None


def test_deal_outcome_has_final_terms_and_no_deal_outcome_does_not():
    # Run many seeds so we exercise both outcome branches deterministically.
    outcomes = set()
    for seed in range(30):
        result = run_negotiation(
            model="claude-haiku-4-5",
            max_rounds=6,
            founder_params=random_founder_params(),
            vc_params=random_vc_params(),
            mock_mode=True,
            seed=seed,
        )
        outcomes.add(result.outcome)
        if result.outcome == "deal":
            assert result.final_terms is not None
            assert result.rounds_to_close is not None
        else:
            assert result.final_terms is None
    assert "deal" in outcomes  # at least one seed converges
    assert "no_deal" in outcomes  # at least one seed doesn't


def test_round_trip_callback_fires_for_every_turn():
    seen = []
    result = run_negotiation(
        model="claude-haiku-4-5",
        max_rounds=4,
        founder_params=random_founder_params(),
        vc_params=random_vc_params(),
        mock_mode=True,
        seed=7,
        on_round=lambda r: seen.append(r.sequence),
    )
    assert seen == [r.sequence for r in result.rounds]


def test_max_rounds_safety_ceiling():
    import pytest

    with pytest.raises(ValueError):
        run_negotiation(
            model="claude-haiku-4-5",
            max_rounds=999,
            founder_params=random_founder_params(),
            vc_params=random_vc_params(),
            mock_mode=True,
        )
