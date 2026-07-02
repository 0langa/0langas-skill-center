---
name: official-docs-citation-cache
description: Use when provider documentation has been consulted or should be reused for Codex, Claude Code, Kimi Code, plugin, skill, MCP, marketplace, config, hook, connector, install, or discovery work. This skill creates compact official-docs evidence notes so future agents do not repeat the same research or rely on memory. Use proactively after official docs lookup, before cross-provider claims, and when a task says docs were checked.
when_to_use: When official provider documentation was checked or should be cached for future skill/plugin work; when repeated Codex, Claude Code, or Kimi Code doc lookup would waste time; when an implementation depends on exact official syntax, paths, discovery behavior, or marketplace shape.
type: prompt
whenToUse: When official provider documentation was checked or should be cached for future skill/plugin work; when repeated Codex, Claude Code, or Kimi Code doc lookup would waste time; when an implementation depends on exact official syntax, paths, discovery behavior, or marketplace shape.
disableModelInvocation: false
---

# Official Docs Citation Cache

Use this skill to turn one-time official documentation lookups into reusable evidence notes. The goal is not to create a private copy of docs; it is to save small, dated, source-linked facts that future agents can trust, refresh, or reject quickly.

## What This Skill Owns

- Record official documentation evidence used for provider-specific claims.
- Separate stable facts from likely-stale facts.
- Save exact source URLs, checked dates, and the claim the docs support.
- Prevent repeated broad web/docs searches for the same Codex, Claude Code, or Kimi Code setup question.
- Mark cached notes stale when provider docs may have changed.

Do not use this skill to answer provider questions by itself. Use it after or alongside official docs lookup. For actual provider behavior, follow `official-ai-devdocs` first.

## Cache Location

Default project cache:

```text
.ai/official-docs-cache/
├── index.json
└── notes/
    └── <provider>-<topic>.md
```

In this skill center repo, use the same location at the repository root. If a consuming repo already has a docs-cache convention, follow that convention but preserve the record schema below.

## Record Schema

Each note should contain:

```yaml
provider: codex|claude-code|kimi-code|openai|anthropic|moonshot
topic: short-topic-key
checked_at: YYYY-MM-DD
stability: stable|likely-changing|volatile
refresh_after_days: 7
sources:
  - url: https://...
    title: Human title
claims:
  - Exact claim this source supports, paraphrased.
used_by:
  - skill-name-or-task
```

Then add a short `## Notes` section with the minimum useful context. Keep quotes short. Prefer paraphrase.

## Workflow

1. Identify the claim that depends on official docs.
2. Check the existing cache index for the same provider/topic.
3. If the cached note is fresh enough, reuse it and cite the note plus original URL.
4. If stale or missing, consult official docs and update the note.
5. Add or update `.ai/official-docs-cache/index.json` with provider, topic, path, checked date, stability, and source URLs.
6. In final answers, cite original official docs, not only the cache note.

## Freshness Rules

- `volatile`: refresh every task. Use for current versions, marketplaces, auth, CLI behavior, pricing, or rollout-dependent details.
- `likely-changing`: refresh after 7 days. Use for provider paths, plugin shapes, MCP setup, config syntax, hooks, and skill discovery.
- `stable`: refresh after 30 days or when a related task fails. Use for conceptual docs that rarely change.

## Quality Bar

- Cache only official sources.
- Save the claim, not just a URL.
- Do not cache secrets, tokens, private mailbox content, or raw connector output.
- If docs conflict, record both sources and mark the note `volatile`.
- If the source did not establish the claim, record that as a negative finding instead of inventing a shape.

## Output

Return a compact result:

```json
{
  "action": "cached-doc-evidence",
  "provider": "codex",
  "topic": "skill-discovery",
  "note": ".ai/official-docs-cache/notes/codex-skill-discovery.md",
  "sources": ["https://developers.openai.com/codex/skills"],
  "fresh_until": "2026-07-09"
}
```

