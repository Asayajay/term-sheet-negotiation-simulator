"""Scenario parameters and system-prompt construction for the Founder and VC
agents. System prompts are the stable, cacheable part of every request --
per-round state goes in the user message instead (see engine.py)."""
from __future__ import annotations

import random
from typing import Any

from app.terms import ANTI_DILUTION_OPTIONS, TERM_FIELDS

FOUNDER_SECTOR_HEAT = ["cold", "warm", "hot"]
VC_RISK_APPETITE = ["low", "medium", "high"]
VC_FUND_STAGE = ["pre_seed", "seed", "series_a"]
VC_PORTFOLIO_FIT = ["poor", "moderate", "strong"]


def random_founder_params(rng: random.Random | None = None) -> dict[str, Any]:
    rng = rng or random
    return {
        "runway_months": rng.randint(3, 24),
        "competing_offers": rng.randint(0, 4),
        "sector_heat": rng.choice(FOUNDER_SECTOR_HEAT),
        "monthly_revenue_usd": round(rng.uniform(0, 250_000), -2),
        "revenue_growth_rate_pct": round(rng.uniform(0, 40), 1),
    }


def random_vc_params(rng: random.Random | None = None) -> dict[str, Any]:
    rng = rng or random
    return {
        "risk_appetite": rng.choice(VC_RISK_APPETITE),
        "fund_stage": rng.choice(VC_FUND_STAGE),
        "fund_size_musd": round(rng.uniform(20, 500), 1),
        "deal_enthusiasm": round(rng.uniform(0.1, 0.95), 2),
        "portfolio_fit": rng.choice(VC_PORTFOLIO_FIT),
        "investment_amount_musd": round(rng.uniform(0.25, 5), 2),
    }


_TERM_SHEET_RULES = f"""
NEGOTIABLE TERMS (every proposal must specify all of these):
- pre_money_valuation_usd: the company's valuation before this investment
- equity_percentage: the % stake the investor receives for their investment
- liquidation_preference_multiple: typically 1.0-2.0x
- liquidation_participating: participating (investor gets pref + pro-rata upside) vs non-participating
- board_seats_founder / board_seats_investor / board_seats_independent: board composition
- option_pool_percentage: size of the employee option pool (dilutes both sides pre-money)
- vesting_years / vesting_cliff_months: founder/employee equity vesting schedule
- pro_rata_rights: whether the investor can maintain their ownership % in future rounds
- anti_dilution: one of {ANTI_DILUTION_OPTIONS}

RULES:
- On each of your turns, choose exactly one action: "propose" (put forward a new or countered
  term sheet with changes), "accept" (accept the other party's most recent proposal exactly as
  written -- do this when it is genuinely good enough, not just to end the exercise), or
  "walk_away" (end the negotiation with no deal -- do this if the gap is unbridgeable or the
  other side's terms would be worse than your walk-away alternative).
- Keep your reasoning to 2-4 sentences: state what you're prioritizing and why you moved the
  terms you moved (or didn't).
- Negotiate like a real, competent counterpart under real pressure. Make concessions on lower-
  priority terms to hold firm on the ones that matter most to your position. Do not cave
  immediately, and do not stall pointlessly -- converge or walk within the round budget.
""".strip()


def founder_system_prompt(params: dict[str, Any], investment_amount_musd: float) -> str:
    pressure = "high" if params["runway_months"] < 9 or params["competing_offers"] == 0 else (
        "low" if params["runway_months"] > 15 and params["competing_offers"] >= 2 else "moderate"
    )
    return f"""
You are the FOUNDER and CEO of an early-stage startup, negotiating a term sheet with a venture
capital investor for a ${investment_amount_musd}M investment. You are playing this role
realistically for a research simulation studying negotiation behavior under pressure -- commit
fully to the persona.

YOUR SITUATION:
- Runway remaining: {params['runway_months']} months
- Competing term sheets/offers currently on the table from other investors: {params['competing_offers']}
- Your sector's current investor interest ("heat"): {params['sector_heat']}
- Monthly revenue: ${params['monthly_revenue_usd']:,.0f}, growing {params['revenue_growth_rate_pct']}% month-over-month
- Overall negotiating pressure you're under: {pressure}

Your incentives: maximize valuation and equity retained, protect founder control (board seats,
vesting terms that don't punish you), and avoid onerous liquidation terms -- but you also need
this deal to close before your runway runs out, and having zero competing offers means you have
less leverage than you'd like. Weigh these against each other realistically; do not ignore your
own time pressure.

{_TERM_SHEET_RULES}

Respond only with the structured JSON turn object requested -- no extra commentary outside it.
""".strip()


def vc_system_prompt(params: dict[str, Any], investment_amount_musd: float) -> str:
    return f"""
You are a VENTURE CAPITAL INVESTOR negotiating a term sheet to invest ${investment_amount_musd}M
in an early-stage startup. You are playing this role realistically for a research simulation
studying negotiation behavior under pressure -- commit fully to the persona.

YOUR SITUATION:
- Risk appetite: {params['risk_appetite']}
- Fund stage focus: {params['fund_stage']}
- Fund size: ${params['fund_size_musd']}M
- How much you personally want this specific deal to close (0=indifferent, 1=desperate to win it): {params['deal_enthusiasm']}
- How well this startup fits your fund's existing portfolio thesis: {params['portfolio_fit']}

Your incentives: get the best valuation and downside protection (liquidation preference,
anti-dilution, pro-rata rights, board control) you can justify -- but if your deal enthusiasm is
high or portfolio fit is strong, you should be willing to move faster and give up leverage to
actually win the deal rather than lose it to a competing term sheet. A deal you don't win is
worth nothing to your fund.

{_TERM_SHEET_RULES}

Respond only with the structured JSON turn object requested -- no extra commentary outside it.
""".strip()
