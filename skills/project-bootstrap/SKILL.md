---
name: project-bootstrap
description: Turn a raw idea into a small first working project. Use when Codex needs to start a new project from scratch, define a minimal scope, choose a simple structure, create the first files, and reach a first runnable or reviewable version without overengineering.
---

# Project Bootstrap

Start from the smallest useful version of the idea.

## Workflow

1. Restate the idea as one short project goal.
2. Reduce the goal to the smallest version that can work.
3. Choose a simple stack that already fits the user's environment.
4. Create the first file structure.
5. Add one runnable entrypoint or example.
6. Add one smoke test if the project type makes sense for it.
7. End with a short summary of what exists now and what should come next.

## Rules

- Prefer one small working version over a broad plan.
- Prefer the simplest stack that can deliver the first version.
- Do not introduce frameworks or services without a clear reason.
- Keep naming plain and predictable.
- Keep the first scaffold easy to read for a non-expert.

## Default output shape

Produce:
- a minimal folder structure
- the first runnable file or entrypoint
- one short README section or usage note
- one smoke test when practical

## When the idea is too broad

If the request is large, reduce it to:
- one user-facing outcome
- one runtime path
- one storage choice
- one test path

Example reduction:
- "Build a startup platform"
- becomes
- "Create the first working service for user signup"

