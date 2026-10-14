# 0langas Skill Center

A public collection of custom agent skills for Codex, Claude Code, Kimi Code, and other AI development workflows.

This repo is intended to grow into a broader skill center, not a single-purpose package. Skills here may target one agent client, multiple clients, or general repeatable engineering workflows.

## Layout

- Top-level skill folders, such as `official-ai-devdocs/`, are the canonical source directories.
- User-level discovery is via junctions/symlinks: `~/.agents/skills/<name>` (read natively by Codex, Kimi Code, and VS Code Copilot) and `~/.claude/skills/<name>` (Claude Code). Note: current Codex does NOT scan `~/.codex/skills`.
- There are no repo-local provider folders (`.claude/skills/` and the like): the user-level links already make every skill visible while working inside this repo.
- `registry/skills.json` + `tools/skillctl.py` manage and verify that link layout — see "Skill management system" below.

## Provenance

This repo holds only skills written by its owner. Skills written by other people
are still managed here — the registry tracks them, `sync` links them, `verify`
checks them, `update` refreshes them — but their files always stay outside the
repo, under `~/.agents/skills/` or their own upstream repo.

Every entry in `registry/skills.json` declares an `origin`:

| `origin` | Meaning | Where the files may live |
| --- | --- | --- |
| `mine` | Written by the repo owner | Anywhere, including a top-level folder in this repo (`canonical.type: "repo"`) |
| `vendored` | Written by someone else, deliberately adopted | Outside this repo only |
| `unknown` | Authorship not yet established | Outside this repo only |

The rule is enforced, not just documented: `verify --ci` fails if any entry is
missing an `origin`, carries an unrecognized one, or pairs a non-`mine` origin
with `canonical.type: "repo"`, and if a skill folder in the repo has no
repo-canonical registry entry at all. CI runs that check on every push, so a
third-party skill cannot be committed into this repo by accident.

`register` writes a path canonical, never a repo canonical, so adopting a skill
records where it already lives instead of copying it in. Pass
`--origin mine|vendored` when adopting; entries left `unknown` are listed as an
audit warning until they are classified.

## Skills

| Skill | Purpose | Provider compatibility |
| --- | --- | --- |
| `official-ai-devdocs` | Requires official provider documentation lookup before provider-specific setup, syntax, plugin, connector, MCP, hook, skill, auth, model-routing, or compatibility work for Codex, Claude Code, and Kimi Code. | Codex, Claude Code, Kimi Code |
| `muteman` | Mutes coding-agent chat into a strict emoji-only protocol while preserving normal planning, editing, testing, validation, and safety behavior. | Codex, Claude Code, Kimi Code |
| `official-docs-citation-cache` | Saves compact, dated official-docs evidence notes for Codex, Claude Code, Kimi Code, plugin, skill, MCP, marketplace, config, hook, connector, install, or discovery claims. | Codex, Claude Code, Kimi Code |
| `tri-client-skill-port` | Ports one canonical skill directory into a tri-client-compatible shape with shared frontmatter, provider discovery links, and docs-backed discovery claims. | Codex, Claude Code, Kimi Code |
| `skill-trigger-evalsmith` | Creates realistic should-trigger and should-not-trigger activation evals so skill autoactivation can be tuned instead of guessed. | Codex, Claude Code, Kimi Code |
| `agent-install-sync` | Keeps canonical skill directories, the registry-driven `~/.agents/skills` and `~/.claude/skills` links, and duplicate legacy installs aligned without copying skill content. | Codex, Claude Code, Kimi Code |
| `skill-center-curator` | Orchestrates docs evidence, tri-client porting, trigger evals, install sync, README updates, tests, and publish readiness for this skill collection. | Codex, Claude Code, Kimi Code |
| `skill-doctor` | Diagnoses and repairs the cross-provider skill setup (broken/duplicate/missing skills, junction repair, upstream refreshes) by driving `tools/skillctl.py` against `registry/skills.json`. | Codex, Claude Code, Kimi Code |

## Engineering domain skills

