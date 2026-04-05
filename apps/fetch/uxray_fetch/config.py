from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = APP_DIR / ".env"


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None


def _required_env(name: str) -> str:
    value = _optional_env(name)
    if value is None:
        raise ValueError(f"{name} is required to run UXRay Fetch agents.")
    return value


@dataclass(slots=True)
class AgentSettings:
    name: str
    seed: str
    port: int
    publish_agent_details: bool
    agentverse_url: str


@dataclass(slots=True)
class FetchConfig:
    agentverse_url: str
    ws_enabled: bool
    ws_host: str
    ws_port: int
    api_key: str
    orchestrator_timeout_seconds: float
    publish_specialists: bool
    orchestrator: AgentSettings
    first_time_visitor: AgentSettings
    intent_driven: AgentSettings
    trust_evaluator: AgentSettings
    custom_audience: AgentSettings
    boss: AgentSettings
    synthesis: AgentSettings

    @classmethod
    def from_env(cls) -> "FetchConfig":
        _load_env_file(ENV_FILE)
        publish_specialists = _env_bool("UXRAY_FETCH_PUBLISH_SPECIALISTS", False)
        return cls(
            agentverse_url=os.getenv("UXRAY_FETCH_AGENTVERSE_URL", "https://agentverse.ai"),
            ws_enabled=_env_bool("UXRAY_FETCH_WS_ENABLED", True),
            ws_host=os.getenv("UXRAY_FETCH_WS_HOST", "127.0.0.1"),
            ws_port=_env_int("UXRAY_FETCH_WS_PORT", 8765),
            api_key=_required_env("UXRAY_FETCH_API_KEY"),
            orchestrator_timeout_seconds=_env_float(
                "UXRAY_FETCH_ORCHESTRATOR_TIMEOUT_SECONDS",
                20.0,
            ),
            publish_specialists=publish_specialists,
            orchestrator=AgentSettings(
                name=os.getenv("UXRAY_FETCH_ORCHESTRATOR_NAME", "uxray_orchestrator_agent"),
                seed=_required_env("UXRAY_FETCH_ORCHESTRATOR_SEED"),
                port=_env_int("UXRAY_FETCH_ORCHESTRATOR_PORT", 8100),
                publish_agent_details=True,
                agentverse_url=os.getenv("UXRAY_FETCH_AGENTVERSE_URL", "https://agentverse.ai"),
            ),
            first_time_visitor=AgentSettings(
                name=os.getenv(
                    "UXRAY_FETCH_FIRST_TIME_VISITOR_NAME",
                    "uxray_first_time_visitor_agent",
                ),
                seed=_required_env("UXRAY_FETCH_FIRST_TIME_VISITOR_SEED"),
                port=_env_int("UXRAY_FETCH_FIRST_TIME_VISITOR_PORT", 8101),
                publish_agent_details=publish_specialists,
                agentverse_url=os.getenv("UXRAY_FETCH_AGENTVERSE_URL", "https://agentverse.ai"),
            ),
            intent_driven=AgentSettings(
                name=os.getenv("UXRAY_FETCH_INTENT_DRIVEN_NAME", "uxray_intent_driven_agent"),
                seed=_required_env("UXRAY_FETCH_INTENT_DRIVEN_SEED"),
                port=_env_int("UXRAY_FETCH_INTENT_DRIVEN_PORT", 8102),
                publish_agent_details=publish_specialists,
                agentverse_url=os.getenv("UXRAY_FETCH_AGENTVERSE_URL", "https://agentverse.ai"),
            ),
            trust_evaluator=AgentSettings(
                name=os.getenv(
                    "UXRAY_FETCH_TRUST_EVALUATOR_NAME",
                    "uxray_trust_evaluator_agent",
                ),
                seed=_required_env("UXRAY_FETCH_TRUST_EVALUATOR_SEED"),
                port=_env_int("UXRAY_FETCH_TRUST_EVALUATOR_PORT", 8103),
                publish_agent_details=publish_specialists,
                agentverse_url=os.getenv("UXRAY_FETCH_AGENTVERSE_URL", "https://agentverse.ai"),
            ),
            custom_audience=AgentSettings(
                name=os.getenv(
                    "UXRAY_FETCH_CUSTOM_AUDIENCE_NAME",
                    "uxray_custom_audience_agent",
                ),
                seed=_required_env("UXRAY_FETCH_CUSTOM_AUDIENCE_SEED"),
                port=_env_int("UXRAY_FETCH_CUSTOM_AUDIENCE_PORT", 8104),
                publish_agent_details=publish_specialists,
                agentverse_url=os.getenv("UXRAY_FETCH_AGENTVERSE_URL", "https://agentverse.ai"),
            ),
            boss=AgentSettings(
                name=os.getenv("UXRAY_FETCH_BOSS_NAME", "uxray_boss_agent"),
                seed=_required_env("UXRAY_FETCH_BOSS_SEED"),
                port=_env_int("UXRAY_FETCH_BOSS_PORT", 8105),
                publish_agent_details=publish_specialists,
                agentverse_url=os.getenv("UXRAY_FETCH_AGENTVERSE_URL", "https://agentverse.ai"),
            ),
            synthesis=AgentSettings(
                name=os.getenv("UXRAY_FETCH_SYNTHESIS_NAME", "uxray_synthesis_agent"),
                seed=_required_env("UXRAY_FETCH_SYNTHESIS_SEED"),
                port=_env_int("UXRAY_FETCH_SYNTHESIS_PORT", 8106),
                publish_agent_details=publish_specialists,
                agentverse_url=os.getenv("UXRAY_FETCH_AGENTVERSE_URL", "https://agentverse.ai"),
            ),
        )
