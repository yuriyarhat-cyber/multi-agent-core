---
name: backend-scaffold
description: Create a small backend project scaffold. Use when Codex needs to build or extend a simple backend, API service, worker, or Python server project with clear folders, entrypoints, tests, and minimal moving parts.
---

# Backend Scaffold

Create a backend that is small, runnable, and easy to extend.

## Workflow

1. Identify the backend type:
- API
- background worker
- CLI service
- webhook receiver

2. Choose the smallest structure that fits:
- entrypoint
- core logic
- storage or state layer
- tests

3. Create only the files needed for the first useful flow.
4. Add one runnable path.
5. Add one test path.
6. Summarize the service contract and next backend step.

## Rules

- Prefer a thin vertical slice over broad architecture.
- Prefer standard library or already-approved dependencies.
- Separate app startup from business logic.
- Make config obvious and local.
- Avoid adding infra abstractions too early.

## Minimum scaffold

Try to produce:
- app entrypoint
- one core module
- one test file
- one short usage example

## Good defaults

- Keep handlers thin.
- Keep state mutations explicit.
- Keep validation obvious.
- Name modules by job, not by vague layers.