Stack-specific skills for the projects in this workspace (Tauri/React/WebGPU desktop apps, .NET Windows apps, Rust and Python sidecars, SQLite storage, MCP servers). They encode the invariants, gates, and hard-won traps of those repos rather than generic framework advice, so they sit on top of - not instead of - commodity skills such as `winui-design`, `webgpu`, or `frontend-design`.

| Skill | Purpose | Provider compatibility |
| --- | --- | --- |
| `repo-quality-gates` | Finds the repo's canonical gate manifest and runs the correct gate set per stack before anything is called done, with the no-rerun anti-flake protocol and evidence-based reporting. | Codex, Claude Code, Kimi Code |
| `windows-release-ritual` | End-to-end release of a Windows desktop app: version surfaces, changelog as user-facing UI, tag and CI watch, asset and checksum verification, updater and rollback proof, unsigned-binary honesty. | Codex, Claude Code, Kimi Code |
| `determinism-and-golden-baselines` | Protects the preview/export determinism law, shared time chokepoints, preset purity, permanent persisted IDs, and the discipline for re-blessing pixel-hash, golden-trace, and snapshot baselines. | Codex, Claude Code, Kimi Code |
| `persisted-format-migrations` | Numbered migration chains for SQLite, document JSON, settings, and cross-process JSONL contracts: never edit a shipped level, tolerate older producers, keep a fixture per shipped version. | Codex, Claude Code, Kimi Code |
| `destructive-operation-safety` | Single deletion chokepoint, read-only analysis, dry-run to quarantine to permanent ladder, restore records, atomic publication, and the workspace off-limits rules. | Codex, Claude Code, Kimi Code |
| `measured-performance-work` | Measurement before optimization, the seven recurring slow-shapes in this portfolio, realtime frame budgets, before/after numbers in the commit, and a guard against regression. | Codex, Claude Code, Kimi Code |
| `desktop-app-ux-polish` | App-shell UX rules for WinUI 3, WPF, and Tauri/React shells: 200 percent scale, parse-time theme resources, verified contrast, honest progress, long-job controls, platform-safe confirmation. | Codex, Claude Code, Kimi Code |
| `sidecar-process-integration` | Bundled external binaries and child processes: pinned fetches, dev-versus-packaged path resolution, versioned line-delimited JSON protocols, cancellation and resume, licence notices. | Codex, Claude Code, Kimi Code |
| `local-first-scope-guard` | Guards the free, local-first, no-cloud, no-accounts, no-telemetry, minimal-dependency product invariants and the legal and licence surface of the media tools. | Codex, Claude Code, Kimi Code |
| `mcp-server-contracts` | Design and hardening rules for MCP servers: tool-surface shape, workspace confinement, ambiguity refusal, atomic mutation with recovery, the unit-to-hardening test ladder, packaging. | Codex, Claude Code, Kimi Code |

## Skill management system

This repo is the management hub for skills installed across Codex CLI, Claude Code, Kimi Code, and VS Code Copilot.

