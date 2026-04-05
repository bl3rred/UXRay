from __future__ import annotations

from uxray_fetch.agents.orchestrator import build_orchestrator_agent
from uxray_fetch.config import FetchConfig


def main() -> None:
    config = FetchConfig.from_env()
    agent = build_orchestrator_agent(config=config)
    agent.run()


if __name__ == "__main__":
    main()
