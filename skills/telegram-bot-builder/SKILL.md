---
name: telegram-bot-builder
description: Create the first version of a Telegram bot project. Use when Codex needs to scaffold a Telegram bot, define commands and handlers, organize bot files, and reach a first working bot flow with minimal structure.
---

# Telegram Bot Builder

Build the first working bot before adding advanced features.

## Workflow

1. Define the first bot outcome:
- greeting
- command handling
- simple booking
- simple FAQ

2. Limit the first version to a few clear commands.
3. Create a simple bot structure:
- bot entrypoint
- handlers
- config
- tests if practical

4. Implement one complete command flow.
5. Add one short run instruction.
6. End with the next bot feature to build.

## Rules

- Start with 2-4 commands maximum.
- Keep command names plain.
- Keep state handling simple.
- Keep environment variables explicit.
- Do not add complex persistence unless the first feature requires it.

## Good first commands

- `/start`
- `/help`
- one main domain command such as `/book`, `/list`, or `/status`

## Output expectation

Produce a first bot scaffold that a developer can run and inspect quickly.

