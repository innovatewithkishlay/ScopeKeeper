"""Checks on what the model sends back through a tool call.

The model's tool-call arguments arrive as a plain dict decoded from JSON.
Nothing here trusts that dict until it's been checked. If a field is
missing, the wrong type, out of range, or not one of the allowed values,
validation fails with a clear message the model can react to - the tool
never silently accepts bad data.
"""

from typing import Any, Dict, List, Tuple

from models import (
    CLASSIFICATIONS,
    CONFIDENCE_LEVELS,
    MAX_DESCRIPTION_LENGTH,
    MAX_HOURS_ESTIMATE,
    MAX_ITEM_LENGTH,
    MAX_LIST_ITEMS,
    MAX_REASONING_LENGTH,
)


class ValidationError(Exception):
    pass


def _require_str(value: Any, field_name: str, max_len: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"'{field_name}' must be a non-empty string.")
    if len(value) > max_len:
        raise ValidationError(f"'{field_name}' is too long (max {max_len} characters).")
    return value.strip()


def _require_string_list(value: Any, field_name: str) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError(f"'{field_name}' must be a list of short strings.")
    if len(value) > MAX_LIST_ITEMS:
        raise ValidationError(f"'{field_name}' has too many items (max {MAX_LIST_ITEMS}).")
    cleaned = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValidationError(f"'{field_name}' must only contain non-empty strings.")
        if len(item) > MAX_ITEM_LENGTH:
            raise ValidationError(f"An item in '{field_name}' is too long (max {MAX_ITEM_LENGTH} characters).")
        cleaned.append(item.strip())
    return cleaned


def validate_log_request_args(args: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """Returns (True, cleaned_args) on success, or (False, {"message": ...})
    on failure. Never raises - callers get a structured result either way,
    so the agent loop can turn a failure into a tool result the model sees
    and can react to, instead of the whole run crashing."""
    try:
        description = _require_str(args.get("description"), "description", MAX_DESCRIPTION_LENGTH)

        hours_estimate = args.get("hours_estimate")
        if not isinstance(hours_estimate, (int, float)) or isinstance(hours_estimate, bool):
            raise ValidationError("'hours_estimate' must be a number.")
        if hours_estimate < 0 or hours_estimate > MAX_HOURS_ESTIMATE:
            raise ValidationError(f"'hours_estimate' must be between 0 and {MAX_HOURS_ESTIMATE}.")

        classification = args.get("classification")
        if classification not in CLASSIFICATIONS:
            raise ValidationError(f"'classification' must be one of {CLASSIFICATIONS}.")

        confidence = args.get("confidence")
        if confidence not in CONFIDENCE_LEVELS:
            raise ValidationError(f"'confidence' must be one of {CONFIDENCE_LEVELS}.")

        reasoning = _require_str(args.get("reasoning"), "reasoning", MAX_REASONING_LENGTH)

        affected_deliverables = _require_string_list(args.get("affected_deliverables"), "affected_deliverables")
        new_capabilities = _require_string_list(args.get("new_capabilities"), "new_capabilities")

        return True, {
            "description": description,
            "hours_estimate": float(hours_estimate),
            "classification": classification,
            "confidence": confidence,
            "reasoning": reasoning,
            "affected_deliverables": affected_deliverables,
            "new_capabilities": new_capabilities,
        }
    except ValidationError as exc:
        return False, {"message": str(exc)}
