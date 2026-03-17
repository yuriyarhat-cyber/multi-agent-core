"""Run a research task example with URL-based live research."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from multi_agent_core import Settings, run_task
from multi_agent_core.llm import get_openai_model


def main() -> None:
    """Run a research task that includes live URLs."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    task = "analyze and compare https://example.com and https://www.iana.org/domains/reserved"

    print(f"Using OpenAI API with model: {get_openai_model()}")
    print()

    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set")
        print("Set OPENAI_API_KEY in your environment, then run the example again.")
        return

    try:
        result = run_task(task, settings=Settings(project_root=str(ROOT)))
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return

    print("TASK")
    print(result["task"])
    print()

    print("EXECUTED FLOW")
    print(" -> ".join(result["executed_flow"]))
    print()

    print("RESEARCH")
    print(json.dumps(result["research"], indent=2))
    print()

    print("LATEST BUILD")
    print(json.dumps(result["build"], indent=2))
    print()

    print("LATEST CRITIQUE")
    print(json.dumps(result["critique"], indent=2))


if __name__ == "__main__":
    main()
