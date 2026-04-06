# Repository Instructions

This repository is a small, reusable Python library for simple multi-agent orchestration.

## Working style

- Prefer simple solutions over clever abstractions.
- Keep the project standard-library only unless explicitly asked otherwise.
- Keep the code small, readable, and modular.
- Do not introduce framework complexity without a clear reason.

## Shorthand Commands

- Treat the user command `33` as a repository hygiene, release-readiness, and deploy pass for this repository.
- On `33`, always inspect and report at least:
  - whether there are uncommitted local changes
  - whether the working tree is clean
  - whether local `main` is ahead, behind, or diverged from `origin/main`
  - whether there are fresh local commits not yet pushed
  - whether there are extra local branches besides `main`
- On `33`, if there are uncommitted local changes, Codex must:
  - inspect them for relevance and safety
  - keep only clearly justified changes in scope
  - validate them as needed
  - commit them if they are coherent and safe to ship
  - report clearly if any local change is not safe to commit
- On `33`, if local `main` is ahead of `origin/main`, Codex must push those commits to `origin/main`.
- On `33`, Codex must inspect local branches and aim to keep only the main working branch `main`.
- On `33`, Codex may delete extra local branches only when all of the following are true:
  - the branch is not `main`
  - the branch is fully merged or clearly obsolete
  - deleting it does not discard unique user work
  - no force-push, history rewrite, or remote branch deletion is required
- On `33`, never silently delete unmerged branches, rewrite history, discard local edits, or remove remote branches.
- On `33`, after commits and pushes are complete, verify the tree is clean again.
- On `33`, if the repository is clean, `main` is aligned with `origin/main`, and documented deploy preconditions are satisfied, proceed with the normal deploy flow and post-deploy verification.
- On `33`, if deploy preconditions are not satisfied, report the exact blocker instead of guessing.

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
- Keep tests offline by default.
- Never hardcode secrets or API keys.
- Prefer environment variables for configuration.
- Update `README.md` whenever setup steps change.

## LLM integration

- The current LLM entry point is `src/multi_agent_core/llm.py`.
- Keep the LLM interface simple so it can be replaced later without rewriting the whole library.
- Keep the provider adapter simple and isolated from the rest of the package.
