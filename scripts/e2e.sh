#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

if [ ! -f .env ]; then
  echo ".env is missing. Copy .env.example and set local secrets first." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

COMPOSE="docker compose -f compose.yaml -f compose.test.yaml"
cleanup() {
  $COMPOSE down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

$COMPOSE up -d --build --wait

BASE="http://127.0.0.1:${LITELLM_PORT:-4000}/v1"
AUTH="Authorization: Bearer ${LITELLM_MASTER_KEY}"

text_response=$(curl -fsS "$BASE/chat/completions" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-flash-vl","messages":[{"role":"user","content":"write hello world"}]}')

vision_response=$(curl -fsS "$BASE/chat/completions" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-pro-vl","messages":[{"role":"user","content":[{"type":"text","text":"what is shown?"},{"type":"image_url","image_url":{"url":"data:image/png;base64,AAAA"}}]}]}')

post_vision_text_response=$(curl -fsS "$BASE/chat/completions" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-flash-vl","messages":[{"role":"user","content":[{"type":"text","text":"what is shown?"},{"type":"image_url","image_url":{"url":"data:image/png;base64,AAAA"}}]},{"role":"assistant","content":"An error screenshot."},{"role":"user","content":"Now inspect package.json."}]}')

models_response=$(curl -fsS "$BASE/models" -H "$AUTH")

TEXT_RESPONSE=$text_response VISION_RESPONSE=$vision_response POST_VISION_TEXT_RESPONSE=$post_vision_text_response MODELS_RESPONSE=$models_response \
python3 - <<'PY'
import json
import os

text = json.loads(os.environ["TEXT_RESPONSE"])
vision = json.loads(os.environ["VISION_RESPONSE"])
post_vision_text = json.loads(os.environ["POST_VISION_TEXT_RESPONSE"])
models = json.loads(os.environ["MODELS_RESPONSE"])

text_content = text["choices"][0]["message"]["content"]
vision_content = vision["choices"][0]["message"]["content"]
post_vision_text_content = post_vision_text["choices"][0]["message"]["content"]
model_ids = {item["id"] for item in models["data"]}

assert "provider=deepseek" in text_content, text_content
assert "provider=qwen" in vision_content, vision_content
assert "provider=deepseek" in post_vision_text_content, post_vision_text_content
assert {"deepseek-v4-flash-vl", "deepseek-v4-pro-vl"} <= model_ids, model_ids

print("E2E PASS: text -> DeepSeek")
print("E2E PASS: current image input -> Qwen")
print("E2E PASS: old image plus latest text turn -> DeepSeek")
print("E2E PASS: both public Cline model IDs are listed")
PY
