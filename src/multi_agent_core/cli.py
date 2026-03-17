"""Command-line entrypoint for multi-agent-core."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from .api import run_task
from .settings import Settings


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    parser = argparse.ArgumentParser(description="Run a task through multi-agent-core.")
    parser.add_argument("task", help="Task text to run")
    parser.add_argument("--project-root", default=None, help="Project root for file operations")
    parser.add_argument("--rounds", type=int, default=2, help="Maximum autonomous rounds")
    parser.add_argument("--iterations", type=int, default=3, help="Maximum iterations per step")
    parser.add_argument("--export", action="store_true", help="Write a JSON run report to project_root/runs")
    parser.add_argument("--verbose", action="store_true", help="Show agent logs")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and print a compact JSON result."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    settings = Settings(
        project_root=args.project_root,
        autonomous_rounds=args.rounds,
        max_iterations_per_step=args.iterations,
        export_enabled=args.export,
    )

    try:
        result = run_task(args.task, settings=settings)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    output = {
        "task": result["task"],
        "active_task": result["active_task"],
        "final_result": result["final_result"],
        "next_step": result["next_step"],
        "escalation": result["escalation"],
    }
    print(json.dumps(output, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