- `registry/skills.json` is the machine-readable source of truth: provider scan layouts (encoded as data), every known skill, its canonical location, its optional GitHub upstream, and its per-provider install method (`agents`, `agents/skills`, `kimi`, `junction:<path>`, `path:<path>`, `plugin:<id>`, `inherit`, `none`).
- `tools/skillctl.py` (Python 3.11+, stdlib only) reconciles reality to the registry:
  - `python tools/skillctl.py audit` — scan all provider scan dirs and report missing installs, strays, duplicates, broken/wrong-target junctions, and frontmatter validation errors (exit 1 on any problem).
  - `python tools/skillctl.py sync [--plan|--apply] [--only <path-or-name>...]` — plan (default) or apply reconciliation: create/repair junctions, and move anything that must be removed into `_archive/` (never delete). Idempotent. A valid skill that is merely missing from the registry, or a folder holding such skills, is reported as `review` and left alone; `--archive-strays` opts in to removing those. A real directory or file sitting where a junction belongs is archived first, then linked. A registered skill whose canonical is not on this machine is reported as `unfixable` and never linked. Nothing that is, holds, or (through a link) sits inside the home, a scan dir, a container, this repo or a registered canonical is ever archived, however its path is spelled; such a path is reported as `unfixable`. `--only` limits the plan to selected paths/skills for per-item repairs.
  - `python tools/skillctl.py verify [--ci]` — every registry skill resolves at every mapped location with valid frontmatter (exit non-zero on failure). `--ci` checks only what the repo itself guarantees, with no home-dir access, and is what CI runs: registry shape and install methods, that every mapped location is somewhere its provider scans, one owner per location, plain folder names (no trailing dots or spaces, which Windows drops), canonicals that are not and do not hold the home, a scan dir or the repo, provenance, and that every repo skill is present, named in its frontmatter, and registered.
  - `python tools/skillctl.py update [--skill <name>] [--apply]` — refresh skills with a GitHub upstream: skip when the cached commit is unchanged (`registry/.upstream-cache.json`) and the canonical is present, otherwise snapshot the state, archive the old canonical, and replace it with the upstream subpath. A canonical that is, or holds, the home, a scan dir, this repo or another skill's canonical is refused. A canonical missing on this machine is installed fresh, which restores tracked third-party skills on a new PC.
  - `python tools/skillctl.py register [--scan] [<path>...] [--upstream OWNER/REPO[:SUBPATH]] [--origin mine|vendored|unknown] [--apply]` — adopt newly installed skills into the registry: `--scan` lists unregistered skills across provider dirs; path-based registration infers the per-provider install map automatically and always records a path canonical, never a repo one. `--origin` records authorship (see "Provenance").
  - `python tools/skillctl.py discover [--fetch <name>...] [--apply]` — list skills that exist in known upstream GitHub repos but are not registered; `--fetch` downloads one into `~/.agents/skills/` and registers it with its upstream recorded.
  - `python tools/skillctl.py unregister <name>... [--archive-canonical] [--apply]` — remove registry entries (files stay by default; `--archive-canonical` also archives the canonical copy; refused for repo-managed skills and for canonicals outside the provider scan dirs, such as a project repo).
  - `python tools/skillctl.py snapshot [--label <text>]` — write registry + link map + skill listing to `_archive/snapshots/<timestamp>/` (also runs automatically before `update --apply`).
  - `python tools/skillctl.py plugins` — read-only report of installed claude/kimi plugins, the skills they provide, and overlaps with registry skills.
  - `python tools/skillctl.py archive <path> [--reason <text>]` — manually move a skill directory into `_archive/` with a log entry.
  - Mutating subcommands plan by default; `--apply` executes, `--dry-run` is an explicit no-change alias and conflicts with `--apply`. `archive` is the exception: it moves the path immediately.
  - `SKILLCTL_HOME=<dir>` makes `~` mean `<dir>` for every subcommand (and for the e2e harness and trap scripts), so a whole install can be exercised in a throwaway home. The tests use it; nothing then touches the real `~/.agents`, `~/.claude` or `~/.kimi-code`.
  - Repo-skill junctions point at the checkout skillctl runs from. Run `sync --apply` from your main checkout: links made from a worktree go dead when the worktree is removed, and anything archived from a worktree lands in that worktree's gitignored `_archive/`, which `git worktree remove` deletes for good. So `sync --apply`, `update --apply`, `archive` and `unregister --archive-canonical` refuse to run in a linked worktree and name the main checkout instead (a sandbox `SKILLCTL_HOME` is still allowed).
- `_archive/` convention: outdated, misconfigured, duplicated, or stray skills are **archived, never deleted** — moved to `_archive/<YYYYMMDD>/` and logged in `_archive/LOG.md`.
- The one command to get everything back in order: the `skill-doctor` skill (`/skill-doctor` in Claude Code, `skill:skill-doctor` in Kimi Code, or just ask Codex to "get my skills back in order"). Tell it what you want in the same prompt (check, register new, discover, update, clean up): it plans the sequence, asks before every disk change (subset answers honored), then reports per provider.
- CI: `.github/workflows/skill-verify.yml` runs `verify --ci`, the sandboxed skillctl tests, and the e2e harness (`-CI` mode) on every push and PR to `main`.

