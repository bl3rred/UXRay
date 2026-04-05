from __future__ import annotations

import os
from pathlib import Path

from uxray_fetch.compat import ensure_supported_python


def main() -> None:
    ensure_supported_python()

    from uagents import Agent

    seed = os.getenv("FETCH_RELAY_AGENT_SEED", "replace-this-with-a-new-seed-phrase").strip()
    agent = Agent(
        name="uxray_mailbox_relay_agent",
        seed=seed,
        port=8000,
        endpoint=("http://127.0.0.1:8000/submit",),
        mailbox=True,
        publish_agent_details=False,
        readme_path=str(Path(__file__).resolve().parents[1] / "README.md"),
    )

    print(agent.address)
    agent.run()


if __name__ == "__main__":
    main()
