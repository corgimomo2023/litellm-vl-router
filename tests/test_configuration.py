from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_litellm_config_exposes_expected_cline_models_and_callback():
    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    models = {item["model_name"] for item in config["model_list"]}

    assert "deepseek-v4-flash-vl" in models
    assert "deepseek-v4-pro-vl" in models
    assert "_internal-qwen3.5-flash-vision" in models
    assert config["litellm_settings"]["callbacks"] == "app.custom_handler.vl_router"


def test_config_uses_environment_references_instead_of_committed_secrets():
    config_text = (ROOT / "config.yaml").read_text()

    assert "DEEPSEEK_API_KEY" in config_text
    assert "QWEN_API_KEY" in config_text
    assert "os.environ/" in config_text
    assert "sk-change-me" not in config_text


def test_compose_keeps_database_and_redis_off_host_ports():
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text())

    assert "ports" not in compose["services"]["postgres"]
    assert "ports" not in compose["services"]["redis"]
    assert compose["services"]["litellm"]["ports"][0].startswith("127.0.0.1:")
