"""The two negotiating agents. Real mode calls the Claude API with structured
JSON output and prompt caching on the system prompt; mock mode fakes a
plausible turn with zero API calls and zero cost, so the whole pipeline
(engine, DB, API, frontend, websockets) can be exercised for free."""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from typing import Any

from app.cost import TokenUsage
from app.terms import TERM_FIELDS, TURN_SCHEMA

VALID_ACTIONS = {"propose", "accept", "walk_away"}


@dataclass
class AgentTurn:
    reasoning: str
    action: str
    terms: dict[str, Any] | None
    usage: TokenUsage

    def __post_init__(self) -> None:
        if self.action not in VALID_ACTIONS:
            raise ValueError(f"invalid action from model: {self.action!r}")
        if self.action == "propose" and not self.terms:
            raise ValueError("action=propose but no terms were provided")


class BaseAgent:
    role: str  # "founder" | "vc"

    def __init__(self, role: str, system_prompt: str, model: str):
        self.role = role
        self.system_prompt = system_prompt
        self.model = model

    def get_turn(self, user_message: str) -> AgentTurn:  # pragma: no cover - interface
        raise NotImplementedError


class RealAgent(BaseAgent):
    """Calls the live Anthropic API. Costs real money -- callers are
    responsible for cap enforcement and cost-estimate confirmation before
    this is ever invoked in a loop."""

    def __init__(self, role: str, system_prompt: str, model: str, api_key: str | None = None):
        super().__init__(role, system_prompt, model)
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)

    def get_turn(self, user_message: str) -> AgentTurn:
        kwargs: dict[str, Any] = dict(
            model=self.model,
            max_tokens=700,
            system=[
                {
                    "type": "text",
                    "text": self.system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_message}],
            output_config={"format": {"type": "json_schema", "schema": TURN_SCHEMA}},
        )
        # Sonnet 5+ defaults to adaptive thinking when the field is omitted,
        # which adds latency/cost we don't need for a short structured turn.
        # Haiku 4.5 has no thinking unless explicitly enabled, so this is a
        # no-op there.
        if not self.model.startswith("claude-haiku"):
            kwargs["thinking"] = {"type": "disabled"}

        response = self._client.messages.create(**kwargs)

        text_block = next(b for b in response.content if b.type == "text")
        payload = json.loads(text_block.text)

        usage = TokenUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cache_read_tokens=getattr(response.usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_tokens=getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
        )
        return AgentTurn(
            reasoning=payload["reasoning"],
            action=payload["action"],
            terms=payload.get("terms") if payload["action"] == "propose" else None,
            usage=usage,
        )


_ACCEPT_REASONS = {
    "founder": "These terms are workable given my situation -- further back-and-forth risks the deal for marginal gains.",
    "vc": "This is within the range I'm comfortable investing at, and I don't want to lose the deal by dragging it out.",
}
_WALK_REASONS = {
    "founder": "The gap between us is too wide relative to my alternatives -- I'm better off pursuing another offer.",
    "vc": "The terms on offer don't clear my risk bar for this stage and portfolio fit -- passing on this one.",
}
_PROPOSE_REASONS = {
    "founder": "Countering to protect valuation and founder control while still moving toward a deal.",
    "vc": "Countering to improve downside protection while keeping the deal live.",
}


class MockAgent(BaseAgent):
    """Deterministic-ish templated agent for the dry-run pipeline. Nudges
    terms toward the agent's own preference each round and occasionally
    accepts or walks away, so mock-mode transcripts exercise the same code
    paths (deal / no-deal / early-accept / full-length) as real runs."""

    def __init__(self, role: str, system_prompt: str, model: str, seed: int | None = None):
        super().__init__(role, system_prompt, model)
        self._rng = random.Random(seed)

    def get_turn(self, user_message: str) -> AgentTurn:
        state = json.loads(user_message)
        round_number = state["round_number"]
        current_terms = state.get("current_terms")
        is_opening = current_terms is None

        if is_opening:
            terms = self._opening_terms()
            return AgentTurn(
                reasoning=f"Opening offer reflecting my starting position (round {round_number}).",
                action="propose",
                terms=terms,
                usage=TokenUsage(),
            )

        # Decide whether to accept, walk, or counter based on round pressure.
        closeness = min(round_number / 5.0, 1.0)
        roll = self._rng.random()
        if closeness > 0.5 and roll < 0.15 + 0.25 * closeness:
            return AgentTurn(
                reasoning=_ACCEPT_REASONS[self.role],
                action="accept",
                terms=None,
                usage=TokenUsage(),
            )
        if closeness > 0.7 and roll > 0.93:
            return AgentTurn(
                reasoning=_WALK_REASONS[self.role],
                action="walk_away",
                terms=None,
                usage=TokenUsage(),
            )

        new_terms = self._counter(current_terms, closeness)
        return AgentTurn(
            reasoning=_PROPOSE_REASONS[self.role],
            action="propose",
            terms=new_terms,
            usage=TokenUsage(),
        )

    def _opening_terms(self) -> dict[str, Any]:
        if self.role == "vc":
            return {
                "pre_money_valuation_usd": 6_000_000,
                "equity_percentage": 20.0,
                "liquidation_preference_multiple": 1.5,
                "liquidation_participating": True,
                "board_seats_founder": 1,
                "board_seats_investor": 2,
                "board_seats_independent": 1,
                "option_pool_percentage": 15.0,
                "vesting_years": 4,
                "vesting_cliff_months": 12,
                "pro_rata_rights": True,
                "anti_dilution": "full_ratchet",
            }
        return {
            "pre_money_valuation_usd": 12_000_000,
            "equity_percentage": 10.0,
            "liquidation_preference_multiple": 1.0,
            "liquidation_participating": False,
            "board_seats_founder": 3,
            "board_seats_investor": 1,
            "board_seats_independent": 1,
            "option_pool_percentage": 10.0,
            "vesting_years": 4,
            "vesting_cliff_months": 12,
            "pro_rata_rights": False,
            "anti_dilution": "broad_based_weighted_average",
        }

    _INTEGER_FIELDS = {"board_seats_founder", "board_seats_investor", "board_seats_independent"}

    def _counter(self, current: dict[str, Any], closeness: float) -> dict[str, Any]:
        """Move numeric terms a fraction of the way toward this agent's
        preferred opening, simulating convergence."""
        target = self._opening_terms()
        step = 0.2 + 0.3 * closeness
        new = dict(current)

        def is_number(v: Any) -> bool:
            return isinstance(v, (int, float)) and not isinstance(v, bool)

        for field in TERM_FIELDS:
            old_val, target_val = current.get(field), target.get(field)
            if is_number(old_val) and is_number(target_val):
                moved = old_val + (target_val - old_val) * step
                new[field] = round(moved) if field in self._INTEGER_FIELDS else round(moved, 2)
        # occasionally flip a boolean/enum term toward preference
        if self._rng.random() < 0.3:
            new["liquidation_participating"] = target["liquidation_participating"]
        if self._rng.random() < 0.3:
            new["pro_rata_rights"] = target["pro_rata_rights"]
        return new


def build_agent(role: str, system_prompt: str, model: str, mock_mode: bool, api_key: str | None = None, seed: int | None = None) -> BaseAgent:
    if mock_mode:
        return MockAgent(role, system_prompt, model, seed=seed)
    return RealAgent(role, system_prompt, model, api_key=api_key)
