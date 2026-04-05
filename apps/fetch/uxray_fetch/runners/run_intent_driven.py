from __future__ import annotations

from uxray_fetch.agents.audience import build_audience_agent
from uxray_fetch.config import FetchConfig


def main() -> None:
    config = FetchConfig.from_env()
    agent = build_audience_agent(settings=config.intent_driven, audience="intent_driven")
    agent.run()


if __name__ == "__main__":
    main()
