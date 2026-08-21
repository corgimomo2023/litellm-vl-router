# LiteLLM DeepSeek V4 VL Router

Production-style **placeholder deployment** for a single public OpenAI-compatible model ID: `DeepSeek-v4-vl`.

- Text/code requests use an internal DeepSeek V4 Flash endpoint through the OpenCode Go backend.
- Images in the latest user turn route to the internal `_internal-gpt-luna-vision` alias.
- Historical images are ignored after a newer text-only user turn; tool continuations keep the current image turn on vision.
- PostgreSQL stores users, teams, virtual keys, budgets, and spend logs; Redis supports auth cache and router state.

> All committed upstream credentials, URLs, and model names are placeholders. This repository does **not** claim that real upstream calls work until you replace and verify them.

## Architecture

```text
OpenAI client -> LiteLLM :4000 -> DeepSeek-v4-vl
                                | text/code -> OpenCode Go / DeepSeek V4 Flash
                                ` image     -> GPT Luna vision
               |-> PostgreSQL 16
               `-> Redis 7
```

The Compose stack binds LiteLLM to localhost only. PostgreSQL and Redis have no host ports. All services include health checks, resource limits sized below a 6 GB host budget, rotating JSON logs, and named data volumes.

## Configure and start

```bash
cp .env.example .env
openssl rand -hex 32  # generate distinct master/salt/database/Redis secrets
# Edit .env and replace every change-me / replace-me placeholder.
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

Built-in admin UI: <http://127.0.0.1:4000/ui>. Sign in with the master-key credentials required by your pinned LiteLLM image.

Client settings:

| Setting | Value |
|---|---|
| Base URL | `http://127.0.0.1:4000/v1` |
| API key | a LiteLLM virtual key (preferred) or master key |
| Model | `DeepSeek-v4-vl` (case-sensitive) |

## Placeholder upstream settings

```dotenv
OPENCODE_GO_API_BASE=https://replace-me-opencode-go.invalid/v1
OPENCODE_GO_API_KEY=change-me-opencode-go-key
OPENCODE_GO_MODEL=openai/replace-me-deepseek-v4-flash
GPT_LUNA_API_BASE=https://replace-me-gpt-luna.invalid/v1
GPT_LUNA_API_KEY=change-me-gpt-luna-key
GPT_LUNA_MODEL=openai/replace-me-gpt-luna-vision
```

Keep `LITELLM_SALT_KEY` stable after initial database setup. Changing it can make encrypted database values unreadable.

## Bootstrap example tenant

After LiteLLM is healthy, create an example user, team, and virtual key restricted to `DeepSeek-v4-vl`:

```bash
export LITELLM_BASE_URL=http://127.0.0.1:4000
export LITELLM_MASTER_KEY='your-master-key'
python3 scripts/bootstrap.py
```

The stdlib-only script applies example 30-day budgets, prints created identifiers, and prints the generated virtual key only in the successful creation response. Store it immediately; rerunning creates another example tenant/key.

## Logging and sensitive content

JSON logs and spend logs are enabled. `turn_off_message_logging: false` plus `store_prompts_in_spend_logs: true` intentionally retain request/response content for audit and spend analysis. Payloads can contain source code, images, PII, credentials, or other sensitive material. Restrict database/log access, protect backups, define retention, and disable content logging if your policy does not permit it. User API-key metadata is redacted.

## Smoke and tests

Health and model-list checks are safe in placeholder mode:

```bash
LITELLM_MASTER_KEY='your-master-key' ./scripts/smoke.sh
```

An optional upstream chat runs only with both explicit switches:

```bash
PLACEHOLDER_MODE=false RUN_CHAT_REQUEST=1 LITELLM_MASTER_KEY='your-master-key' ./scripts/smoke.sh
```

Do not disable placeholder mode until real upstream configuration is installed. Unit/config tests and Compose validation:

```bash
uv sync --extra test
uv run pytest -q
cp .env.example .env
docker compose config --quiet
docker compose -f compose.yaml -f compose.test.yaml config --quiet
```

Mock Docker E2E (no paid upstream calls) verifies text → OpenCode Go mock, current image → GPT Luna mock, stale image → OpenCode Go mock, the sole public alias, and `scripts/bootstrap.py` user/team/key endpoints:

```bash
./scripts/e2e.sh
```

## TLS reverse proxy

The repository includes a generic Nginx template. Supply the public hostname and
certificate paths at install time; do not commit deployment-specific domains or
private keys.

```bash
DOMAIN=llmproxy.example.com \
SSL_CERT=/etc/ssl/certs/llmproxy-origin.crt \
SSL_KEY=/etc/ssl/private/llmproxy-origin.key \
./deploy/install-nginx.sh
```

The installer renders the template, runs `nginx -t`, reloads Nginx, and performs
public root, UI, and unauthenticated model-list checks. It prompts for local sudo
authorization and never reads or copies the private-key contents into the repository.

## Operations

```bash
docker compose logs -f litellm
docker compose down          # preserve named volumes
docker compose down -v       # permanently delete DB/Redis data
```

Do not expose port 4000 directly to a network. Put a TLS reverse proxy and appropriate access controls in front of it.
