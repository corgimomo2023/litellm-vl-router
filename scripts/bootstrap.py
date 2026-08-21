#!/usr/bin/env python3
"""Create an example LiteLLM user, team, and restricted virtual key."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, TextIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PUBLIC_MODEL = "DeepSeek-v4-vl"


class BootstrapError(RuntimeError):
    """Raised when a LiteLLM management endpoint rejects the bootstrap request."""


def _admin_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        normalized = normalized[:-3]
    return normalized


def _post(base_url: str, master_key: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = Request(
        f"{_admin_base_url(base_url)}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {master_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        raise BootstrapError(f"LiteLLM {path} failed with HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise BootstrapError(f"LiteLLM {path} request failed: {exc}") from exc


def bootstrap(base_url: str, master_key: str, *, output: TextIO = sys.stdout) -> dict[str, str]:
    """Create example budgeted resources and print the generated key exactly once."""
    user = _post(
        base_url,
        master_key,
        "/user/new",
        {
            "user_email": "example-user@example.invalid",
            "user_alias": "example-user",
            "max_budget": 25,
            "budget_duration": "30d",
            "models": [PUBLIC_MODEL],
            "auto_create_key": False,
        },
    )
    user_id = str(user["user_id"])
    print(f"Created user_id: {user_id}", file=output)

    team = _post(
        base_url,
        master_key,
        "/team/new",
        {
            "team_alias": "example-team",
            "models": [PUBLIC_MODEL],
            "members_with_roles": [{"user_id": user_id, "role": "user"}],
            "max_budget": 100,
            "budget_duration": "30d",
        },
    )
    team_id = str(team["team_id"])
    print(f"Created team_id: {team_id}", file=output)

    key = _post(
        base_url,
        master_key,
        "/key/generate",
        {
            "key_alias": "example-deepseek-v4-vl-key",
            "user_id": user_id,
            "team_id": team_id,
            "models": [PUBLIC_MODEL],
            "max_budget": 25,
            "budget_duration": "30d",
        },
    )
    virtual_key = str(key["key"])
    print("Created virtual key (shown only now; store it securely):", file=output)
    print(virtual_key, file=output)
    return {"user_id": user_id, "team_id": team_id, "virtual_key": virtual_key}


def main() -> int:
    base_url = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000")
    master_key = os.environ.get("LITELLM_MASTER_KEY")
    if not master_key:
        print("LITELLM_MASTER_KEY is required", file=sys.stderr)
        return 2
    try:
        bootstrap(base_url, master_key)
    except (BootstrapError, KeyError, ValueError) as exc:
        print(f"Bootstrap failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
