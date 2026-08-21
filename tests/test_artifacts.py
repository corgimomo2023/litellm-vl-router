import os
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_smoke_placeholder_mode_skips_optional_chat(tmp_path):
    fake_curl = tmp_path / "curl"
    calls = tmp_path / "curl-calls"
    fake_curl.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$*\" >> {calls}\n"
        "case \"$*\" in *models*) printf '{\"data\":[{\"id\":\"DeepSeek-v4-vl\"}]}' ;; *) printf '{\"status\":\"ok\"}' ;; esac\n"
    )
    fake_curl.chmod(fake_curl.stat().st_mode | stat.S_IXUSR)
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "LITELLM_BASE_URL": "http://router.invalid",
        "LITELLM_MASTER_KEY": "master",
        "PLACEHOLDER_MODE": "true",
        "RUN_CHAT_REQUEST": "1",
    }

    result = subprocess.run(
        [str(ROOT / "scripts/smoke.sh")], env=env, text=True, capture_output=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert "SKIP" in result.stdout
    assert "placeholder" in result.stdout.lower()
    curl_calls = calls.read_text()
    assert "/health/liveliness" in curl_calls
    assert "/v1/models" in curl_calls
    assert "/chat/completions" not in curl_calls


def test_e2e_uses_an_isolated_compose_project_and_host_port():
    script = (ROOT / "scripts/e2e.sh").read_text()

    assert "COMPOSE_PROJECT_NAME=litellm-vl-router-e2e" in script
    assert "E2E_COMPOSE_PROJECT_NAME" not in script
    assert "E2E_LITELLM_PORT:-14000" in script
    assert 'docker compose -p "$COMPOSE_PROJECT_NAME"' in script
    assert "export LITELLM_PORT" in script


def test_public_deployment_artifacts_are_generic_and_verify_tls():
    names = [
        "README.md",
        ".env.example",
        "deploy/install-nginx.sh",
        "deploy/nginx/litellm-proxy.conf.template",
    ]
    combined = "\n".join((ROOT / name).read_text() for name in names)

    assert "/home/" not in combined
    assert "cloudflare/" not in combined.lower()
    assert "llmproxy.example.com" in combined
    assert "curl -k" not in combined
    assert "curl -4 -k" not in combined
    assert "return 301 https://__DOMAIN__$request_uri;" in combined
    assert "https://$host$request_uri" not in combined


def test_nginx_installer_rejects_unsafe_template_values():
    installer = ROOT / "deploy/install-nginx.sh"
    cases = [
        {"DOMAIN": "safe.example.com\nserver { listen 9999; }"},
        {"SSL_CERT": "/safe/cert.pem; include /tmp/unsafe.conf"},
        {"SSL_KEY": "relative/private.key"},
        {"SITE_NAME": "../unsafe"},
    ]

    for overrides in cases:
        result = subprocess.run(
            [str(installer)],
            env=os.environ | overrides,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode != 0
        assert "Invalid" in result.stderr


def test_nginx_installer_can_render_a_complete_config_without_sudo(tmp_path):
    installer = ROOT / "deploy/install-nginx.sh"
    rendered = tmp_path / "litellm-proxy.conf"
    env = os.environ | {
        "DOMAIN": "router.example.com",
        "SSL_CERT": "/etc/ssl/certs/router.crt",
        "SSL_KEY": "/etc/ssl/private/router.key",
    }

    result = subprocess.run(
        [str(installer), "--render-only", str(rendered)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    config = rendered.read_text()
    assert "server_name router.example.com;" in config
    assert "return 301 https://router.example.com$request_uri;" in config
    assert "ssl_certificate     /etc/ssl/certs/router.crt;" in config
    assert "ssl_certificate_key /etc/ssl/private/router.key;" in config
    for token in ("__DOMAIN__", "__SSL_CERT__", "__SSL_KEY__"):
        assert token not in config


def test_docs_and_scripts_use_only_new_public_and_backend_names():
    names = ["README.md", ".env.example", "pyproject.toml", "scripts/e2e.sh", "scripts/smoke.sh"]
    combined = "\n".join((ROOT / name).read_text() for name in names)

    assert "DeepSeek-v4-vl" in combined
    assert "OPENCODE_GO_API_BASE" in combined
    assert "GPT_LUNA_API_BASE" in combined
    assert "scripts/bootstrap.py" in combined
    assert "/ui" in combined
    project_metadata = (ROOT / "pyproject.toml").read_text()
    assert "OpenCode Go" in project_metadata
    assert "GPT Luna" in project_metadata
