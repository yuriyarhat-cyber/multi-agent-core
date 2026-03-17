# multi-agent-core

`multi-agent-core` is a very small Python library for a simple agent workflow.

It now uses the real OpenAI API for text generation.

## What this repository is

This is a starter project for simple multi-agent experiments.

It is:

- standalone
- easy to copy into another repository
- small and readable

## Main idea

The flow is always:

1. `Planner` makes a short list of steps
2. `Builder` creates output for one step
3. `Critic` checks that output
4. if needed, the step is tried again

The `Orchestrator` runs that flow for you.

## Files

- `src/multi_agent_core/orchestrator.py`  
  Runs the full planner -> builder -> critic flow.

- `src/multi_agent_core/agents.py`  
  Contains the `Planner`, `Builder`, and `Critic`.

- `src/multi_agent_core/state.py`  
  Creates the shared state dictionary.

- `src/multi_agent_core/llm.py`  
  Contains the OpenAI API call.

- `examples/simple_run.py`  
  A simple example you can run right away.

- `tests/test_smoke.py`  
  A basic test to confirm the flow works.

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

## Reuse in another repository

The simplest option is to copy `src/multi_agent_core` into another project and import it:

```python
from multi_agent_core import Orchestrator, create_state

task = "Write a short welcome message"
state = create_state(task)
result = Orchestrator().run(task, state)
```

## How it works now

- `src/multi_agent_core/llm.py` sends prompts to OpenAI
- it reads the key from `OPENAI_API_KEY`
- it reads the model from `OPENAI_MODEL`
- if the key is missing, it raises a clear error
- if the API call fails, it raises a clear error

That keeps the rest of the library simple.
