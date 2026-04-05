from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = ROOT_DIR / "apps" / "api" / "data" / "uxray.db"
DEFAULT_ARTIFACTS_DIR = ROOT_DIR / "apps" / "api" / "data" / "artifacts"
DEFAULT_LOCAL_REPO_BUILD_ROOT = Path.home() / "Desktop" / "uxray-buildStorage"
ENV_FILE = ROOT_DIR / ".env.local"
SUPPORTED_BROWSER_USE_MODELS = frozenset(
    {
        "claude-sonnet-4.6",
        "claude-opus-4.6",
        "gemini-3-flash",
    }
)


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


@dataclass(slots=True)
class AppConfig:
    db_path: Path = DEFAULT_DB_PATH
    artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR
    browser_use_api_key: str | None = None
    browser_use_model: str = "claude-sonnet-4.6"
    browser_use_run_timeout_seconds: float = 240.0
    queue_poll_seconds: float = 0.5
    start_worker: bool = True
    frontend_origin: str = "http://127.0.0.1:3000,http://localhost:3000"
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_storage_bucket: str | None = None
    local_repo_build_enabled: bool = True
    local_repo_build_root: Path = DEFAULT_LOCAL_REPO_BUILD_ROOT
    fetch_evaluation_enabled: bool = False
    fetch_evaluation_agent_url: str | None = None
    fetch_evaluation_api_key: str | None = None
    fetch_evaluation_timeout_seconds: float = 180.0
    fetch_evaluation_asi_api_key: str | None = None
    fetch_evaluation_asi_model: str = "asi1-mini"
    source_review_enabled: bool = False
    source_review_api_key: str | None = None
    source_review_model: str = "gpt-5-mini"
    source_review_timeout_seconds: float = 45.0

    @classmethod
    def from_env(cls) -> "AppConfig":
        _load_env_file(ENV_FILE)
        config = cls(
            db_path=Path(os.getenv("UXRAY_DB_PATH", str(DEFAULT_DB_PATH))),
            artifacts_dir=Path(os.getenv("UXRAY_ARTIFACTS_DIR", str(DEFAULT_ARTIFACTS_DIR))),
            browser_use_api_key=os.getenv("BROWSER_USE_API_KEY"),
            browser_use_model=os.getenv("BROWSER_USE_MODEL", "claude-sonnet-4.6"),
            browser_use_run_timeout_seconds=float(
                os.getenv("BROWSER_USE_RUN_TIMEOUT_SECONDS", "240")
            ),
            queue_poll_seconds=float(os.getenv("UXRAY_QUEUE_POLL_SECONDS", "0.5")),
            start_worker=_env_bool("UXRAY_START_WORKER", True),
            frontend_origin=os.getenv(
                "UXRAY_FRONTEND_ORIGIN",
                "http://127.0.0.1:3000,http://localhost:3000",
            ),
            supabase_url=os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
            supabase_publishable_key=os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"),
            supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
            supabase_storage_bucket=os.getenv("SUPABASE_STORAGE_BUCKET"),
            local_repo_build_enabled=_env_bool("UXRAY_LOCAL_REPO_BUILD_ENABLED", True),
            local_repo_build_root=Path(
                os.getenv("UXRAY_LOCAL_REPO_BUILD_ROOT", str(DEFAULT_LOCAL_REPO_BUILD_ROOT))
            ),
            fetch_evaluation_enabled=_env_bool("FETCH_EVALUATION_ENABLED", False),
            fetch_evaluation_agent_url=os.getenv("FETCH_EVALUATION_AGENT_URL"),
            fetch_evaluation_api_key=os.getenv("FETCH_EVALUATION_API_KEY"),
            fetch_evaluation_timeout_seconds=float(
                os.getenv("FETCH_EVALUATION_TIMEOUT_SECONDS", "180.0")
            ),
            fetch_evaluation_asi_api_key=os.getenv("ASI_ONE_API_KEY"),
            fetch_evaluation_asi_model=os.getenv(
                "FETCH_RELAY_ASI_MODEL",
                os.getenv("UXRAY_FETCH_ASI_MODEL", "asi1-mini"),
            ),
            source_review_enabled=_env_bool(
                "SOURCE_REVIEW_ENABLED",
                bool(os.getenv("OPENAI_API_KEY")),
            ),
            source_review_api_key=os.getenv("OPENAI_API_KEY"),
            source_review_model=os.getenv("SOURCE_REVIEW_MODEL", "gpt-5-mini"),
            source_review_timeout_seconds=float(
                os.getenv("SOURCE_REVIEW_TIMEOUT_SECONDS", "45.0")
            ),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.browser_use_model not in SUPPORTED_BROWSER_USE_MODELS:
            supported = ", ".join(sorted(SUPPORTED_BROWSER_USE_MODELS))
            raise ValueError(
                f"Unsupported BROWSER_USE_MODEL '{self.browser_use_model}'. "
                f"Choose one of: {supported}"
            )
