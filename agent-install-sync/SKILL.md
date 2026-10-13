---
name: agent-install-sync
description: Use after adding, renaming, importing, moving, or deleting a skill in 0langas-skill-center or any local agent customization repo. This skill reconciles canonical skill directories, provider discovery links, user-level ~/.agents and ~/.claude skill links, stale duplicate copies, and local install state across Codex, Claude Code, and Kimi Code without duplicating content. Use proactively when skill visibility, symlinks, or local installs may drift.
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

In 0langas-skill-center the layout is data: `registry/skills.json` records each skill's canonical directory and per-provider install method, and `tools/skillctl.py` reconciles the machine to it. Expected user-level links for a repo skill:

```text
~/.agents/skills/<skill-name>   (Codex, Kimi Code, VS Code Copilot)
~/.claude/skills/<skill-name>   (Claude Code)
```

Current Codex does not scan `~/.codex/skills` (only its own `.system` scope lives there), and the repo keeps no repo-local `.codex/`, `.claude/` or `.kimi-code/` skill folders. Copies under legacy roots are reported as duplicates, never deleted automatically.

## Sync Workflow

1. Inventory canonical top-level skill directories.
2. Ignore infrastructure directories: `.git`, `.codex`, `.claude`, `.kimi-code`, `scripts`, `tests`, `tools`, `registry`, `_archive`, `.ai`, `.handoff`.
3. For each canonical skill, verify `SKILL.md`, frontmatter name, and `evals/evals.json` when present.
4. Make sure every skill has a registry entry: `python tools/skillctl.py verify --ci` reports unregistered skill folders.
5. Inspect the links with `python tools/skillctl.py sync --plan` (and `audit`): missing, dead, or wrong-target links, strays, and duplicates.
6. Report duplicate copies in legacy roots.
7. Apply link creation or repair with `sync --apply` (or `sync --only <skill-name> --apply`) only after confirming the plan, then run `python tools/skillctl.py verify`.

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
  "created_links": ["~/.claude/skills/skill-name"],
  "repaired_links": [],
  "duplicates_reported": ["~/.codex/skills/skill-name"],
  "conflicts": [],
  "status": "synced"
}
```

