"""The core round-by-round negotiation loop. VC always opens each round;
Founder responds. Terminates on accept, walk-away, or exhausting max_rounds."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from app.agents import build_agent
from app.cost import TokenUsage, turn_cost_usd
from app.personas import founder_system_prompt, vc_system_prompt
from app.terms import diff_terms

# Absolute safety net independent of the configurable/override-able cap
# enforced at the API layer (see app/limits.py) -- this just prevents a
# runaway loop if something calls the engine directly.
ABSOLUTE_MAX_ROUNDS = 50


@dataclass
class RoundResult:
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


@dataclass
class NegotiationResult:
    outcome: str  # "deal" | "no_deal" | "error"
    final_terms: dict[str, Any] | None
    rounds: list[RoundResult] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    rounds_to_close: int | None = None
    error: str | None = None


RoundCallback = Callable[[RoundResult], None]


def run_negotiation(
    *,
    model: str,
    max_rounds: int,
    founder_params: dict[str, Any],
    vc_params: dict[str, Any],
    mock_mode: bool = False,
    api_key: str | None = None,
    seed: int | None = None,
    on_round: RoundCallback | None = None,
) -> NegotiationResult:
    if max_rounds > ABSOLUTE_MAX_ROUNDS:
        raise ValueError(f"max_rounds={max_rounds} exceeds absolute safety ceiling {ABSOLUTE_MAX_ROUNDS}")

    investment_amount_musd = vc_params.get("investment_amount_musd", 1.0)
    founder_agent = build_agent(
        "founder",
        founder_system_prompt(founder_params, investment_amount_musd),
        model,
        mock_mode,
        api_key=api_key,
        seed=seed,
    )
    vc_agent = build_agent(
        "vc",
        vc_system_prompt(vc_params, investment_amount_musd),
        model,
        mock_mode,
        api_key=api_key,
        seed=(seed + 1) if seed is not None else None,
    )
    agents = {"founder": founder_agent, "vc": vc_agent}

    current_terms: dict[str, Any] | None = None
    last_reasoning: dict[str, str | None] = {"founder": None, "vc": None}
    rounds: list[RoundResult] = []
    sequence = 0
    total_input = total_output = 0
    total_cost = 0.0
    outcome: str | None = None
    final_terms: dict[str, Any] | None = None
    error: str | None = None

    try:
        for round_number in range(1, max_rounds + 1):
            for actor in ("vc", "founder"):
                opponent = "founder" if actor == "vc" else "vc"
                is_opening = current_terms is None
                state = {
                    "round_number": round_number,
                    "rounds_remaining": max_rounds - round_number + 1,
                    "current_terms": current_terms,
                    "opponent_last_reasoning": last_reasoning[opponent],
                    "instruction": (
                        "This is the opening move of the negotiation -- you must propose the "
                        "first term sheet."
                        if is_opening
                        else "Respond with your action for this round: propose a counter, "
                        "accept the terms above as-is, or walk away."
                    ),
                }
                turn = agents[actor].get_turn(json.dumps(state))

                if is_opening and turn.action != "propose":
                    raise RuntimeError(
                        f"{actor} returned action={turn.action!r} on the opening turn, expected 'propose'"
                    )

                previous_terms = current_terms
                if turn.action == "propose":
                    current_terms = turn.terms
                # No diff on the opening move -- there's no prior state for
                # anything to have "changed" from.
                diff = (
                    {}
                    if is_opening
                    else diff_terms(previous_terms, current_terms if turn.action == "propose" else None)
                )

                cost = turn_cost_usd(model, turn.usage)
                result = RoundResult(
                    sequence=sequence,
                    round_number=round_number,
                    actor=actor,
                    action=turn.action,
                    terms=turn.terms if turn.action == "propose" else None,
                    reasoning=turn.reasoning,
                    diff=diff,
                    input_tokens=turn.usage.input_tokens,
                    output_tokens=turn.usage.output_tokens,
                    cache_read_tokens=turn.usage.cache_read_tokens,
                    cost_usd=cost,
                )
                rounds.append(result)
                sequence += 1
                total_input += turn.usage.input_tokens
                total_output += turn.usage.output_tokens
                total_cost += cost
                last_reasoning[actor] = turn.reasoning

                if on_round is not None:
                    on_round(result)

                if turn.action == "accept":
                    outcome = "deal"
                    final_terms = previous_terms
                    break
                if turn.action == "walk_away":
                    outcome = "no_deal"
                    final_terms = None
                    break
            if outcome is not None:
                break

        if outcome is None:
            outcome = "no_deal"  # ran out of rounds without convergence
            final_terms = None

    except Exception as exc:  # noqa: BLE001 - surface as a failed negotiation, don't crash the batch
        outcome = "error"
        error = str(exc)

    return NegotiationResult(
        outcome=outcome,
        final_terms=final_terms,
        rounds=rounds,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_cost_usd=total_cost,
        rounds_to_close=rounds[-1].round_number if outcome == "deal" and rounds else None,
        error=error,
    )
