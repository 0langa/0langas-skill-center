---
name: official-docs-first
description: Use automatically whenever a task involves Codex, Claude Code, Kimi Code, or projects meant to work across multiple AI coding clients. This skill is required for any question or code change involving provider configuration, config syntax, plugins, skills, connectors, MCP servers, hooks, subagents, memory/instructions files, auth setup, environment variables, CLI commands, IDE/desktop/web surfaces, model/provider routing, migrations, or compatibility between Codex, Claude Code, and Kimi Code. Use it even when the user does not explicitly ask for documentation, because official docs should be checked before guessing provider-specific shapes or behavior.
---

# Official Docs First

Use this skill to keep multi-client agent projects grounded in current provider documentation. The goal is simple: when provider behavior, syntax, setup, or compatibility can be looked up, verify it from the official docs before answering or editing files.

This applies especially to projects targeting more than one AI coding client, mainly:

- OpenAI Codex
- Anthropic Claude Code
- Kimi Code

## Core Rule

Before making a provider-specific claim or changing provider-specific files, consult the relevant official documentation first. Do not rely on memory for config keys, plugin structure, connector setup, MCP setup, hook syntax, command names, auth paths, environment variables, model IDs, or cross-client compatibility behavior.

If the official docs do not establish the needed fact, say that plainly and proceed with bounded uncertainty. Prefer a small, verified answer over a broad guessed one.

## Official Sources

Use these entry points and then navigate to the most specific page for the task.

| Provider | Official docs entry point | Use for |
| --- | --- | --- |
| Codex | `https://developers.openai.com/codex` | Codex CLI/app/web/IDE behavior, `config.toml`, `AGENTS.md`, skills, plugins, MCP, hooks, permissions, automations, subagents, integrations |
| Claude Code | `https://code.claude.com/docs/en/overview` | Claude Code CLI/desktop/web/IDE behavior, `.claude` directory, `CLAUDE.md`, skills, hooks, MCP, sessions, permission modes, settings, commands |
| Kimi Code | `https://www.kimi.com/code/docs/en/` | Kimi Code CLI/VS Code behavior, configuration files, providers/models, overrides, environment variables, MCP, skills, plugins, agents, hooks, third-party coding-agent setup |

For Claude Code, first fetch or inspect `https://code.claude.com/docs/llms.txt` when possible. The overview page points to that file as the complete documentation index, and it is the best way to discover the current page to read next.

## Lookup Workflow

1. Identify which provider(s) the task touches.
2. Open the official docs entry point for each touched provider.
3. Navigate to the narrowest official page that owns the needed fact.
4. Verify exact syntax, filenames, command names, environment variables, config nesting, required fields, and current limitations.
5. Capture the source URL(s) in your notes and cite or mention them in the user-facing result when the answer depends on provider docs.
6. Only then answer, edit files, or recommend a setup.

When multiple clients are involved, check each provider's docs independently. Similar concepts often have different names or file locations across clients.

## What Requires Documentation First

Always verify first for these task types:

- Creating or editing Codex, Claude Code, or Kimi Code config files.
- Adding skills, plugins, hooks, MCP servers, slash commands, subagents, or connector/app setup.
- Writing installation, onboarding, or migration instructions for any of the three clients.
- Mapping one provider's concept to another, such as Codex `AGENTS.md` versus Claude `CLAUDE.md`, or provider-specific plugin formats.
- Setting model IDs, base URLs, API endpoints, auth flows, or provider routing for Kimi/OpenAI/Anthropic-compatible clients.
- Troubleshooting provider behavior, CLI flags, permission modes, sandboxing, browser/desktop/IDE features, or automation features.
- Building shared repo guidance intended to steer more than one coding agent.

## Source Priority

Prefer the most authoritative source available:

1. Official docs pages from the provider domains listed above.
2. Official provider docs indexes, markdown docs, or `llms.txt` files that point to exact docs pages.
3. Official CLI help output from an installed provider CLI, but only as a supplement to docs unless the user specifically asks about the installed local version.
4. Existing repo files, examples, or memory, used only after official docs have established the provider shape.

Avoid third-party blog posts, old GitHub snippets, package README guesses, or model memory for provider-specific syntax unless official docs are unavailable and you label the result as unverified.

## Editing Rules

When changing files:

- Keep provider-specific sections separated unless the docs explicitly say the same file or setting applies to multiple clients.
- Preserve existing working config unless official docs show it is invalid or the user asks for migration.
- Add comments sparingly and only where they prevent future agents from confusing provider-specific formats.
- If docs conflict with current repo conventions, explain the conflict before making a broad change.
- If a syntax detail cannot be verified, leave a TODO or ask for confirmation rather than inventing a key or shape.

## Response Pattern

For docs-backed answers, use this compact shape:

1. Recommendation or change made.
2. Provider docs checked, with URLs.
3. Any uncertainty or provider differences that matter.

For implementation work, include the docs check in the final summary:

```text
Docs checked: Codex config docs, Claude Code settings docs, Kimi Code provider/model docs.
```

## Failure Mode

If you cannot reach the official docs:

1. Try the provider's docs index or search within the same official domain.
2. Use local CLI help only for installed-version behavior.
3. Tell the user exactly which docs could not be reached.
4. Avoid changing provider-specific syntax unless the repo already contains a working example or the user confirms the intended shape.

