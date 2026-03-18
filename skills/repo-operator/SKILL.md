---
name: repo-operator
description: Operate safely inside an existing repository. Use when Codex needs to inspect a repo, choose a minimal change path, edit files carefully, run checks, and summarize exactly what changed without unnecessary churn.
---

# Repo Operator

Work inside a repository with caution and clear steps.

## Workflow

1. Inspect the repo before changing code.
2. Find the smallest set of files that matter.
3. Prefer small, reversible edits.
4. Run the relevant checks after changes.
5. Summarize what changed, what was verified, and any remaining risk.

## Rules

- Do not widen scope without a reason.
- Do not rewrite unrelated files.
- Respect existing project structure and style.
- Preserve user changes.
- Prefer one clean change over many speculative changes.

## Default checks

When practical:
- run the smallest relevant test
- run the project example if it is directly affected
- report anything not verified

## Output expectation

Always end with:
- what was changed
- what was checked
- what still needs attention, if anything
