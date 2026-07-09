"""Cost-control cap enforcement. Both single-negotiation and batch entry
points must call these before spending any money -- this is the one place
the "refuse above N without --override" policy is enforced."""
from __future__ import annotations

from app.config import get_settings


class CapExceededError(ValueError):
    pass


def validate_max_rounds(max_rounds: int, override: bool) -> None:
    hard_cap = get_settings().rounds.hard_cap
    if max_rounds > hard_cap and not override:
        raise CapExceededError(
            f"max_rounds={max_rounds} exceeds the hard cap of {hard_cap}. "
            f"Pass override_caps=true to run anyway."
        )
    if max_rounds < 1:
        raise CapExceededError("max_rounds must be at least 1")


def validate_batch_size(size: int, override: bool) -> None:
    hard_cap = get_settings().batch.hard_cap
    if size > hard_cap and not override:
        raise CapExceededError(
            f"batch size={size} exceeds the hard cap of {hard_cap}. "
            f"Pass override_caps=true to run anyway."
        )
    if size < 1:
        raise CapExceededError("batch size must be at least 1")


def validate_model(model: str) -> None:
    allowed = get_settings().model.allowed
    if model not in allowed:
        raise CapExceededError(f"model={model!r} is not in the allowed model list: {allowed}")
