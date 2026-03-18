---
name: api-tester
description: API testing and contract review for HTTP endpoints, webhooks, auth, validation, integration behavior, and failure handling. Use when Codex should test or review API reliability, compare docs to implementation, inspect status codes and payloads, or evaluate runtime behavior when a live environment exists.
---

# API Tester

## Workflow
- Identify the available surface first: endpoints, webhook handlers, external integrations, schemas, and environment requirements.
- If a runnable environment exists, exercise the API and inspect success, validation, auth, timeout, and failure paths.
- If a runnable environment does not exist, perform a contract review from code and configuration without pretending it was live tested.
- Check request shape, response shape, status codes, idempotency, retries, observability, and error messages.
- Compare declared behavior in docs with actual behavior in code.

## Review Standard
- Prefer reproducible findings over generic advice.
- Highlight broken user journeys, unsafe defaults, and silent failures.
- Call out missing dependencies, missing env vars, and endpoints that report healthy while key integrations are broken.
- Distinguish clearly between tested behavior, inferred behavior, and unverified risk.

## Output
- List findings by severity.
- Summarize what was actually tested versus reviewed statically.
- End with the smallest set of fixes that would materially improve API reliability.
