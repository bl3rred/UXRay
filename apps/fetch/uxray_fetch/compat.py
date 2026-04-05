from __future__ import annotations

import sys


def ensure_supported_python() -> None:
    if sys.version_info < (3, 11):
        raise RuntimeError("UXRay Fetch agents require Python 3.11 or newer.")
    if sys.version_info >= (3, 14):
        version = ".".join(str(part) for part in sys.version_info[:3])
        raise RuntimeError(
            "uAgents is not stable on Python 3.14 in the current Fetch.ai stack. "
            f"Detected Python {version}. Use Python 3.11 or 3.12 for the agent runners."
        )
