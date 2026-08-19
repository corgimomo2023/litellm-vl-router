# LiteLLM VL Router

A Docker Compose LiteLLM gateway for Cline with two public model IDs:

- `deepseek-v4-flash-vl`
- `deepseek-v4-pro-vl`

Text and code requests use the selected DeepSeek model. When Cline's latest user turn includes an image, a LiteLLM `async_pre_call_hook` routes that turn (including its tool-result continuations) to Qwen 3.5 Flash for vision understanding. A historical screenshot does not keep later text-only user turns pinned to Qwen.

> The `-vl` names are gateway aliases. They do not claim that the upstream DeepSeek models are vision models.

## Architecture

```text
Cline (OpenAI Compatible)
  -> LiteLLM :4000
       -> text/code  -> DeepSeek V4 Flash or Pro
       -> image input -> Qwen 3.5 Flash
       -> PostgreSQL  -> keys, budgets, spend logs
       -> Redis       -> auth cache, routing state, optional response cache
```

## Quick start

```bash
cp .env.example .env
```

Edit `.env` and provide:

- `DEEPSEEK_API_KEY`
- `QWEN_API_KEY`
- strong, unique values for `LITELLM_MASTER_KEY`, `LITELLM_SALT_KEY`, `POSTGRES_PASSWORD`, and `REDIS_PASSWORD`

Generate secrets with:

```bash
openssl rand -hex 32
```

Keep `LITELLM_SALT_KEY` stable after first startup. LiteLLM uses it to encrypt credentials stored in PostgreSQL.

Start the stack:

```bash
docker compose up -d --build
docker compose ps
```

Admin UI: <http://localhost:4000/ui>

- Username: `admin`
- Password: the value of `LITELLM_MASTER_KEY`

## Cline configuration

Choose **OpenAI Compatible**:

| Setting | Value |
|---|---|
| Base URL | `http://localhost:4000/v1` |
| API key | your `LITELLM_MASTER_KEY` or a LiteLLM virtual key |
| Model ID | `deepseek-v4-flash-vl` or `deepseek-v4-pro-vl` |

For shared use, create a LiteLLM virtual key instead of distributing the master key.

## Routing behavior

| Request | Selected upstream |
|---|---|
| Text/code using `deepseek-v4-flash-vl` | `DEEPSEEK_FLASH_MODEL` |
| Text/code using `deepseek-v4-pro-vl` | `DEEPSEEK_PRO_MODEL` |
| Either public model with `image_url` or `input_image` | `QWEN_VISION_MODEL` |
| Image generation endpoint | Not rewritten; this project handles image understanding, not image generation |

The internal Qwen alias is `_internal-qwen3.5-flash-vision`. Do not configure Cline to use it directly.

## Provider configuration

Defaults assume OpenAI-compatible APIs:

```dotenv
DEEPSEEK_API_BASE=https://api.deepseek.com/v1
DEEPSEEK_FLASH_MODEL=openai/deepseek-v4-flash
DEEPSEEK_PRO_MODEL=openai/deepseek-v4-pro

QWEN_API_BASE=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
QWEN_VISION_MODEL=openai/qwen3.5-flash
```

Change the Qwen API base for the Alibaba Cloud region tied to your key. Model IDs are environment variables because provider naming can change independently of this gateway.

## Verification

Unit tests:

```bash
uv sync --extra test
uv run pytest -q
```

Full Docker E2E using a local mock OpenAI provider, with no paid API calls:

```bash
./scripts/e2e.sh
```

The E2E test proves:

1. PostgreSQL, Redis, mock provider, and LiteLLM become healthy.
2. A text request stays on DeepSeek.
3. The same public model with an image routes to Qwen.
4. Both public model IDs are available through `/v1/models`.

## Operations

```bash
# Logs
docker compose logs -f litellm

# Stop without deleting data
docker compose down

# Stop and permanently delete DB/Redis volumes
docker compose down -v
```

The default port binding is localhost-only. Put a TLS reverse proxy and authentication controls in front before exposing it over a network.

## Files

```text
app/routing.py          Pure, tested routing rules
app/custom_handler.py   LiteLLM async_pre_call_hook
config.yaml             Models, Redis, DB, reliability settings
compose.yaml            LiteLLM + PostgreSQL + Redis
compose.test.yaml       Mock provider E2E overlay
```

## License

MIT
