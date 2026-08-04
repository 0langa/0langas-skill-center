# 0langas Skill Center — Status & Roadmap
_Portfolio audit: 2026-07-11_

> **Superseded 2026-08-04.** The layout this document describes (per-client symlinks into `.codex/skills` / `.kimi-code/skills`, seven skills, manual validation) has been replaced by the registry-driven management system: `registry/skills.json` + `tools/skillctl.py` + the `skill-doctor` skill (8 repo skills now), with user-level links in `~/.agents/skills` and `~/.claude/skills`. Done since: CI workflow (`.github/workflows/skill-verify.yml`), LICENSE, eval coverage for muteman and official-ai-devdocs. Kept for history; read README.md for current truth.

## What this is
A public collection of seven custom agent skills that work across Codex, Claude Code, and Kimi Code, built around a canonical-source-plus-symlink layout: each skill lives once in a top-level folder (for example `official-ai-devdocs/`, `skill-center-curator/`) and is exposed to each client through symlinks in `.codex/skills/`, `.claude/skills/`, and `.kimi-code/skills/`. The stack is Markdown `SKILL.md` files with shared frontmatter, JSON activation evals under `<skill>/evals/`, a dated official-docs evidence cache under `.ai/official-docs-cache/`, and a 309-line PowerShell end-to-end validation harness at `tests/skill-center.e2e.ps1`.

## Current state
The repo works as designed. All seven skills — official-ai-devdocs, muteman, official-docs-citation-cache, tri-client-skill-port, skill-trigger-evalsmith, agent-install-sync, and skill-center-curator — resolve through their provider symlinks and are discoverable; they load in live Claude Code sessions today. The five workflow skills form a deliberate dependency chain (curator orchestrates docs-cache, port, evalsmith, and install-sync), which the e2e harness explicitly asserts.

The e2e script is unusually thorough for a content repo: it verifies required frontmatter fields, eval JSON shape (at least three prompts per skill), trigger-eval coverage, provider symlink resolution, user-level install links under `~/.codex/skills`, `~/.claude/skills`, and `~/.kimi-code/skills`, README catalog rows, docs-cache records, and the dependency order between the workflow skills.

History is short but coherent: eight commits over 2026-07-02/03, working tree clean and pushed to `origin/main`, no tags. Momentum has paused for about a week.

The gaps are at the edges of the repo's own standards. The strict eval checks in the harness only loop over the five workflow skills (`$WorkflowSkills`), so the two exempt skills fall short of the house rules: `muteman/` contains only a SKILL.md with no `evals/` directory at all, and `official-ai-devdocs/evals/` has `evals.json` but no `trigger-evals.json`. That is a notable irony, since skill-trigger-evalsmith is the collection's own tool for exactly this job.

Beyond eval coverage, the remaining gaps are:

- Validation is manual: there is no `.github/workflows/` directory, so the e2e script never runs automatically.
- The README declares the repo public, but there is no LICENSE file.
- The README's "Candidate Skills" section lists five designed-but-unbuilt skills (recall-memory-hygiene, addon-archive-miner, handoff-cck-bridge, windows-agent-pathguard, skill-release-publisher).
- The three docs-cache notes were last checked 2026-07-02 and are self-labeled "likely-changing", so they are due for a refresh.

## Definition of "finished"
Version 1.0 of the skill center means all of the following hold:

- Every published skill, including muteman and official-ai-devdocs, has both `evals/evals.json` and `evals/trigger-evals.json`.
- `tests/skill-center.e2e.ps1` enforces the full rule set for all seven skills rather than five, so the exemption cannot silently persist.
- The e2e harness runs in CI on every push and pull request.
- The repo carries a LICENSE appropriate for a public collection.
- At least the first one or two backlog candidates are either built to the same standard or explicitly dropped from the README.

## Roadmap

### Phase 1 — Now (next 1-2 weeks)
- Use skill-trigger-evalsmith to author `muteman/evals/evals.json` and `muteman/evals/trigger-evals.json`, and add the missing `official-ai-devdocs/evals/trigger-evals.json`.
- Promote both skills into the strict loop of `tests/skill-center.e2e.ps1` — merge them into `$WorkflowSkills` or add an all-skills eval check alongside the existing `$InstalledSkills` link checks.
- Add a LICENSE file; the README's first line promises a public collection.
- Add a GitHub Actions workflow that runs `tests/skill-center.e2e.ps1` under `pwsh` on push and pull request.

### Phase 2 — Next (2-6 weeks)
- Build the two highest-leverage backlog candidates from the README: `skill-release-publisher`, which closes the publish loop the curator skill references, and `windows-agent-pathguard`, which fits this Windows-first setup. Each needs full frontmatter, evals, symlinks, README rows, and docs-cache evidence per the curator workflow.
- Refresh the three `.ai/official-docs-cache/notes/*-skill-discovery.md` notes (checked 2026-07-02, marked likely-changing) and bump the dates in `index.json`.
- Run PluginEval from the sibling plugin-evaluation-kimi repo against these skills and record baseline scores, mirroring the discipline already applied to the marketplace plugins on 2026-07-06.

### Phase 3 — Later (optional/stretch)
- Build or prune the remaining backlog candidates (recall-memory-hygiene, addon-archive-miner, handoff-cck-bridge), keeping the README table as the single catalog of record.
- Document the canonical-plus-symlink convention for outside users cloning on non-Windows systems, where symlink behavior differs from this repo's Git Bash/Windows setup.
- Tag a v1.0 release once CI is green and eval coverage is complete.

## Effort to "finished"
S (<1 week) for the v1.0 bar itself — two eval files, a test-loop change, a LICENSE, and one CI workflow are small, well-templated tasks in a repo whose own tooling automates most of the authoring; building the Phase 2 backlog skills would add another one to two weeks (M overall if those are included).
