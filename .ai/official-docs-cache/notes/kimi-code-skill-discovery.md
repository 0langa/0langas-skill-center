---
provider: kimi-code
topic: skill-discovery
checked_at: 2026-07-02
stability: likely-changing
refresh_after_days: 7
sources:
  - url: https://www.kimi.com/code/docs/en/kimi-code-cli/customization/skills.html
    title: Agent Skills - Kimi Code Docs
claims:
  - Kimi Code documents directory-form skills with SKILL.md as the recommended structure.
  - Kimi Code requires name and description in directory-form SKILL.md frontmatter.
  - Kimi Code documents project skills under .kimi-code/skills and .agents/skills, and user skills under ~/.kimi-code/skills and ~/.agents/skills.
  - Kimi Code can automatically invoke skills based on description and whenToUse when disableModelInvocation is not true and type is not flow.
used_by:
  - tri-client-skill-port
  - skill-trigger-evalsmith
  - agent-install-sync
  - skill-center-curator
---

## Notes

Use `.kimi-code/skills` as the clean repo-local Kimi Code discovery surface for this skill center.

