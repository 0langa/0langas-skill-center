---
name: agent-install-sync
description: Use after adding, renaming, importing, moving, or deleting a skill in 0langas-skill-center or any local agent customization repo. This skill reconciles canonical skill directories, provider discovery links, user-level Codex skill links, stale .agents copies, and local install state across Codex, Claude Code, and Kimi Code without duplicating content. Use proactively when skill visibility, symlinks, or local installs may drift.
when_to_use: When a skill was added, renamed, imported, moved, deleted, or ported; when provider discovery links need repair; when ~/.codex/skills, .codex/skills, .claude/skills, .kimi-code/skills, or .agents/skills disagree; when a skill appears twice or not at all.
type: prompt
whenToUse: When a skill was added, renamed, imported, moved, deleted, or ported; when provider discovery links need repair; when ~/.codex/skills, .codex/skills, .claude/skills, .kimi-code/skills, or .agents/skills disagree; when a skill appears twice or not at all.
disableModelInvocation: false
---

# Agent Install Sync

Use this skill to keep local skill installs and provider discovery links aligned with the canonical source.

## Dependency Order

Use `tri-client-skill-port` before syncing if a skill is not already tri-client compatible. Use `skill-trigger-evalsmith` before publishing or broad install when activation behavior matters.

## Scope

This skill manages skill locations, not plugin cache cleanup. For broad plugin/cache dedupe, use `customization-control`.

Expected repo-local provider links:

```text
.codex/skills/<skill-name>
.claude/skills/<skill-name>
.kimi-code/skills/<skill-name>
```

Expected optional user-level Codex link:

```text
~/.codex/skills/<skill-name>
```

Legacy roots such as `~/.agents/skills` are inspected so duplicates can be reported, but do not delete them automatically.

## Sync Workflow

1. Inventory canonical top-level skill directories.
2. Ignore infrastructure directories: `.git`, `.codex`, `.claude`, `.kimi-code`, `scripts`, `tests`, `.ai`, `.handoff`.
3. For each canonical skill, verify `SKILL.md`, frontmatter name, and `evals/evals.json` when present.
4. Verify provider links point to the canonical directory.
5. Verify user-level Codex links only when the user wants global availability.
6. Report duplicate copies in legacy roots.
7. Apply safe link creation or repair only after confirming target paths.

## Safety Rules

- Never delete a directory with real files unless the user explicitly asks and a backup path is prepared.
- Prefer symlink/junction repair over copying.
- Resolve absolute paths before creating or replacing links.
- If a link target does not exist, report it as broken and propose repair.
- If two same-named skills have different content, classify as conflict and stop.

## Output

```json
{
  "action": "install-sync",
  "created_links": [".claude/skills/skill-name"],
  "repaired_links": [],
  "duplicates_reported": ["~/.agents/skills/skill-name"],
  "conflicts": [],
  "status": "synced"
}
```

