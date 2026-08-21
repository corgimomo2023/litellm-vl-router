#!/usr/bin/env sh
set -eu

BASE_URL=${LITELLM_BASE_URL:-http://127.0.0.1:4000}
MASTER_KEY=${LITELLM_MASTER_KEY:?set LITELLM_MASTER_KEY}
PLACEHOLDER_MODE=${PLACEHOLDER_MODE:-true}
RUN_CHAT_REQUEST=${RUN_CHAT_REQUEST:-0}
AUTH="Authorization: Bearer ${MASTER_KEY}"

echo "Health:"
curl -fsS "${BASE_URL%/}/health/liveliness"
printf '\nModels:\n'
curl -fsS "${BASE_URL%/}/v1/models" -H "$AUTH"
printf '\n'

if [ "$RUN_CHAT_REQUEST" != "1" ]; then
  echo "SKIP: optional chat disabled (set RUN_CHAT_REQUEST=1 to enable)."
elif [ "$PLACEHOLDER_MODE" = "true" ] || [ "$PLACEHOLDER_MODE" = "1" ]; then
  echo "SKIP: placeholder mode prevents paid/upstream chat calls. Set real upstream credentials and PLACEHOLDER_MODE=false explicitly."
else
  echo "Optional chat:"
  curl -fsS "${BASE_URL%/}/v1/chat/completions" \
    -H "$AUTH" \
    -H "Content-Type: application/json" \
    -d '{"model":"DeepSeek-v4-vl","messages":[{"role":"user","content":"Reply with: smoke ok"}]}'
  printf '\n'
fi
