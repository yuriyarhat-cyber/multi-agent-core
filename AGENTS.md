# Repository Instructions

This repository is a small, reusable Python library for simple multi-agent orchestration.

## Working style

- Prefer simple solutions over clever abstractions.
- Keep the project standard-library only unless explicitly asked otherwise.
- Keep the code small, readable, and modular.
- Do not introduce framework complexity without a clear reason.

## Repository maintenance

- Keep library code in `src/multi_agent_core/`.
- Keep runnable examples in `examples/`.
- Keep tests in `tests/`.
- Update `README.md` whenever the repository structure or usage changes.
- Preserve the repository as standalone and reusable, not tied to one business project.

## Code changes

- After making code changes, run the example if relevant.
- After making code changes, run the test suite.
- Prefer clear names and predictable data structures.
- Avoid adding configuration layers unless they solve a real problem.

## LLM integration

- The current LLM entry point is `src/multi_agent_core/llm.py`.
- Keep the LLM interface simple so it can be replaced later without rewriting the whole library.
