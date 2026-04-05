import app.config as config_module
from app.config import AppConfig


def test_config_uses_default_browser_use_model_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("BROWSER_USE_MODEL", raising=False)
    monkeypatch.delenv("BROWSER_USE_RUN_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setattr(config_module, "_load_env_file", lambda path: None)

    config = AppConfig.from_env()

    assert config.browser_use_model == "claude-sonnet-4.6"
    assert config.browser_use_run_timeout_seconds == 240.0


def test_config_marks_fetch_evaluation_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("FETCH_EVALUATION_ENABLED", raising=False)
    monkeypatch.delenv("FETCH_EVALUATION_AGENT_URL", raising=False)
    monkeypatch.delenv("FETCH_EVALUATION_API_KEY", raising=False)
    monkeypatch.delenv("FETCH_EVALUATION_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setattr(config_module, "_load_env_file", lambda path: None)

    config = AppConfig.from_env()

    assert config.fetch_evaluation_enabled is False
    assert config.fetch_evaluation_agent_url is None
    assert config.fetch_evaluation_api_key is None
    assert config.fetch_evaluation_timeout_seconds == 180.0
