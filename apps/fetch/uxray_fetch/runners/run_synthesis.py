from __future__ import annotations

from uxray_fetch.agents.synthesis import build_synthesis_agent
from uxray_fetch.config import FetchConfig


def main() -> None:
    config = FetchConfig.from_env()
    agent = build_synthesis_agent(settings=config.synthesis)
    agent.run()


if __name__ == "__main__":
    main()
