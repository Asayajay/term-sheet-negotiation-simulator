"""The negotiable term sheet: field definitions, JSON schema for structured
output, and diffing between two term sheets for the round-by-round log."""
from __future__ import annotations

from typing import Any

ANTI_DILUTION_OPTIONS = ["none", "broad_based_weighted_average", "full_ratchet"]

# JSON schema for a full term sheet proposal. Used both to force structured
# output from the API and to validate mock-mode output.
TERM_SHEET_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "pre_money_valuation_usd": {"type": "number", "description": "Pre-money valuation in USD"},
        "equity_percentage": {"type": "number", "description": "Equity % the investor receives"},
        "liquidation_preference_multiple": {"type": "number", "description": "1.0, 1.5, or 2.0"},
        "liquidation_participating": {"type": "boolean", "description": "Participating (true) vs non-participating (false)"},
        "board_seats_founder": {"type": "integer"},
        "board_seats_investor": {"type": "integer"},
        "board_seats_independent": {"type": "integer"},
        "option_pool_percentage": {"type": "number"},
        "vesting_years": {"type": "number"},
        "vesting_cliff_months": {"type": "number"},
        "pro_rata_rights": {"type": "boolean"},
        "anti_dilution": {"type": "string", "enum": ANTI_DILUTION_OPTIONS},
    },
    "required": [
        "pre_money_valuation_usd",
        "equity_percentage",
        "liquidation_preference_multiple",
        "liquidation_participating",
        "board_seats_founder",
        "board_seats_investor",
        "board_seats_independent",
        "option_pool_percentage",
        "vesting_years",
        "vesting_cliff_months",
        "pro_rata_rights",
        "anti_dilution",
    ],
    "additionalProperties": False,
}

# Full agent turn: reasoning + action + (terms unless walking away)
TURN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "reasoning": {
            "type": "string",
            "description": "2-4 sentences of stated reasoning for this move.",
        },
        "action": {
            "type": "string",
            "enum": ["propose", "accept", "walk_away"],
            "description": (
                "'propose' to put forward a new/countered term sheet, 'accept' to accept the "
                "other party's most recent proposal as-is, 'walk_away' to end the negotiation "
                "with no deal."
            ),
        },
        "terms": {
            **TERM_SHEET_SCHEMA,
            "description": "Required when action is 'propose'. Omit/ignore when accepting or walking away.",
        },
    },
    "required": ["reasoning", "action", "terms"],
    "additionalProperties": False,
}

TERM_FIELDS = list(TERM_SHEET_SCHEMA["properties"].keys())


def diff_terms(previous: dict | None, current: dict | None) -> dict[str, dict[str, Any]]:
    """Return {field: {"from": x, "to": y}} for every field that changed."""
    if current is None:
        return {}
    previous = previous or {}
    changes: dict[str, dict[str, Any]] = {}
    for field in TERM_FIELDS:
        old, new = previous.get(field), current.get(field)
        if old != new:
            changes[field] = {"from": old, "to": new}
    return changes


def opening_terms_from_vc_scenario(vc_params: dict) -> dict:
    """A reasonable VC opening offer derived from scenario params, used only
    to seed mock mode / as a sanity fallback -- the real opening offer comes
    from the model."""
    enthusiasm = vc_params.get("deal_enthusiasm", 0.5)
    investment = vc_params.get("investment_amount_musd", 1.0) * 1_000_000
    valuation = investment / (0.15 + 0.1 * enthusiasm)
    return {
        "pre_money_valuation_usd": round(valuation, -3),
        "equity_percentage": round(investment / (valuation + investment) * 100, 2),
        "liquidation_preference_multiple": 1.0 if vc_params.get("risk_appetite") == "low" else 1.0,
        "liquidation_participating": vc_params.get("risk_appetite") == "high",
        "board_seats_founder": 2,
        "board_seats_investor": 2,
        "board_seats_independent": 1,
        "option_pool_percentage": 12.0,
        "vesting_years": 4,
        "vesting_cliff_months": 12,
        "pro_rata_rights": True,
        "anti_dilution": "broad_based_weighted_average",
    }
