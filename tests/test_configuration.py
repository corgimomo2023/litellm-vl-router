from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_yaml(name):
    return yaml.safe_load((ROOT / name).read_text())


def test_litellm_config_exposes_one_public_alias_and_one_internal_vision_target():
    config = load_yaml("config.yaml")
    models = {item["model_name"]: item for item in config["model_list"]}
    public_models = {name for name in models if not name.startswith("_internal-")}

    assert public_models == {"DeepSeek-v4-vl"}
    assert "_internal-gpt-luna-vision" in models
    assert models["DeepSeek-v4-vl"]["litellm_params"] == {
        "model": "os.environ/OPENCODE_GO_MODEL",
        "api_base": "os.environ/OPENCODE_GO_API_BASE",
        "api_key": "os.environ/OPENCODE_GO_API_KEY",
        "timeout": 180,
    }
    assert models["_internal-gpt-luna-vision"]["litellm_params"] == {
        "model": "os.environ/GPT_LUNA_MODEL",
        "api_base": "os.environ/GPT_LUNA_API_BASE",
        "api_key": "os.environ/GPT_LUNA_API_KEY",
        "timeout": 180,
    }
    assert config["litellm_settings"]["callbacks"] == "app.custom_handler.vl_router"


def test_config_enables_database_redis_reliability_and_content_spend_logging():
    config = load_yaml("config.yaml")
    litellm = config["litellm_settings"]
    general = config["general_settings"]
    router = config["router_settings"]

    assert litellm["json_logs"] is True
    assert litellm["turn_off_message_logging"] is False
    assert litellm["redact_user_api_key_info"] is True
    assert litellm["enable_redis_auth_cache"] is True
    assert litellm["cache_params"]["type"] == "redis"
    assert general["master_key"] == "os.environ/LITELLM_MASTER_KEY"
    assert general["database_url"] == "os.environ/DATABASE_URL"
    assert general["store_prompts_in_spend_logs"] is True
    assert general["disable_spend_logs"] is False
    assert router["retry_policy"]["TimeoutErrorRetries"] >= 1
    assert router["retry_policy"]["RateLimitErrorRetries"] >= 1


def test_config_uses_only_placeholder_environment_references_for_upstreams():
    config_text = (ROOT / "config.yaml").read_text()

    for name in (
        "OPENCODE_GO_API_BASE",
        "OPENCODE_GO_API_KEY",
        "OPENCODE_GO_MODEL",
        "GPT_LUNA_API_BASE",
        "GPT_LUNA_API_KEY",
        "GPT_LUNA_MODEL",
    ):
        assert f"os.environ/{name}" in config_text
    assert "os.environ/" in config_text
    assert "sk-change-me" not in config_text


def test_compose_is_private_healthy_persistent_and_resource_bounded():
    compose = load_yaml("compose.yaml")
    services = compose["services"]

    assert set(services) == {"postgres", "redis", "litellm"}
    assert services["postgres"]["image"].startswith("postgres:16")
    assert services["redis"]["image"].startswith("redis:7")
    assert "ports" not in services["postgres"]
    assert "ports" not in services["redis"]
    assert services["litellm"]["ports"][0].startswith("127.0.0.1:")
    assert services["litellm"]["environment"]["DATABASE_URL"].endswith("@postgres:5432/litellm")
    assert set(compose["volumes"]) == {"postgres_data", "redis_data"}

    total_memory_mb = 0
    for service in services.values():
        assert "healthcheck" in service
        assert service["logging"]["driver"] == "json-file"
        assert service["logging"]["options"]["max-size"]
        assert service["logging"]["options"]["max-file"]
        memory = service["deploy"]["resources"]["limits"]["memory"]
        assert memory.endswith("M")
        total_memory_mb += int(memory[:-1])
    assert total_memory_mb <= 5_120


def test_compose_test_overlay_uses_new_mock_provider_names_only():
    overlay_text = (ROOT / "compose.test.yaml").read_text()

    assert "http://mock-provider:8080/opencode-go/v1" in overlay_text
    assert "http://mock-provider:8080/gpt-luna/v1" in overlay_text
    assert "OPENCODE_GO_MODEL" in overlay_text
    assert "GPT_LUNA_MODEL" in overlay_text
