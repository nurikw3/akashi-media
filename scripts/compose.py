"""Run Docker Compose with the local PoC key file without printing secrets.

Production deployments should put the values in `.env`. This convenience
wrapper only maps the historical names in the ignored `keys.txt` file so the
local stack can be started without copying secrets into Git-tracked files.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


KEY_MAP = {
    "telegram_channel_id": "TELEGRAM_CHANNEL_ID",
    "bot_id": "TELEGRAM_BOT_TOKEN",
    "tavily_api": "TAVILY_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def _read_keys(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        separator = "=" if "=" in line else ":" if ":" in line else None
        if separator is None:
            continue
        key, value = line.split(separator, 1)
        values[key.strip()] = value.strip()
    return values


def main() -> int:
    compose_args = sys.argv[1:] or ["up", "--build", "-d"]
    env = os.environ.copy()
    values = _read_keys(Path("keys.txt"))
    for source, target in KEY_MAP.items():
        if not env.get(target):
            env[target] = values.get(source, "")
    return subprocess.run(["docker", "compose", *compose_args], env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
