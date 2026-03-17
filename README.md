# multi-agent-core

`multi-agent-core` is a tiny Python library for running a simple multi-agent workflow.

It is designed to be:

- standalone
- easy to read
- easy to copy into another repository
- usable without internet access
- based only on the Python standard library

This first version uses three small agents:

1. `Planner`: breaks a task into steps
2. `Builder`: produces an output for the current step
3. `Critic`: checks the output and decides whether it passes or needs one more try

The orchestrator runs those agents in order and stores what happened in shared state.

## Repository layout

- `pyproject.toml`  
  Basic package metadata so the project can be installed later if needed.

- `README.md`  
  Human-friendly explanation of what this repository does and how to use it.

- `AGENTS.md`  
  Durable instructions for future Codex work in this repository.

- `src/multi_agent_core/__init__.py`  
  Public exports for the library.

- `src/multi_agent_core/orchestrator.py`  
  The main `Orchestrator` class that runs planner -> builder -> critic.

- `src/multi_agent_core/agents.py`  
  Small agent classes used by the orchestrator.

- `src/multi_agent_core/state.py`  
  Helper for creating the shared state dictionary.

- `src/multi_agent_core/llm.py`  
  A mock LLM function. This is the place to replace later if you want to connect a real model provider.

- `examples/simple_run.py`  
  A complete end-to-end example.

- `tests/test_smoke.py`  
  A basic smoke test using Python's built-in `unittest`.

## How the flow works

The library keeps a shared dictionary called `state`. All agents read from it and write to it.

The state always includes these keys:

- `task`
- `plan`
- `current_step`
- `build`
- `critique`
- `history`

The flow is:

1. Create a state object from a task
2. Run the planner once to create a step-by-step plan
3. For each step:
   - run the builder
   - run the critic
   - if the critic says `revise`, try again
   - stop after at most 3 tries for that step
4. Return the final state

Every attempt is saved in `history` so you can inspect what happened.

## Run the example

From the repository root:

```bash
python examples/simple_run.py
```

You should see:

- the original task
- the plan
- the most recent build output
- the most recent critique
- the saved history entries

## Run the tests

From the repository root:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## Reuse this library in another repository

The easiest path is:

1. Copy the `src/multi_agent_core` folder into your other repository
2. Import the pieces you need
3. Replace the mock LLM later if you want richer behavior

Example import:

```python
from multi_agent_core import Orchestrator, create_state

state = create_state("Draft a simple welcome message")
result = Orchestrator().run(task=state["task"], state=state)
```

If you want to install it as a package later, this repository already has a basic `pyproject.toml`.

## Where to replace the mock LLM

The replacement point is:

`src/multi_agent_core/llm.py`

Right now it contains a deterministic `codex_llm(prompt: str) -> str` function so the whole project works offline.

When you are ready to connect a real provider, keep the same function shape if possible. That will let the rest of the code stay simple.

## Why this version is intentionally small

This repository is meant to be a clean starting point, not a full framework.

It does not include:

- network calls
- external packages
- async orchestration
- persistence layers
- plugin systems

That keeps it easy to understand and easy to adapt.
