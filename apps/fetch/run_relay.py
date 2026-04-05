from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import uvicorn


APP_DIR = Path(__file__).resolve().parent
DEFAULT_HOST = os.getenv("FETCH_RELAY_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("FETCH_RELAY_PORT", "8100"))


def configure_event_loop_policy(
    *,
    platform: str | None = None,
    asyncio_module=asyncio,
) -> None:
    current_platform = platform or sys.platform
    if not current_platform.startswith("win"):
        return
    if not hasattr(asyncio_module, "WindowsSelectorEventLoopPolicy"):
        return
    asyncio_module.set_event_loop_policy(asyncio_module.WindowsSelectorEventLoopPolicy())


def run_relay(*, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    configure_event_loop_policy()
    uvicorn.run(
        "uxray_fetch.relay:app",
        host=host,
        port=port,
        app_dir=str(APP_DIR),
    )


def main() -> None:
    run_relay()


if __name__ == "__main__":
    main()
