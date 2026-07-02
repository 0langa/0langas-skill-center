---
name: skill-center-curator
description: Use whenever working in 0langas-skill-center or another personal skill collection to add, rename, move, publish, document, test, or install skills. This skill orchestrates official-docs-citation-cache, tri-client-skill-port, skill-trigger-evalsmith, and agent-install-sync so every skill is canonical, documented, tri-client compatible, linked correctly, covered by activation evals, and safe to publish.
when_to_use: When adding, renaming, moving, publishing, testing, organizing, documenting, or installing skills in 0langas-skill-center; when README tables, provider links, evals, docs evidence, or local installs need to stay in sync; when the user says this repo is becoming a skill center.
type: prompt
whenToUse: When adding, renaming, moving, publishing, testing, organizing, documenting, or installing skills in 0langas-skill-center; when README tables, provider links, evals, docs evidence, or local installs need to stay in sync; when the user says this repo is becoming a skill center.
disableModelInvocation: false
---

# Skill Center Curator

Use this skill as the operating manual for `0langas-skill-center`. It keeps the collection useful as it grows instead of letting it become a pile of disconnected skills.

## Owned Outcome

After a skill-center task, the repo should have:

- one canonical top-level directory per skill
- tri-client frontmatter for Codex, Claude Code, and Kimi Code where appropriate
- provider discovery links under `.codex/skills`, `.claude/skills`, and `.kimi-code/skills`
- trigger evals beside each skill
- official docs evidence cached when provider behavior is claimed
- README skill table updated
- local install state synced when requested
- tests passing

## Orchestration Order

Use the other skills in this order:

1. `official-docs-citation-cache` for provider docs evidence.
2. `tri-client-skill-port` for metadata and canonical layout.
3. `skill-trigger-evalsmith` for activation evals.
4. `agent-install-sync` for provider and user-level links.
5. Curator final pass for README, tests, commit readiness, and release notes.

## Curator Workflow

1. Inspect git status and existing skill directories.
2. Identify the requested skill operation: add, rename, import, update, publish, or install.
3. Run the orchestration order above.
4. Update `README.md` skills table and remove completed candidates from the candidate list.
5. Run deterministic checks:
   - frontmatter has required fields
   - provider links exist and resolve
   - eval JSON parses
   - README table contains the skill
   - official docs cache exists when provider claims changed
6. Summarize only material changes and verification results.

## Repository Policy

- Keep skills ASCII unless the source skill already uses Unicode intentionally.
- Do not duplicate skill content across provider folders.
- Do not delete user-level installs without explicit confirmation.
- Keep candidate ideas separate from implemented skills.
- Prefer high-value workflow-specific skills over generic commodity skills.
- If a skill would be better as a plugin, say so and stop before overloading the skill surface.

## Output

```json
{
  "action": "skill-center-curation",
  "skills_changed": ["skill-name"],
  "docs_cached": true,
  "tri_client_ported": true,
  "evals_created": true,
  "links_synced": true,
  "tests": "passed",
  "ready_to_commit": true
}
```