### Provider matrix (verified 2026-08-04)

| Provider | Scans | Dedupe | Notes |
| --- | --- | --- | --- |
| Codex CLI | `~/.agents/skills` (+ repo `.agents/skills` upward, `/etc/codex/skills`, bundled) | none | `~/.codex/skills` is NOT scanned; follows junctioned skill folders |
| Kimi Code | `~/.kimi-code/skills`, then `~/.agents/skills` | by name, first scope wins | nested sub-skill bundles via `has-sub-skill: true` |
| Claude Code | `~/.claude/skills` (+ project `.claude/skills`, plugins) | by target | does NOT read `.agents`; plugin skills are namespaced `plugin:skill` |
| VS Code Copilot | `~/.copilot/skills`, `~/.claude/skills`, `~/.agents/skills` | none | lowest priority |

## Validation

Run the checks after adding, renaming, moving, or publishing skills, and after changing `tools/skillctl.py`:

```powershell
python tools/skillctl.py verify --ci
python -m unittest discover -s tests -v
powershell -NoProfile -ExecutionPolicy Bypass -File tests\skill-center.e2e.ps1
```

`tests/test_skillctl.py` drives skillctl against throwaway homes (via `SKILLCTL_HOME`): fresh install and idempotency, relinking dead and wrong-target junctions, archiving whatever occupies a junction path, never moving the home, a scan dir, the repo or a canonical however a path is spelled, review-only handling of unregistered skills, `register`/`unregister`, `verify --ci`, and this repo's real registry installed into an empty home.

The E2E harness verifies, for every repo skill in the registry, frontmatter name and description, JSON eval files, trigger-eval shape, and README catalog coverage; the five workflow skills are also held to the full tri-client frontmatter contract and the stricter eval thresholds, and to their intended dependency order. It validates the official docs cache records when `.ai/official-docs-cache/` exists. Without `-CI` it also asserts the registry-driven user-level junctions in `~/.agents/skills` and `~/.claude/skills` (the authoritative layout; `~/.codex/skills` and `~/.kimi-code/skills` are intentionally not used for repo skills), so run it after `sync --apply`.

## Candidate Skills

These are workflow-specific, autoactivating skills that would fit this collection:

- `recall-memory-hygiene`: activate when a durable lesson, repo convention, or recurring failure appears; decide whether it belongs in Recall, README, skill instructions, or repo config, then save only reusable signal.
- `addon-archive-miner`: activate when you mention looking for new addons, skills, plugins, or automation ideas; search the local addon archive for gaps, avoid duplicates of installed skills, and propose only workflow-specific candidates.
- `handoff-cck-bridge`: activate when work crosses Codex, Claude Code, and Kimi Code; write handoffs that include current repo state, command history, docs checked, symlink/install assumptions, and next safe actions.
- `windows-agent-pathguard`: activate when editing installs, symlinks, PATH, PowerShell commands, or Windows-local agent setup; verify absolute paths, avoid fragile shell mixing, and keep user-home versus repo-local installs explicit.
- `skill-release-publisher`: activate when a skill is ready to publish; verify public-safe content, update repo description/README, commit with clean history, push, and prepare a compact release note or install snippet.

## Install Notes

Clone the repository, then let the registry link its skills into the user-level discovery folders:

```powershell
python tools/skillctl.py sync           # plan: what would be linked, repaired, or archived
python tools/skillctl.py sync --apply   # create the junctions
python tools/skillctl.py verify
```

Each repo skill gets a directory junction in `~/.agents/skills/` (Codex, Kimi Code, VS Code Copilot) and `~/.claude/skills/` (Claude Code), so edits in the repo are live everywhere and nothing is copied. Current Codex does not scan `~/.codex/skills`. Registry entries for skills that live outside this repo report `unfixable` (and fail `verify`) until those skills are installed on the machine; `unregister` the ones you do not use.
