"""Term volatility and starting-condition/outcome correlation, computed over
whatever negotiations are passed in (typically "all completed negotiations").
Pure functions over plain dicts so they're trivially unit-testable in mock
mode with zero API cost."""
from __future__ import annotations

from typing import Any

from app.terms import TERM_FIELDS

NUMERIC_TERM_FIELDS = [
    "pre_money_valuation_usd",
    "equity_percentage",
    "liquidation_preference_multiple",
    "board_seats_founder",
    "board_seats_investor",
    "board_seats_independent",
    "option_pool_percentage",
    "vesting_years",
    "vesting_cliff_months",
]
CATEGORICAL_TERM_FIELDS = ["liquidation_participating", "pro_rata_rights", "anti_dilution"]

STARTING_CONDITION_FIELDS = {
    "founder.runway_months": lambda n: n["founder_params"].get("runway_months"),
    "founder.competing_offers": lambda n: n["founder_params"].get("competing_offers"),
    "founder.monthly_revenue_usd": lambda n: n["founder_params"].get("monthly_revenue_usd"),
    "founder.revenue_growth_rate_pct": lambda n: n["founder_params"].get("revenue_growth_rate_pct"),
    "vc.deal_enthusiasm": lambda n: n["vc_params"].get("deal_enthusiasm"),
    "vc.fund_size_musd": lambda n: n["vc_params"].get("fund_size_musd"),
    "vc.investment_amount_musd": lambda n: n["vc_params"].get("investment_amount_musd"),
}
OUTCOME_FIELDS = {
    "final_valuation": lambda n: n.get("final_valuation"),
    "final_equity_pct": lambda n: n.get("final_equity_pct"),
    "rounds_to_close": lambda n: n.get("rounds_to_close"),
    "deal_reached": lambda n: 1.0 if n.get("outcome") == "deal" else 0.0,
}


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return None
    return cov / (var_x**0.5 * var_y**0.5)


def term_volatility(negotiations: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """For each negotiable term, measure how much it moved round-over-round.

    Numeric terms: average absolute % change per proposal (relative to the
    field's own scale, using the field's mean value across all rounds as the
    denominator so wildly-different-magnitude fields are comparable).
    Categorical/boolean terms: fraction of proposal-rounds where the value
    changed from the prior proposal -- "non-negotiable" terms should sit near 0.
    """
    numeric_changes: dict[str, list[float]] = {f: [] for f in NUMERIC_TERM_FIELDS}
    numeric_values: dict[str, list[float]] = {f: [] for f in NUMERIC_TERM_FIELDS}
    categorical_changes: dict[str, list[int]] = {f: [] for f in CATEGORICAL_TERM_FIELDS}

    for neg in negotiations:
        prior: dict[str, Any] | None = None
        for rnd in neg.get("rounds", []):
            terms = rnd.get("terms")
            if not terms:
                continue
            if prior is not None:
                for f in NUMERIC_TERM_FIELDS:
                    old, new = prior.get(f), terms.get(f)
                    if isinstance(old, (int, float)) and isinstance(new, (int, float)):
                        numeric_changes[f].append(abs(new - old))
                for f in CATEGORICAL_TERM_FIELDS:
                    if f in prior and f in terms:
                        categorical_changes[f].append(1 if prior[f] != terms[f] else 0)
            for f in NUMERIC_TERM_FIELDS:
                v = terms.get(f)
                if isinstance(v, (int, float)):
                    numeric_values[f].append(v)
            prior = terms

    result: dict[str, dict[str, float]] = {}
    for f in NUMERIC_TERM_FIELDS:
        changes = numeric_changes[f]
        values = numeric_values[f]
        mean_val = (sum(values) / len(values)) if values else 0.0
        avg_abs_change = (sum(changes) / len(changes)) if changes else 0.0
        pct_volatility = (avg_abs_change / mean_val * 100) if mean_val else 0.0
        result[f] = {
            "avg_absolute_change_per_round": round(avg_abs_change, 4),
            "pct_volatility": round(pct_volatility, 2),
            "n_changes_observed": len(changes),
        }
    for f in CATEGORICAL_TERM_FIELDS:
        changes = categorical_changes[f]
        change_rate = (sum(changes) / len(changes)) if changes else 0.0
        result[f] = {
            "change_rate": round(change_rate, 4),
            "n_changes_observed": len(changes),
        }
    return result


def starting_condition_correlations(negotiations: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Pearson correlation between each starting condition and each outcome
    metric, computed only over negotiation pairs where both values exist."""
    result: dict[str, dict[str, float]] = {}
    for cond_name, cond_fn in STARTING_CONDITION_FIELDS.items():
        result[cond_name] = {}
        for outcome_name, outcome_fn in OUTCOME_FIELDS.items():
            xs, ys = [], []
            for n in negotiations:
                x, y = cond_fn(n), outcome_fn(n)
                if x is not None and y is not None:
                    xs.append(float(x))
                    ys.append(float(y))
            corr = _pearson(xs, ys)
            if corr is not None:
                result[cond_name][outcome_name] = round(corr, 3)
    return result


def negotiation_to_analysis_dict(n) -> dict[str, Any]:
    """Convert a Negotiation ORM row (with .rounds loaded) into the plain
    dict shape the functions above expect."""
    return {
        "outcome": n.outcome,
        "final_valuation": n.final_valuation,
        "final_equity_pct": n.final_equity_pct,
        "rounds_to_close": n.rounds_to_close,
        "founder_params": n.founder_params,
        "vc_params": n.vc_params,
        "rounds": [{"terms": r.terms} for r in n.rounds],
    }
