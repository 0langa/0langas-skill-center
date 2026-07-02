# 0langas Skill Center

A public collection of custom agent skills for Codex, Claude Code, Kimi Code, and other AI development workflows.

This repo is intended to grow into a broader skill center, not a single-purpose package. Skills here may target one agent client, multiple clients, or general repeatable engineering workflows.

## Layout

- Top-level skill folders, such as `official-ai-devdocs/`, are the canonical source directories.
- `.claude/skills/` exposes compatible skills to Claude Code.
- `.kimi-code/skills/` exposes compatible skills to Kimi Code.
- `.codex/skills/` keeps Codex-facing skills grouped with other Codex project files.
- Provider discovery directories may use symlinks back to the canonical top-level skill folder to avoid duplicate copies.

## Skills

| Skill | Purpose | Provider compatibility |
| --- | --- | --- |
| `official-ai-devdocs` | Requires official provider documentation lookup before provider-specific setup, syntax, plugin, connector, MCP, hook, skill, auth, model-routing, or compatibility work for Codex, Claude Code, and Kimi Code. | Codex, Claude Code, Kimi Code |
| `muteman` | Mutes coding-agent chat into a strict emoji-only protocol while preserving normal planning, editing, testing, validation, and safety behavior. | Codex, Claude Code, Kimi Code |

## Candidate Skills

These are high-value autoactivating skills that would fit this collection:

- `repo-intake-map`: activate in unfamiliar repos; build a concise project map, commands list, ownership boundaries, and risk notes before edits.
- `failure-loop`: activate on failing tests/builds/CI; reproduce, isolate, fix, rerun, and record failure evidence.
- `docs-truth-guard`: activate when editing docs; verify README/API/docs claims against code, commands, and current behavior.
- `config-schema-sentinel`: activate when touching config files; find official schema/docs, validate syntax, and avoid invented keys.
- `dependency-upgrade-sherpa`: activate for dependency bumps; read changelogs, apply narrow updates, run compatibility checks, and document breaking changes.
- `secret-hygiene`: activate around `.env`, auth, keys, logs, and config; prevent leaks and suggest safe local handling.
- `release-note-crafter`: activate near version bumps, changelogs, tags, or PR wrap-up; produce concise user-facing release notes from diffs.
- `test-gap-finder`: activate after bug fixes or behavior changes; identify missing regression coverage and add focused tests.
- `pr-review-hardener`: activate before push/PR; inspect diff like a reviewer for regressions, missing tests, risky behavior, and sloppy docs.
- `cross-agent-handoff`: activate when work may move between Codex, Claude Code, and Kimi Code; write portable state, commands, decisions, and next steps.

## Install Notes

Clone the repository into any project or shared skills location that your agent client can scan.

For project-local discovery:

- Claude Code: keep `.claude/skills/<skill-name>`.
- Kimi Code: keep `.kimi-code/skills/<skill-name>`.
- Codex: keep `.codex/skills/<skill-name>` for clean provider-specific organization. For user-wide discovery in Codex, install or symlink the canonical skill into your Codex skills home, for example `~/.codex/skills/<skill-name>`.
