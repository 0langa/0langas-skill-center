---
name: tri-client-skill-port
description: Use when creating, importing, renaming, or repairing a skill that should work across Codex, Claude Code, and Kimi Code. This skill ports a canonical SKILL.md into a tri-client-compatible shape, verifies frontmatter fields, preserves provider-specific metadata, checks official docs evidence before discovery claims, and prepares provider discovery links without duplicating content.
when_to_use: When a skill needs to support Codex, Claude Code, and Kimi Code; when moving a skill between .agents, .codex, .claude, .kimi-code, ~/.codex/skills, ~/.claude/skills, or ~/.kimi-code/skills; when frontmatter or discovery behavior is uncertain; when importing an existing skill into this skill center.
type: prompt
whenToUse: When a skill needs to support Codex, Claude Code, and Kimi Code; when moving a skill between .agents, .codex, .claude, .kimi-code, ~/.codex/skills, ~/.claude/skills, or ~/.kimi-code/skills; when frontmatter or discovery behavior is uncertain; when importing an existing skill into this skill center.
disableModelInvocation: false
---

# Tri-Client Skill Port

Use this skill to make one canonical skill directory usable by Codex, Claude Code, and Kimi Code without creating three drifting copies.

## Dependency Order

Before making provider claims, use `official-docs-citation-cache` or `official-ai-devdocs` to verify and record the current docs evidence. Then port the skill.

## Canonical Layout

For this repo, keep the source skill at:

```text
<repo>/<skill-name>/SKILL.md
```

Provider-facing links should point back to that canonical folder:

```text
<repo>/.codex/skills/<skill-name>
<repo>/.claude/skills/<skill-name>
<repo>/.kimi-code/skills/<skill-name>
```

For Codex user-wide availability, use a link under:

```text
~/.codex/skills/<skill-name>
```

Do not copy the same skill into multiple provider folders unless symlinks or junctions are impossible.

## Frontmatter Contract

Use a frontmatter shape that all three clients can tolerate:

```yaml
---
name: skill-name
description: Short but trigger-rich description.
when_to_use: Claude-compatible trigger guidance.
type: prompt
whenToUse: Kimi-compatible trigger guidance.
disableModelInvocation: false
---
```

Rules:

- `name` must match the canonical directory name.
- `description` must include both purpose and trigger contexts.
- `when_to_use` and `whenToUse` should be semantically equivalent.
- Keep `type: prompt` unless the Kimi docs and task clearly require another type.
- Preserve any existing safe provider-specific fields that do not break other clients.
- Do not add unsupported fields just because another skill has them.

## Porting Workflow

1. Inspect the source skill and existing provider copies.
2. Check official docs evidence for any discovery, frontmatter, or install claim.
3. Choose the canonical directory.
4. Normalize frontmatter to the contract.
5. Preserve the body behavior unless the user asked for a rewrite.
6. Create or repair provider discovery links.
7. Add or update `evals/evals.json` if trigger behavior matters.
8. Report exactly what changed and any provider caveats.

## Conflict Policy

- If provider copies differ, do not merge blindly. Diff them and classify differences as content, metadata, or formatting.
- Prefer the newest user-authored canonical source when timestamps and git history are clear.
- Preserve provider-only behavior in a dedicated section named `Provider Notes`.
- If a field is unsupported by one provider, keep it only when that provider ignores unknown frontmatter safely; otherwise move it into the body.

## Output

```json
{
  "action": "tri-client-port",
  "skill": "skill-name",
  "canonical": "skill-name/SKILL.md",
  "links": [".codex/skills/skill-name", ".claude/skills/skill-name", ".kimi-code/skills/skill-name"],
  "docs_evidence": [".ai/official-docs-cache/notes/codex-skill-discovery.md"],
  "status": "ported"
}
```

