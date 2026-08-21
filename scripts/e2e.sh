#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

if [ ! -f .env ]; then
  echo ".env is missing. Copy .env.example to .env; mock E2E overrides all upstream placeholders." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

COMPOSE_PROJECT_NAME=litellm-vl-router-e2e
LITELLM_PORT=${E2E_LITELLM_PORT:-14000}
export LITELLM_PORT

compose() {
  docker compose -p "$COMPOSE_PROJECT_NAME" -f compose.yaml -f compose.test.yaml "$@"
}

cleanup() {
  compose down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

compose up -d --build --wait

BASE_URL="http://127.0.0.1:${LITELLM_PORT:-4000}"
BASE="$BASE_URL/v1"
AUTH="Authorization: Bearer ${LITELLM_MASTER_KEY}"

text_response=$(curl -fsS "$BASE/chat/completions" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-v4-vl","messages":[{"role":"user","content":"write hello world"}]}')

vision_response=$(curl -fsS "$BASE/chat/completions" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-v4-vl","messages":[{"role":"user","content":[{"type":"text","text":"what is shown?"},{"type":"image_url","image_url":{"url":"data:image/png;base64,AAAA"}}]}]}')

stale_image_response=$(curl -fsS "$BASE/chat/completions" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"model":"DeepSeek-v4-vl","messages":[{"role":"user","content":[{"type":"text","text":"what is shown?"},{"type":"image_url","image_url":{"url":"data:image/png;base64,AAAA"}}]},{"role":"assistant","content":"An error screenshot."},{"role":"user","content":"Now inspect package.json."}]}')

models_response=$(curl -fsS "$BASE/models" -H "$AUTH")
bootstrap_output=$(LITELLM_BASE_URL="$BASE_URL" LITELLM_MASTER_KEY="$LITELLM_MASTER_KEY" python3 scripts/bootstrap.py)

TEXT_RESPONSE=$text_response VISION_RESPONSE=$vision_response STALE_IMAGE_RESPONSE=$stale_image_response MODELS_RESPONSE=$models_response BOOTSTRAP_OUTPUT=$bootstrap_output \
python3 - <<'PY'
import json
import os

text = json.loads(os.environ["TEXT_RESPONSE"])
vision = json.loads(os.environ["VISION_RESPONSE"])
stale = json.loads(os.environ["STALE_IMAGE_RESPONSE"])
models = json.loads(os.environ["MODELS_RESPONSE"])
bootstrap = os.environ["BOOTSTRAP_OUTPUT"]

content = lambda response: response["choices"][0]["message"]["content"]
assert "provider=opencode-go" in content(text), content(text)
assert "provider=gpt-luna" in content(vision), content(vision)
assert "provider=opencode-go" in content(stale), content(stale)
model_ids = {item["id"] for item in models["data"]}
public_ids = {model_id for model_id in model_ids if not model_id.startswith("_internal-")}
assert public_ids == {"DeepSeek-v4-vl"}, model_ids
assert "Created user_id:" in bootstrap, bootstrap
assert "Created team_id:" in bootstrap, bootstrap
assert "Created virtual key" in bootstrap, bootstrap

print("E2E PASS: text -> OpenCode Go mock")
print("E2E PASS: current-turn image -> GPT Luna mock")
print("E2E PASS: stale historical image -> OpenCode Go mock")
print("E2E PASS: exactly one public model ID")
print("E2E PASS: bootstrap user/team/key endpoints")
PY
