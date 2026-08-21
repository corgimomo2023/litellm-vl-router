#!/usr/bin/env bash
set -euo pipefail

RENDER_ONLY=""
if [[ "${1:-}" == "--render-only" && $# -eq 2 ]]; then
  RENDER_ONLY="$2"
elif [[ $# -ne 0 ]]; then
  printf 'Usage: %s [--render-only OUTPUT]\n' "$0" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE="$PROJECT_DIR/deploy/nginx/litellm-proxy.conf.template"
DOMAIN="${DOMAIN:-llmproxy.example.com}"
SSL_CERT="${SSL_CERT:-/etc/ssl/certs/llmproxy-origin.crt}"
SSL_KEY="${SSL_KEY:-/etc/ssl/private/llmproxy-origin.key}"
SITE_NAME="${SITE_NAME:-litellm-proxy}"
DEST="/etc/nginx/sites-available/$SITE_NAME"
LINK="/etc/nginx/sites-enabled/$SITE_NAME"

if [[ ! "$DOMAIN" =~ ^[A-Za-z0-9][A-Za-z0-9.-]*[A-Za-z0-9]$ ]]; then
  printf 'Invalid DOMAIN: use a DNS hostname without whitespace or directives\n' >&2
  exit 2
fi
for name in SSL_CERT SSL_KEY; do
  value="${!name}"
  if [[ ! "$value" =~ ^/[A-Za-z0-9._/-]+$ ]]; then
    printf 'Invalid %s: use an absolute path without whitespace or directives\n' "$name" >&2
    exit 2
  fi
done
if [[ ! "$SITE_NAME" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  printf 'Invalid SITE_NAME: use letters, numbers, dot, underscore, or hyphen\n' >&2
  exit 2
fi

TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

if [[ ! -f "$SOURCE" ]]; then
  printf 'Missing nginx template: %s\n' "$SOURCE" >&2
  exit 1
fi

python3 - "$SOURCE" "$TMP_FILE" "$DOMAIN" "$SSL_CERT" "$SSL_KEY" <<'PY'
from pathlib import Path
import sys
source, destination, domain, certificate, key = sys.argv[1:]
text = Path(source).read_text()
replacements = {
    "__DOMAIN__": domain,
    "__SSL_CERT__": certificate,
    "__SSL_KEY__": key,
}
for token, value in replacements.items():
    text = text.replace(token, value)
for token in replacements:
    if token in text:
        raise SystemExit(f"Unresolved template placeholder: {token}")
Path(destination).write_text(text)
PY

if [[ -n "$RENDER_ONLY" ]]; then
  install -m 0644 "$TMP_FILE" "$RENDER_ONLY"
  printf 'Rendered nginx config: %s\n' "$RENDER_ONLY"
  exit 0
fi

# Ask for the local sudo password once, interactively.
sudo -v
sudo install -o root -g root -m 0644 "$TMP_FILE" "$DEST"
sudo ln -sfn "$DEST" "$LINK"
sudo nginx -t
sudo systemctl reload nginx

printf 'Installed and reloaded nginx for %s\n' "$DOMAIN"
printf 'Public checks:\n'
curl -sS --max-time 20 -o /dev/null -w '  root HTTP=%{http_code}\n' "https://$DOMAIN/"
curl -sS --max-time 20 -o /dev/null -w '  ui HTTP=%{http_code}\n' "https://$DOMAIN/ui/"
curl -sS --max-time 20 -o /dev/null -w '  unauth models HTTP=%{http_code}\n' "https://$DOMAIN/v1/models"
