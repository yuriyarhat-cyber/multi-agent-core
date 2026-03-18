# multi-agent-core

`multi-agent-core` is a small Python library for running one task through a simple autonomous agent workflow.

It can:
- understand the task type
- plan the work
- build a result
- review and retry when needed
- keep a little memory across runs
- return a clean final summary

## The easiest way to use it

```python
from multi_agent_core import Settings, run_task

result = run_task(
    "Write a short welcome message",
    settings=Settings(),
)

print(result["final_result"]["summary"])
```

## The easiest CLI use

After installing the package:

```bash
multi-agent-core "Write a short welcome message"
```

## What you need first

Set your OpenAI API key in the environment.

Windows:

```bash
set OPENAI_API_KEY=your_key_here
```

Optional model override:

```bash
set OPENAI_MODEL=gpt-5.3-codex
```

Do not paste the API key into Python files.

## Two official ways to use the library

### 1. Python code

```python
from multi_agent_core import Settings, run_task

settings = Settings(
    project_root="C:/my-project",
    autonomous_rounds=2,
    max_iterations_per_step=3,
    export_enabled=False,
)

result = run_task("Create file generated/hello.py", settings=settings)

print(result["final_result"])
print(result["next_step"])
```

### 2. CLI

```bash
multi-agent-core "Create file generated/hello.py" --project-root C:/my-project --rounds 2 --iterations 3
```

## What the library returns

The most useful fields are:
- `final_result`
- `next_step`
- `escalation`
- `task_board`
- `capability_report`

If you want the full internal state, it is also returned.

## What happens inside

The library runs a compact agent workflow:

1. route the task
2. choose useful tool modes
3. plan and build
4. test and review
5. retry if useful
6. synthesize the final result
7. prepare recovery or escalation if the run is stuck

For larger tasks, it can split work into subtasks and manage them on a small internal task board.

## Examples

From the repository root:

```bash
python examples/simple_run.py
python examples/research_run.py
python examples/use_from_another_project.py
```

## Run the tests

```bash
python -m unittest discover -s tests -p "test_*.py"
```

The tests stay offline by default.

## Use it in another project

Local development:

```bash
pip install -e ../multi-agent-core
```

Later from Git:

```bash
pip install git+https://github.com/yuriyarhat-cyber/multi-agent-core.git
```

Then:

```python
from multi_agent_core import Settings, run_task
```

## Move this setup to another computer

This repository now stores both:
- the Python multi-agent library
- your Codex `skills`

The library agents already live in:

```text
src/multi_agent_core/
```

The mirrored Codex skills now live in:

```text
skills/
```

On the new computer:

1. Clone this GitHub repository.
2. Install the Python package if you want to use the library.
3. Copy the skills into Codex:

```bash
python scripts/install_codex_skills.py
```

If the target machine already has skill folders and you want to overwrite them:

```bash
python scripts/install_codex_skills.py --force
```

System-managed Codex skills from `.system/` are not mirrored here. The repository stores the non-system skills you want to keep and move.

## Main public API

- `run_task`
- `Settings`
- `Orchestrator`
- `create_state`
- `Router`
- `Planner`
- `Builder`
- `Tester`
- `Critic`
- `ResearchCritic`

Advanced session agents are also exported from the package for lower-level use.
