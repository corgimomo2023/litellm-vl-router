"""LiteLLM proxy hook that sends current-turn image inputs to GPT Luna."""

from __future__ import annotations

from typing import Any

from litellm.integrations.custom_logger import CustomLogger

from app.routing import route_model


class VisionRoutingHandler(CustomLogger):
    async def async_pre_call_hook(
        self,
        user_api_key_dict: Any,
        cache: Any,
        data: dict[str, Any],
        call_type: str,
    ) -> dict[str, Any]:
        original_model = str(data.get("model", ""))
        selected_model = route_model(data, call_type=call_type)

        if selected_model != original_model:
            data["model"] = selected_model
            metadata = dict(data.get("metadata") or {})
            metadata.update(
                {
                    "vl_router_original_model": original_model,
                    "vl_router_selected_model": selected_model,
                    "vl_router_reason": "vision_input",
                }
            )
            data["metadata"] = metadata

        return data


vl_router = VisionRoutingHandler()
