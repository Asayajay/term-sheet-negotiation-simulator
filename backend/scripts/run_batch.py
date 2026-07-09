#!/usr/bin/env python
"""CLI batch runner. Prints a cost estimate and requires interactive
confirmation before spending any money (skipped automatically in --mock mode,
where the estimate is always $0).

Usage:
    python scripts/run_batch.py --size 10 --max-rounds 6 --model claude-haiku-4-5
    python scripts/run_batch.py --size 5 --mock
    python scripts/run_batch.py --size 50 --override-caps --yes
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.batch import estimate_batch, run_batch
from app.config import get_settings
from app.limits import CapExceededError, validate_batch_size, validate_max_rounds, validate_model


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Run a batch of term sheet negotiations.")
    parser.add_argument("--size", type=int, default=settings.batch.default_size_cap)
    parser.add_argument("--model", default=settings.model.default, choices=settings.model.allowed)
    parser.add_argument("--max-rounds", type=int, default=settings.rounds.default_max_rounds)
    parser.add_argument("--mock", action="store_true", help="Fake responses, zero API cost.")
    parser.add_argument("--override-caps", action="store_true", help="Allow exceeding the configured hard caps.")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    try:
        validate_model(args.model)
        validate_max_rounds(args.max_rounds, args.override_caps)
        validate_batch_size(args.size, args.override_caps)
    except CapExceededError as exc:
        print(f"Refusing to run: {exc}", file=sys.stderr)
        sys.exit(1)

    est = estimate_batch(args.model, args.max_rounds, args.size)
    if args.mock:
        print(f"MOCK MODE: {args.size} negotiations x up to {args.max_rounds} rounds -- $0.00 (no API calls)")
    else:
        print(
            f"Estimated cost for {args.size} negotiations x up to {args.max_rounds} rounds "
            f"on {args.model}: ${est.estimated_cost_usd:.4f}"
        )
        print("(This is a ceiling estimate assuming no early accepts -- actual cost is usually lower.)")
        if not args.yes:
            reply = input("Proceed? [y/N] ").strip().lower()
            if reply not in ("y", "yes"):
                print("Aborted.")
                sys.exit(0)

    def progress(done: int, total: int, result) -> None:
        print(f"[{done}/{total}] outcome={result.outcome} cost=${result.total_cost_usd:.4f} rounds={len(result.rounds)}")

    batch_id = run_batch(
        size=args.size,
        model=args.model,
        max_rounds=args.max_rounds,
        mock_mode=args.mock,
        override_caps=args.override_caps,
        api_key=settings.anthropic_api_key,
        seed=args.seed,
        on_progress=progress,
    )
    print(f"\nBatch complete. batch_id={batch_id}")


if __name__ == "__main__":
    main()
