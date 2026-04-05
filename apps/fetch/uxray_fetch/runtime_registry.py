from __future__ import annotations

import json
from pathlib import Path


RUNTIME_DIR = Path(__file__).resolve().parents[1] / ".runtime"
REGISTRY_PATH = RUNTIME_DIR / "agents.json"


def _read_registry() -> dict[str, dict[str, str | int]]:
    if not REGISTRY_PATH.exists():
        return {}
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def register_agent_runtime(name: str, address: str, port: int, role: str) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    payload = _read_registry()
    payload[name] = {
        "name": name,
        "address": address,
        "port": port,
        "role": role,
    }
    temp_path = REGISTRY_PATH.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp_path.replace(REGISTRY_PATH)


def resolve_agent_address(name: str) -> str | None:
    return _read_registry().get(name, {}).get("address")  # type: ignore[return-value]
