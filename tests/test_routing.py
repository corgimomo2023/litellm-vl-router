import pytest

from app.routing import QWEN_VISION_ALIAS, contains_vision_input, route_model


@pytest.mark.parametrize(
    "payload",
    [
        {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Explain this screenshot"},
                        {
                            "type": "image_url",
                            "image_url": {"url": "data:image/png;base64,AAAA"},
                        },
                    ],
                }
            ]
        },
        {
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Read this image"},
                        {"type": "input_image", "image_url": "https://example.com/a.png"},
                    ],
                }
            ]
        },
    ],
)
def test_detects_vision_for_chat_and_responses_payloads(payload):
    assert contains_vision_input(payload) is True


def test_plain_code_request_is_not_vision():
    payload = {
        "messages": [
            {"role": "user", "content": "Fix this Python function: def add(a,b): ..."}
        ]
    }

    assert contains_vision_input(payload) is False


def test_old_screenshot_does_not_keep_routing_new_text_turns_to_qwen():
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Explain this screenshot"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "https://example.com/old.png"},
                    },
                ],
            },
            {"role": "assistant", "content": "The screenshot shows an error."},
            {"role": "user", "content": "Now inspect package.json and fix the code."},
        ]
    }

    assert contains_vision_input(payload) is False
    assert (
        route_model(payload | {"model": "deepseek-v4-flash-vl"}, "acompletion")
        == "deepseek-v4-flash-vl"
    )


def test_tool_continuation_of_latest_image_turn_stays_on_vision_model():
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Inspect this screenshot"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "https://example.com/current.png"},
                    },
                ],
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "{}"},
        ]
    }

    assert contains_vision_input(payload) is True


@pytest.mark.parametrize(
    "public_model",
    ["deepseek-v4-flash-vl", "deepseek-v4-pro-vl"],
)
@pytest.mark.parametrize("call_type", ["completion", "acompletion"])
def test_both_public_models_route_vision_to_qwen(public_model, call_type):
    payload = {
        "model": public_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": "https://example.com/ui.png"}}
                ],
            }
        ],
    }

    assert route_model(payload, call_type=call_type) == QWEN_VISION_ALIAS


@pytest.mark.parametrize(
    "public_model",
    ["deepseek-v4-flash-vl", "deepseek-v4-pro-vl"],
)
def test_text_requests_keep_the_selected_deepseek_model(public_model):
    payload = {
        "model": public_model,
        "messages": [{"role": "user", "content": "Implement a rate limiter"}],
    }

    assert route_model(payload, call_type="completion") == public_model


def test_non_chat_calls_are_not_redirected_to_vision_model():
    payload = {
        "model": "deepseek-v4-pro-vl",
        "prompt": "Generate an image of a corgi",
    }

    assert route_model(payload, call_type="image_generation") == "deepseek-v4-pro-vl"


def test_unknown_model_is_not_rewritten():
    payload = {
        "model": "another-model",
        "messages": [
            {
                "role": "user",
                "content": [{"type": "image_url", "image_url": {"url": "https://example.com/a.png"}}],
            }
        ],
    }

    assert route_model(payload, call_type="completion") == "another-model"
