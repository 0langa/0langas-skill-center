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

These are workflow-specific, autoactivating skills that would fit this collection:

- `skill-center-curator`: activate when working in this repo; enforce the canonical top-level skill folder plus `.codex`, `.claude`, and `.kimi-code` symlink layout, update README tables, validate frontmatter across providers, and optionally link Codex user-home installs.
- `tri-client-skill-port`: activate when importing or writing a skill meant for Codex, Claude Code, and Kimi Code; add compatible metadata, normalize trigger descriptions, preserve client-specific fields, and check official docs before claiming discovery behavior.
- `skill-trigger-evalsmith`: activate when a skill's trigger behavior matters; generate realistic should-trigger and should-not-trigger prompts, store eval sets beside the skill, and tune the frontmatter description without making it keyword spam.
- `agent-install-sync`: activate after adding or renaming a skill; reconcile repo symlinks, `~/.codex/skills`, `.claude/skills`, `.kimi-code/skills`, and any installed `.agents` source without duplicating canonical content.
- `official-docs-citation-cache`: activate when repeated official-docs lookups are needed; fetch provider docs indexes, cache source URLs and exact sections, and leave compact evidence notes usable by future agents.
- `recall-memory-hygiene`: activate when a durable lesson, repo convention, or recurring failure appears; decide whether it belongs in Recall, README, skill instructions, or repo config, then save only reusable signal.
- `addon-archive-miner`: activate when you mention looking for new addons, skills, plugins, or automation ideas; search the local addon archive for gaps, avoid duplicates of installed skills, and propose only workflow-specific candidates.
- `handoff-cck-bridge`: activate when work crosses Codex, Claude Code, and Kimi Code; write handoffs that include current repo state, command history, docs checked, symlink/install assumptions, and next safe actions.
- `windows-agent-pathguard`: activate when editing installs, symlinks, PATH, PowerShell commands, or Windows-local agent setup; verify absolute paths, avoid fragile shell mixing, and keep user-home versus repo-local installs explicit.
- `skill-release-publisher`: activate when a skill is ready to publish; verify public-safe content, update repo description/README, commit with clean history, push, and prepare a compact release note or install snippet.

## Install Notes

Clone the repository into any project or shared skills location that your agent client can scan.

For project-local discovery:

- Claude Code: keep `.claude/skills/<skill-name>`.
- Kimi Code: keep `.kimi-code/skills/<skill-name>`.
- Codex: keep `.codex/skills/<skill-name>` for clean provider-specific organization. For user-wide discovery in Codex, install or symlink the canonical skill into your Codex skills home, for example `~/.codex/skills/<skill-name>`.
