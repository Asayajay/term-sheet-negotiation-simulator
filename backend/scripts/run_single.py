#!/usr/bin/env python
"""CLI single on-demand negotiation trigger. Runs one negotiation directly
(no API server needed) and prints the transcript round by round.

Usage:
    python scripts/run_single.py --mock
    python scripts/run_single.py --model claude-haiku-4-5 --max-rounds 6
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.cost import estimate_negotiation_cost_usd
from app.database import SessionLocal
from app.engine import run_negotiation
from app.limits import CapExceededError, validate_max_rounds, validate_model
from app.models import Negotiation, Round
from app.personas import random_founder_params, random_vc_params


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Run a single term sheet negotiation.")
    parser.add_argument("--model", default=settings.model.default, choices=settings.model.allowed)
    parser.add_argument("--max-rounds", type=int, default=settings.rounds.default_max_rounds)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--override-caps", action="store_true")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--persist", action="store_true", help="Save to the configured database.")
    args = parser.parse_args()

    try:
        validate_model(args.model)
        validate_max_rounds(args.max_rounds, args.override_caps)
    except CapExceededError as exc:
        print(f"Refusing to run: {exc}", file=sys.stderr)
        sys.exit(1)

    founder_params = random_founder_params()
    vc_params = random_vc_params()

    if not args.mock:
        est = estimate_negotiation_cost_usd(args.model, args.max_rounds)
        print(f"Estimated cost ceiling: ${est:.4f} on {args.model}, up to {args.max_rounds} rounds\n")

    def on_round(r):
        actor = r.actor.upper()
        print(f"--- round {r.round_number} | {actor} | {r.action} ---")
        print(f"reasoning: {r.reasoning}")
        if r.terms:
            print(f"terms: {json.dumps(r.terms, indent=2)}")
        if r.diff:
            print(f"changed: {list(r.diff.keys())}")
        print(f"tokens: in={r.input_tokens} out={r.output_tokens} cache_read={r.cache_read_tokens} cost=${r.cost_usd:.5f}\n")

    result = run_negotiation(
        model=args.model,
        max_rounds=args.max_rounds,
        founder_params=founder_params,
        vc_params=vc_params,
        mock_mode=args.mock,
        api_key=settings.anthropic_api_key,
        seed=args.seed,
        on_round=on_round,
    )

    print("=" * 60)
    print(f"OUTCOME: {result.outcome}")
    if result.error:
        print(f"ERROR: {result.error}")
    if result.final_terms:
        print(f"FINAL TERMS: {json.dumps(result.final_terms, indent=2)}")
    print(f"Rounds to close: {result.rounds_to_close}")
    print(
        f"TOTAL: input_tokens={result.total_input_tokens} output_tokens={result.total_output_tokens} "
        f"cost=${result.total_cost_usd:.5f}"
    )

    if args.persist:
        db = SessionLocal()
        try:
            neg = Negotiation(
                model=args.model,
                max_rounds=args.max_rounds,
                mock_mode=args.mock,
                founder_params=founder_params,
                vc_params=vc_params,
                status="failed" if result.outcome == "error" else "completed",
                outcome=result.outcome,
                final_terms=result.final_terms,
                final_valuation=(result.final_terms or {}).get("pre_money_valuation_usd"),
                final_equity_pct=(result.final_terms or {}).get("equity_percentage"),
                final_liquidation_multiple=(result.final_terms or {}).get("liquidation_preference_multiple"),
                final_liquidation_participating=(result.final_terms or {}).get("liquidation_participating"),
                rounds_to_close=result.rounds_to_close,
                total_input_tokens=result.total_input_tokens,
                total_output_tokens=result.total_output_tokens,
                total_cost_usd=result.total_cost_usd,
                error=result.error,
            )
            db.add(neg)
            db.commit()
            for r in result.rounds:
                db.add(
                    Round(
                        negotiation_id=neg.id,
                        sequence=r.sequence,
                        round_number=r.round_number,
                        actor=r.actor,
                        action=r.action,
                        terms=r.terms,
                        reasoning=r.reasoning,
                        diff=r.diff,
                        input_tokens=r.input_tokens,
                        output_tokens=r.output_tokens,
                        cache_read_tokens=r.cache_read_tokens,
                        cost_usd=r.cost_usd,
                    )
                )
            db.commit()
            print(f"\nPersisted as negotiation_id={neg.id}")
        finally:
            db.close()


if __name__ == "__main__":
    from app.database import init_db

    init_db()
    main()
