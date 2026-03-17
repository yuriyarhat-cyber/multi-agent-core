"""Smoke tests for the minimal multi-agent flow."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from multi_agent_core import Orchestrator, create_state


class SmokeTest(unittest.TestCase):
    def test_orchestrator_runs_full_flow(self) -> None:
        task = "Prepare a short customer onboarding outline"
        state = create_state(task)

        result = Orchestrator().run(task=task, state=state)

        self.assertEqual(result["task"], task)
        self.assertIn("steps", result["plan"])
        self.assertGreaterEqual(len(result["plan"]["steps"]), 1)
        self.assertIn("status", result["critique"])
        self.assertIn(result["critique"]["status"], {"pass", "revise"})
        self.assertGreaterEqual(len(result["history"]), len(result["plan"]["steps"]))

        first_entry = result["history"][0]
        self.assertIn("step", first_entry)
        self.assertIn("attempt", first_entry)
        self.assertIn("build", first_entry)
        self.assertIn("critique", first_entry)


if __name__ == "__main__":
    unittest.main()
