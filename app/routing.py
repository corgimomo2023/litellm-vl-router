"""Pure routing rules shared by tests and the LiteLLM callback."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

PUBLIC_MODELS = frozenset(
    {
        "deepseek-v4-flash-vl",
        "deepseek-v4-pro-vl",
    }
)
QWEN_VISION_ALIAS = "_internal-qwen3.5-flash-vision"
_CHAT_CALL_TYPES = frozenset(
    {
        "completion",
        "acompletion",
        "responses",
        "aresponses",
    }
)
_IMAGE_PART_TYPES = frozenset({"image_url", "input_image", "image"})


def _walk(value: Any):
    """Yield every nested value from JSON-like mappings and sequences."""
    yield value
    if isinstance(value, Mapping):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for child in value:
            yield from _walk(child)


def _latest_user_scope(value: Any) -> Any:
    """Return the latest user turn, or the raw value for role-less Responses input."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return value

    for item in reversed(value):
        if isinstance(item, Mapping) and str(item.get("role", "")).lower() == "user":
            return item

    # Responses API can pass content parts directly without role wrappers.
    return value


def contains_vision_input(data: Mapping[str, Any]) -> bool:
    """Return True when the current user turn contains an image input part.

    Older screenshots are intentionally ignored after a newer text-only user turn.
    Tool-result continuations still see the latest user turn and stay on the same
    vision model until that turn completes.
    """
    request_content = {
        "messages": _latest_user_scope(data.get("messages", [])),
        "input": _latest_user_scope(data.get("input", [])),
    }
    for item in _walk(request_content):
        if not isinstance(item, Mapping):
            continue
        part_type = str(item.get("type", "")).lower()
        if part_type in _IMAGE_PART_TYPES:
            return True
    return False


def route_model(data: Mapping[str, Any], call_type: str) -> str:
    """Select an internal model while preserving unsupported/unknown requests."""
    selected_model = str(data.get("model", ""))
    if (
        call_type in _CHAT_CALL_TYPES
        and selected_model in PUBLIC_MODELS
        and contains_vision_input(data)
    ):
        return QWEN_VISION_ALIAS
    return selected_model
