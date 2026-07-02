# 0langas Skill Center

A public collection of custom agent skills for Codex, Claude Code, Kimi Code, and other AI development workflows.

This repo is intended to grow into a broader skill center, not a single-purpose package. Skills here may target one agent client, multiple clients, or general repeatable engineering workflows.

## Layout

- Top-level skill folders, such as `official-ai-devdocs/`, are the canonical source directories.
- `.agents/skills/` exposes compatible skills to Codex and Kimi Code.
- `.claude/skills/` exposes compatible skills to Claude Code.
- Provider discovery directories may use symlinks back to the canonical top-level skill folder to avoid duplicate copies.

## Skills

| Skill | Purpose | Provider compatibility |
| --- | --- | --- |
| `official-ai-devdocs` | Requires official provider documentation lookup before provider-specific setup, syntax, plugin, connector, MCP, hook, skill, auth, model-routing, or compatibility work for Codex, Claude Code, and Kimi Code. | Codex, Claude Code, Kimi Code |

## Install Notes

Clone the repository into any project or shared skills location that your agent client can scan. For project-local discovery, keep the `.agents/skills` and `.claude/skills` paths intact so compatible clients can find the relevant skills automatically.
