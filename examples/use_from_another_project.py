"""Minimal example showing how another project can use multi_agent_core."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from multi_agent_core import Settings, run_task


def main() -> None:
    """Run a minimal task through the library."""
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set")
        print("Set the API key in your environment before running this example.")
        return

    result = run_task("Write a short welcome message", settings=Settings())

    print(result["task"])
    print(result["routing"])
    print(result["plan"])
    print(result["build"])
    print(result["critique"])


if __name__ == "__main__":
    main()
