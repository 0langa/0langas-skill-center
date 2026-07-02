---
provider: claude-code
topic: skill-discovery
checked_at: 2026-07-02
stability: likely-changing
refresh_after_days: 7
sources:
  - url: https://code.claude.com/docs/en/skills
    title: Extend Claude with skills
claims:
  - Claude Code documents personal skills under ~/.claude/skills/<skill-name>/SKILL.md.
  - Claude Code documents project skills under .claude/skills/<skill-name>/SKILL.md.
  - Claude Code follows symlinks for personal and project skills and loads the same target once when reachable from multiple locations.
used_by:
  - tri-client-skill-port
  - agent-install-sync
  - skill-center-curator
---

## Notes

Use `.claude/skills` as the clean repo-local Claude Code discovery surface for this skill center.

