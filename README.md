# 0langas Skill Center

A public collection of custom agent skills for Codex, Claude Code, Kimi Code, and other AI development workflows.

This repo is intended to grow into a broader skill center, not a single-purpose package. Skills here may target one agent client, multiple clients, or general repeatable engineering workflows.

## Layout

- Top-level skill folders, such as `official-ai-devdocs/`, are the canonical source directories.
- `.claude/skills/` exposes compatible skills to Claude Code.
- `.kimi-code/skills/` exposes compatible skills to Kimi Code.
- `.codex/skills/` keeps Codex-facing skills grouped with other Codex project files. Current Codex docs list `.agents/skills` as the official repo auto-discovery path, so this folder is an organized source/mirror unless your Codex setup explicitly supports or installs from it.
- Provider discovery directories may use symlinks back to the canonical top-level skill folder to avoid duplicate copies.

## Skills

| Skill | Purpose | Provider compatibility |
| --- | --- | --- |
| `official-ai-devdocs` | Requires official provider documentation lookup before provider-specific setup, syntax, plugin, connector, MCP, hook, skill, auth, model-routing, or compatibility work for Codex, Claude Code, and Kimi Code. | Codex, Claude Code, Kimi Code |

## Install Notes

Clone the repository into any project or shared skills location that your agent client can scan.

For project-local discovery:

- Claude Code: keep `.claude/skills/official-ai-devdocs`.
- Kimi Code: keep `.kimi-code/skills/official-ai-devdocs`.
- Codex: use the canonical `official-ai-devdocs/` folder or `.codex/skills/official-ai-devdocs` as the clean source, then install or symlink it into a Codex-supported skills location if your Codex version still requires `.agents/skills`.
