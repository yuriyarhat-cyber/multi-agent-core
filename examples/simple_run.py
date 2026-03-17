"""Run a minimal end-to-end orchestration example."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from multi_agent_core import Orchestrator, create_state, get_openai_model


def main() -> None:
    """Run the orchestrator with the real OpenAI API."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    task = "Write a simple welcome note for a new product user"
    state = create_state(task)
    print(f"Using OpenAI API with model: {get_openai_model()}")
    print()

    try:
        result = Orchestrator().run(task=task, state=state)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        raise

    print("TASK")
    print(result["task"])
    print()

    print("PLAN")
    print(json.dumps(result["plan"], indent=2))
    print()

    print("LATEST BUILD")
    print(json.dumps(result["build"], indent=2))
    print()

    print("LATEST CRITIQUE")
    print(json.dumps(result["critique"], indent=2))
    print()

    print("HISTORY")
    print(json.dumps(result["history"], indent=2))


if __name__ == "__main__":
    main()
