from __future__ import annotations

from uxray_fetch.agents.boss import build_boss_agent
from uxray_fetch.config import FetchConfig


def main() -> None:
    config = FetchConfig.from_env()
    agent = build_boss_agent(settings=config.boss)
    agent.run()


if __name__ == "__main__":
    main()
