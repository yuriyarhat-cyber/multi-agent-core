# multi-agent-core

`multi-agent-core` is a small Python library that can take a task, route it, plan it, build a result, and review the result.

It is meant to be easy to reuse in other repositories.

## Simplest way to use it

```python
from multi_agent_core import run_task

result = run_task("Write a short welcome message")
print(result["task"])
print(result["routing"])
print(result["plan"])
```

## Main idea

The library does this:

1. `Router` looks at the task and chooses a task type
2. `Planner` makes a short list of steps
3. `Builder` creates output for one step
4. `Critic` checks that output
5. if needed, the step is tried again

The `Orchestrator` runs that flow for you.

Different task types can use different flows:

- `file_task`: `planner -> builder -> critic`
- `text_task`: `planner -> builder -> critic`
- `research_task`: `planner -> builder -> critic -> research_critic`
- `general_task`: `planner -> builder -> critic`

## Run the example

From the repository root:

```bash
python examples/simple_run.py
```

The example prints the OpenAI model name before it starts.

## Set up the API key

You must set `OPENAI_API_KEY` before running the system.

Important:

- do not paste your API key into Python files
- do not hardcode your API key anywhere in this repository
- use the `OPENAI_API_KEY` environment variable

You can also set `OPENAI_MODEL` if you want to choose a model yourself.

If `OPENAI_MODEL` is not set, the project uses:

`gpt-5.3-codex`

Example on Windows:

```bash
set OPENAI_API_KEY=your_key_here
set OPENAI_MODEL=gpt-5.3-codex
python examples/simple_run.py
```

If `OPENAI_API_KEY` is missing, the program stops with:

`OPENAI_API_KEY not set`

## Run the tests

From the repository root:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

The tests do not make real network calls. They replace the OpenAI client with a local stub.

## How to use this in another project

Option A: connect a local neighboring folder during development

```bash
pip install -e ../multi-agent-core
```

Option B: install from Git later

```bash
pip install git+https://github.com/yuriyarhat-cyber/multi-agent-core.git
```

Then use it like this:

```python
from multi_agent_core import run_task
```

## Minimal usage from another project

```python
from multi_agent_core import run_task

result = run_task("Write a short welcome message")

print(result["routing"])
print(result["plan"])
print(result["build"])
print(result["critique"])
```

## What the result contains

The returned dictionary includes:

- `task`
- `routing`
- `executed_flow`
- `plan`
- `build`
- `critique`
- `history`

## Main public API

- `run_task`
- `Orchestrator`
- `create_state`
- `Router`
- `Planner`
- `Builder`
- `Critic`
- `ResearchCritic`
- `codex_llm`
