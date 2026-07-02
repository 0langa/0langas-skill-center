---
provider: codex
topic: skill-discovery
checked_at: 2026-07-02
stability: likely-changing
refresh_after_days: 7
sources:
  - url: https://developers.openai.com/codex/skills
    title: Agent Skills - Codex
claims:
  - Codex documents repo skills under $REPO_ROOT/.agents/skills and user skills under $HOME/.agents/skills.
  - Codex documents symlinked skill folders as supported and followed when scanning skill locations.
  - This repo intentionally keeps clean provider-facing .codex/skills links for organization, but current official docs evidence should be checked before claiming Codex auto-scans that path.
used_by:
  - tri-client-skill-port
  - agent-install-sync
  - skill-center-curator
---

## Notes

Use this cache note to avoid overclaiming `.codex/skills` auto-discovery. The local Codex app may also expose `~/.codex/skills` in this environment, but this note records the official docs checked for repo/user skill discovery.

