"""Smoke tests for the minimal multi-agent flow."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from multi_agent_core import (
    Analyzer,
    ArtifactTracker,
    Builder,
    CapabilityReport,
    Contrarian,
    Critic,
    Debugger,
    EscalationAgent,
    ExecutionPolicy,
    Orchestrator,
    Planner,
    ResearchAgent,
    ResearchCritic,
    RecoveryPlanner,
    ResultSynthesizer,
    RunExporter,
    Router,
    PriorityAgent,
    SessionMemory,
    SessionStrategist,
    Settings,
    Strategist,
    TaskBoard,
    Tester,
    ToolSelector,
    codex_llm,
    create_state,
    run_task,
)


class FakeResponsesClient:
    def create(self, model: str, input: str) -> SimpleNamespace:
        if "Target file:" in input:
            return SimpleNamespace(output_text="print('hello from generated file')\n")
        return SimpleNamespace(output_text=f"fake-response for {model}: {input[:60]}")


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.responses = FakeResponsesClient()


class FakeHTTPResponse:
    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def read(self) -> bytes:
        html = (
            "<html><body><h1>Comparison</h1>"
            "<p>Option A is faster. Option B is safer. "
            "Conclusion: choose A for speed.</p></body></html>"
        )
        return html.encode("utf-8")


class FakeCompletedProcess:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class SmokeTest(unittest.TestCase):
    def test_public_api_imports_are_available(self) -> None:
        self.assertEqual(Orchestrator.__name__, "Orchestrator")
        self.assertEqual(Router.__name__, "Router")
        self.assertEqual(SessionStrategist.__name__, "SessionStrategist")
        self.assertEqual(Strategist.__name__, "Strategist")
        self.assertEqual(Planner.__name__, "Planner")
        self.assertEqual(Builder.__name__, "Builder")
        self.assertEqual(ArtifactTracker.__name__, "ArtifactTracker")
        self.assertEqual(ExecutionPolicy.__name__, "ExecutionPolicy")
        self.assertEqual(ToolSelector.__name__, "ToolSelector")
        self.assertEqual(CapabilityReport.__name__, "CapabilityReport")
        self.assertEqual(RunExporter.__name__, "RunExporter")
        self.assertEqual(SessionMemory.__name__, "SessionMemory")
        self.assertEqual(RecoveryPlanner.__name__, "RecoveryPlanner")
        self.assertEqual(TaskBoard.__name__, "TaskBoard")
        self.assertEqual(PriorityAgent.__name__, "PriorityAgent")
        self.assertEqual(EscalationAgent.__name__, "EscalationAgent")
        self.assertEqual(Settings.__name__, "Settings")
        self.assertEqual(Tester.__name__, "Tester")
        self.assertEqual(Critic.__name__, "Critic")
        self.assertEqual(ResearchCritic.__name__, "ResearchCritic")
        self.assertEqual(ResultSynthesizer.__name__, "ResultSynthesizer")
        self.assertEqual(Contrarian.__name__, "Contrarian")
        self.assertEqual(Debugger.__name__, "Debugger")
        self.assertEqual(Analyzer.__name__, "Analyzer")
        self.assertEqual(ResearchAgent.__name__, "ResearchAgent")
        self.assertTrue(callable(create_state))
        self.assertTrue(callable(codex_llm))
        self.assertTrue(callable(run_task))

    def test_package_imports_as_library(self) -> None:
        command = [
            sys.executable,
            "-c",
            "import multi_agent_core; print(multi_agent_core.run_task.__name__, multi_agent_core.Settings.__name__)",
        ]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SRC)
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.stdout.strip(), "run_task Settings")

    def test_settings_resolve_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(project_root=temp_dir)
            self.assertEqual(settings.resolved_project_root(), temp_dir)

    def test_router_classifies_file_task(self) -> None:
        routing = Router().route("create file generated/hello.py")
        self.assertEqual(routing["task_type"], "file_task")
        self.assertEqual(routing["suggested_flow"], ["planner", "builder", "critic"])

    def test_router_classifies_text_task(self) -> None:
        routing = Router().route("rewrite this email into a short summary")
        self.assertEqual(routing["task_type"], "text_task")

    def test_router_classifies_research_task(self) -> None:
        routing = Router().route("analyze and compare two onboarding approaches")
        self.assertEqual(routing["task_type"], "research_task")

    def test_router_classifies_general_task(self) -> None:
        routing = Router().route("help me think through this task")
        self.assertEqual(routing["task_type"], "general_task")

    @patch.dict("os.environ", {}, clear=True)
    def test_llm_raises_without_api_key(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY not set"):
            codex_llm("hello")

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}, clear=True)
    @patch("multi_agent_core.llm.OpenAI", return_value=FakeOpenAIClient())
    def test_run_task_returns_basic_result_shape(self, mock_openai: object) -> None:
        result = run_task("Help me think through the next step", settings=Settings(project_root=str(ROOT)))
        self.assertEqual(result["task"], "Help me think through the next step")
        self.assertIn("routing", result)
        self.assertIn("tool_selection", result)
        self.assertIn("strategy", result)
        self.assertIn("plan", result)
        self.assertIn("artifacts", result)
        self.assertIn("policy", result)
        self.assertIn("subtasks", result)
        self.assertIn("current_subtask", result)
        self.assertIn("completed_subtasks", result)
        self.assertIn("task_board", result)
        self.assertIn("priorities", result)
        self.assertIn("next_step", result)
        self.assertIn("session_strategy", result)
        self.assertIn("session_history", result)
        self.assertIn("final_result", result)
        self.assertIn("capability_report", result)
        self.assertIn("memory", result)
        self.assertIn("recovery_plan", result)
        self.assertIn("escalation", result)
        self.assertIn("export", result)
        self.assertIn("history", result)
        self.assertTrue(mock_openai.called)

    def test_cli_returns_error_without_api_key(self) -> None:
        command = [sys.executable, "-m", "multi_agent_core.cli", "Write a short welcome message"]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SRC)
        env.pop("OPENAI_API_KEY", None)
        result = subprocess.run(command, capture_output=True, text=True, env=env, check=False)

        self.assertEqual(result.returncode, 1)
        self.assertIn("OPENAI_API_KEY not set", result.stderr)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}, clear=True)
    @patch("multi_agent_core.llm.OpenAI", return_value=FakeOpenAIClient())
    def test_strategist_drives_general_flow(self, mock_openai: object) -> None:
        task = "Help me think through the next step"
        result = Orchestrator().run(task=task, state=create_state(task))

        self.assertEqual(result["routing"]["task_type"], "general_task")
        self.assertEqual(
            result["executed_flow"],
            ["strategist", "planner", "builder", "critic", "debugger", "analyzer"],
        )
        self.assertEqual(result["history"][0]["agent"], "session_memory")
        self.assertEqual(result["history"][1]["agent"], "task_board")
        self.assertEqual(result["history"][2]["agent"], "priority_agent")
        self.assertEqual(result["history"][3]["agent"], "session_strategist")
        self.assertEqual(result["history"][4]["agent"], "task_board")
        self.assertEqual(result["history"][5]["agent"], "priority_agent")
        self.assertEqual(result["history"][6]["agent"], "tool_selector")
        self.assertEqual(result["history"][7]["agent"], "strategist")
        self.assertTrue(mock_openai.called)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}, clear=True)
    @patch("multi_agent_core.llm.OpenAI", return_value=FakeOpenAIClient())
    def test_file_task_uses_tester_and_creates_file(self, mock_openai: object) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            task = "create file generated/hello.py"
            state = create_state(task)
            state["project_root"] = temp_dir

            result = Orchestrator().run(task=task, state=state)

            created_path = Path(temp_dir) / "generated" / "hello.py"
            tester_entries = [entry for entry in result["history"] if entry["agent"] == "tester"]
            artifact_entries = [entry for entry in result["history"] if entry["agent"] == "artifact_tracker"]

            self.assertTrue(created_path.exists())
            self.assertEqual(result["routing"]["task_type"], "file_task")
            self.assertIn("tester", result["executed_flow"])
            self.assertGreaterEqual(len(tester_entries), 1)
            self.assertGreaterEqual(len(artifact_entries), 1)
            self.assertGreaterEqual(len(result["artifacts"]["items"]), 1)
            self.assertTrue(mock_openai.called)

    @patch("multi_agent_core.agents.subprocess.run")
    def test_tester_runs_project_unittest_for_python_files(self, mock_run: object) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "tests").mkdir()
            (project_root / "generated").mkdir()
            target_file = project_root / "generated" / "hello.py"
            target_file.write_text("print('hello')\n", encoding="utf-8")
            mock_run.return_value = FakeCompletedProcess(0, stdout="OK", stderr="")

            testing = Tester().run(
                {
                    "task": "create file generated/hello.py",
                    "project_root": str(project_root),
                    "build": {
                        "path": str(target_file),
                        "action": "write_file",
                        "content": "print('hello')\n",
                    },
                }
            )

            self.assertEqual(testing["status"], "pass")
            self.assertIn("ran project unittest suite", testing["checks"])
            self.assertEqual(
                testing["command"],
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
            )
            self.assertEqual(testing["stdout"], "OK")
            self.assertTrue(mock_run.called)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}, clear=True)
    @patch("multi_agent_core.agents.subprocess.run")
    @patch("multi_agent_core.llm.OpenAI", return_value=FakeOpenAIClient())
    def test_orchestrator_can_continue_for_second_autonomous_round(
        self,
        mock_openai: object,
        mock_run: object,
    ) -> None:
        mock_run.return_value = FakeCompletedProcess(
            1,
            stdout="FAIL: test_example (tests.test_example.SmokeTest)",
            stderr="AssertionError: expected hello",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "tests").mkdir()
            result = run_task("create file generated/hello.py", project_root=str(project_root))

        self.assertEqual(len(result["session_history"]), 2)
        self.assertEqual(result["session_history"][0]["critique_status"], "revise")
        self.assertEqual(result["session_history"][1]["round"], 2)
        self.assertTrue(result["task_guidance"])
        self.assertEqual(result["next_step"]["status"], "needs_work")
        self.assertTrue(result["session_strategy"]["continue_session"] is False or result["session_strategy"]["continue_session"] is True)
        self.assertIn("session_strategy", result["session_history"][0])
        self.assertTrue(mock_openai.called)
        self.assertTrue(mock_run.called)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}, clear=True)
    @patch("multi_agent_core.llm.OpenAI", return_value=FakeOpenAIClient())
    def test_debugger_runs_when_review_fails(self, mock_openai: object) -> None:
        task = "Prepare a short customer onboarding outline"
        result = Orchestrator().run(task=task, state=create_state(task))

        debugger_entries = [
            entry for entry in result["history"]
            if entry["agent"] == "debugger" and entry["result"]["status"] == "active"
        ]
        second_build = next(
            entry["result"]
            for entry in result["history"]
            if entry["agent"] == "builder" and entry["attempt"] == 2
        )

        self.assertGreaterEqual(len(debugger_entries), 1)
        self.assertTrue(second_build["used_feedback"])
        self.assertEqual(result["next_step"]["status"], "ready")
        self.assertTrue(mock_openai.called)

    def test_debugger_uses_test_output_in_fix_guidance(self) -> None:
        debugging = Debugger().run(
            {
                "critique": {
                    "status": "revise",
                    "issues": ["Project tests failed"],
                    "fix_instructions": ["Read the failing unittest output and fix the code or tests that are breaking."],
                },
                "testing": {
                    "command": [sys.executable, "-m", "unittest"],
                    "stdout": "FAIL: test_example (tests.test_example.SmokeTest)",
                    "stderr": "AssertionError: expected hello",
                },
            }
        )

        self.assertEqual(debugging["status"], "active")
        self.assertTrue(any("Recent test output:" in note for note in debugging["debug_notes"]))
        self.assertTrue(any("Recent test error output:" in note for note in debugging["debug_notes"]))
        self.assertTrue(any("Re-run tests with:" in note for note in debugging["debug_notes"]))
        self.assertTrue(
            any("unittest output" in instruction for instruction in debugging["fix_instructions"])
        )

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}, clear=True)
    @patch("multi_agent_core.llm.OpenAI", return_value=FakeOpenAIClient())
    def test_research_task_uses_research_critic_and_contrarian(self, mock_openai: object) -> None:
        task = "analyze and compare two onboarding approaches"
        result = Orchestrator().run(task=task, state=create_state(task))

        research_critic_entries = [entry for entry in result["history"] if entry["agent"] == "research_critic"]
        contrarian_entries = [entry for entry in result["history"] if entry["agent"] == "contrarian"]

        self.assertEqual(result["routing"]["task_type"], "research_task")
        self.assertIn("research_critic", result["executed_flow"])
        self.assertIn("contrarian", result["executed_flow"])
        self.assertGreaterEqual(len(research_critic_entries), 1)
        self.assertGreaterEqual(len(contrarian_entries), 1)
        self.assertTrue(mock_openai.called)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}, clear=True)
    @patch("multi_agent_core.llm.OpenAI", return_value=FakeOpenAIClient())
    def test_research_agent_is_not_used_without_urls(self, mock_openai: object) -> None:
        task = "analyze and compare two onboarding approaches"
        result = Orchestrator().run(task=task, state=create_state(task))

        research_agent_entries = [entry for entry in result["history"] if entry["agent"] == "research_agent"]
        self.assertEqual(research_agent_entries, [])
        self.assertTrue(mock_openai.called)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}, clear=True)
    @patch("multi_agent_core.agents.urlopen", return_value=FakeHTTPResponse())
    @patch("multi_agent_core.llm.OpenAI", return_value=FakeOpenAIClient())
    def test_research_agent_runs_with_urls_in_task(self, mock_openai: object, mock_urlopen: object) -> None:
        task = "analyze and compare https://example.com/source-a and https://example.com/source-b"
        result = Orchestrator().run(task=task, state=create_state(task))

        research_agent_entries = [entry for entry in result["history"] if entry["agent"] == "research_agent"]

        self.assertEqual(result["routing"]["task_type"], "research_task")
        self.assertIn("research_agent", result["executed_flow"])
        self.assertGreaterEqual(len(research_agent_entries), 1)
        self.assertEqual(research_agent_entries[0]["result"]["status"], "completed")
        self.assertGreaterEqual(len(result["research"]["findings"]), 1)
        self.assertTrue(mock_openai.called)
        self.assertTrue(mock_urlopen.called)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}, clear=True)
    @patch("multi_agent_core.llm.OpenAI", return_value=FakeOpenAIClient())
    def test_next_step_is_agent_backed_and_saved(self, mock_openai: object) -> None:
        task = "create file generated/hello.py"
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_task(task, project_root=temp_dir)

        next_step_entries = [entry for entry in result["history"] if entry["agent"] == "next_step"]

        self.assertIn("action", result["next_step"])
        self.assertIn("confirmed_by", result["next_step"])
        self.assertEqual(result["next_step"]["confirmed_by"], ["strategist", "analyzer", "session_strategist"])
        self.assertGreaterEqual(len(next_step_entries), 1)
        self.assertTrue(mock_openai.called)

    def test_session_strategist_can_continue_when_more_work_exists(self) -> None:
        session_strategy = SessionStrategist().run(
            {
                "current_round": 1,
                "_max_rounds": 2,
                "critique": {"status": "revise"},
                "next_step": {"status": "needs_work", "action": "Apply the latest fixes."},
            }
        )

        self.assertTrue(session_strategy["continue_session"])
        self.assertEqual(session_strategy["guidance"], "Apply the latest fixes.")

    def test_session_strategist_decomposes_large_task(self) -> None:
        session_strategy = SessionStrategist().run(
            {
                "task": "write intro and write summary and write final note",
                "current_round": 1,
                "_max_rounds": 2,
                "critique": {},
                "next_step": {},
            }
        )

        self.assertEqual(
            session_strategy["subtasks"],
            ["write intro", "write summary", "write final note"],
        )
        self.assertEqual(session_strategy["current_subtask"], "write intro")

    def test_task_board_marks_statuses(self) -> None:
        board = TaskBoard().run(
            {
                "subtasks": ["write intro", "write summary", "write final note"],
                "current_subtask": "write summary",
                "completed_subtasks": ["write intro"],
                "critique": {"status": "revise"},
            }
        )

        statuses = {item["task"]: item["status"] for item in board["items"]}
        self.assertEqual(statuses["write intro"], "done")
        self.assertEqual(statuses["write summary"], "blocked")
        self.assertEqual(statuses["write final note"], "queued")

    def test_priority_agent_ranks_blocked_task_highest(self) -> None:
        priorities = PriorityAgent().run(
            {
                "task_board": {
                    "items": [
                        {"task": "write intro", "status": "done"},
                        {"task": "write summary", "status": "blocked"},
                        {"task": "write final note", "status": "queued"},
                    ]
                },
                "critique": {"status": "revise"},
            }
        )

        self.assertEqual(priorities["next_task"], "write summary")
        self.assertEqual(priorities["items"][0]["status"], "blocked")

    def test_escalation_agent_requests_human_help_for_stuck_session(self) -> None:
        escalation = EscalationAgent().run(
            {
                "final_result": {"status": "needs_work"},
                "recovery_plan": {"status": "needed", "steps": ["Fix the blocker."]},
                "policy": {"allowed": True},
                "critique": {"status": "revise"},
                "session_history": [
                    {"critique_status": "revise", "task_board": {"summary": {"blocked": 1}}},
                    {"critique_status": "revise", "task_board": {"summary": {"blocked": 1}}},
                ],
            }
        )

        self.assertTrue(escalation["needed"])
        self.assertIn("human", escalation["recommendation"].lower())

    def test_artifact_tracker_records_latest_build(self) -> None:
        tracked = ArtifactTracker().run(
            {
                "active_task": "create file generated/hello.py",
                "artifacts": {"items": []},
                "build": {
                    "path": "generated/hello.py",
                    "action": "write_file",
                    "content": "print('hello')\n",
                },
            }
        )

        self.assertEqual(tracked["latest"]["path"], "generated/hello.py")
        self.assertEqual(len(tracked["items"]), 1)

    def test_result_synthesizer_builds_final_summary(self) -> None:
        final_result = ResultSynthesizer().run(
            {
                "task": "write intro and write summary",
                "critique": {"status": "pass", "issues": []},
                "artifacts": {"items": [{"path": "generated/hello.py"}]},
                "completed_subtasks": ["write intro"],
                "current_subtask": "write summary",
                "next_step": {"action": "Review the generated file.", "status": "ready"},
                "build": {"content": "Draft result"},
            }
        )

        self.assertEqual(final_result["status"], "ready")
        self.assertIn("Session status: ready.", final_result["summary"])
        self.assertIn("generated/hello.py", final_result["artifacts"])

    def test_execution_policy_blocks_path_outside_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy = ExecutionPolicy().run(
                {
                    "project_root": temp_dir,
                    "active_task": "create file ../outside.py",
                    "artifacts": {"items": []},
                }
            )

        self.assertFalse(policy["allowed"])
        self.assertIn("inside project_root", policy["reason"])

    def test_tool_selector_sets_modes_for_python_file_task(self) -> None:
        selection = ToolSelector().run(
            {
                "active_task": "create file generated/hello.py",
                "routing": {"task_type": "file_task"},
            }
        )

        self.assertTrue(selection["modes"]["file_mode"])
        self.assertTrue(selection["modes"]["test_mode"])
        self.assertTrue(selection["modes"]["synthesis_mode"])

    def test_capability_report_summarizes_usage(self) -> None:
        report = CapabilityReport().run(
            {
                "tool_selection": {
                    "modes": {
                        "file_mode": True,
                        "test_mode": True,
                        "research_mode": False,
                        "synthesis_mode": True,
                    }
                },
                "artifacts": {"items": [{"path": "generated/hello.py"}]},
                "testing": {"checks": ["python syntax check passed"]},
                "research": {},
                "history": [
                    {"agent": "builder"},
                    {"agent": "artifact_tracker"},
                    {"agent": "tester"},
                    {"agent": "result_synthesizer"},
                    {"agent": "execution_policy"},
                ],
            }
        )

        self.assertIn("file_mode", report["available_modes"])
        self.assertIn("testing", report["used_capabilities"])
        self.assertIn("final_synthesis", report["used_capabilities"])

    def test_run_exporter_is_disabled_by_default(self) -> None:
        exported = RunExporter().run({"export_enabled": False})

        self.assertFalse(exported["enabled"])
        self.assertFalse(exported["written"])

    def test_run_exporter_writes_json_report_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            exported = RunExporter().run(
                {
                    "export_enabled": True,
                    "project_root": temp_dir,
                    "current_round": 2,
                    "task": "create file generated/hello.py",
                    "active_task": "create file generated/hello.py",
                    "final_result": {"status": "ready"},
                    "capability_report": {"used_capabilities": ["build"]},
                    "next_step": {"action": "Review the file"},
                    "completed_subtasks": ["create file generated/hello.py"],
                    "artifacts": {"items": [{"path": "generated/hello.py"}]},
                }
            )

            self.assertTrue(exported["enabled"])
            self.assertTrue(exported["written"])
            self.assertTrue(Path(exported["path"]).exists())

    def test_session_memory_loads_empty_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory = SessionMemory().run(
                {
                    "_memory_phase": "load",
                    "project_root": temp_dir,
                }
            )

        self.assertEqual(memory["status"], "empty")
        self.assertEqual(memory["entries"], [])

    def test_session_memory_saves_and_loads_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            saved = SessionMemory().run(
                {
                    "_memory_phase": "save",
                    "project_root": temp_dir,
                    "task": "write intro",
                    "final_result": {
                        "summary": "Session status: ready. Completed work: write intro.",
                        "status": "ready",
                        "artifacts": ["generated/hello.py"],
                    },
                    "capability_report": {"used_capabilities": ["build", "final_synthesis"]},
                    "next_step": {"action": "Review the file."},
                }
            )
            loaded = SessionMemory().run(
                {
                    "_memory_phase": "load",
                    "project_root": temp_dir,
                }
            )

        self.assertEqual(saved["status"], "saved")
        self.assertEqual(loaded["status"], "loaded")
        self.assertEqual(len(loaded["entries"]), 1)
        self.assertIn("write intro", loaded["latest_summary"])

    def test_recovery_planner_returns_steps_for_stuck_session(self) -> None:
        recovery = RecoveryPlanner().run(
            {
                "final_result": {"status": "needs_work"},
                "critique": {"issues": ["Top issue"]},
                "testing": {"stdout": "FAIL", "stderr": "AssertionError"},
                "policy": {"allowed": False, "reason": "File actions must stay inside project_root."},
                "debugging": {"debug_notes": ["Investigate the failing test."]},
            }
        )

        self.assertEqual(recovery["status"], "needed")
        self.assertGreaterEqual(len(recovery["steps"]), 3)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}, clear=True)
    @patch("multi_agent_core.llm.OpenAI", return_value=FakeOpenAIClient())
    def test_orchestrator_records_policy_block(self, mock_openai: object) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_task("create file ../outside.py", project_root=temp_dir)

        self.assertFalse(result["policy"]["allowed"])
        self.assertEqual(result["critique"]["status"], "revise")
        self.assertTrue(any(entry["agent"] == "execution_policy" for entry in result["history"]))
        self.assertTrue(mock_openai.called)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}, clear=True)
    @patch("multi_agent_core.llm.OpenAI", return_value=FakeOpenAIClient())
    def test_orchestrator_tracks_completed_subtasks(self, mock_openai: object) -> None:
        result = run_task("write intro and write summary", project_root=str(ROOT))

        self.assertEqual(result["subtasks"], ["write intro", "write summary"])
        self.assertGreaterEqual(len(result["completed_subtasks"]), 1)
        self.assertIn("active_task", result["session_history"][0])
        self.assertTrue(mock_openai.called)


if __name__ == "__main__":
    unittest.main()
