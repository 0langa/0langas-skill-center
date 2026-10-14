---
name: skill-doctor
description: Cross-provider skill health and repair across Codex, Claude Code, Kimi Code, and VS Code Copilot. Use for anything about SKILL folders specifically — findings-first health checks of the skill setup (fully report-only when asked), broken/duplicated/misplaced skills, broken or wrong-target junctions/symlinks, skills visible to one client but not another, registering newly installed skills into the catalog, discovering new skills in tracked upstream repos, unregistering/retiring skills, updating skills from GitHub upstreams, and reconciling which providers can see which skills. Triggers: "my skills are a mess", "skill setup feels off", "a skill stopped loading", "check for skill updates", "register all new skills", "am I missing any skills", "get my skills back in order", "health check of my skill setup". Plans the requested sequence, asks before every disk change (partial/subset answers honored), supports dry-run check-only mode. Boundary: for a broad audit of ALL customization types (plugins, MCP servers, hooks, marketplaces, configs), customization-audit owns that; skill-doctor owns the skill layer end-to-end, including the repairs.
whenToUse: When the user reports skill loading/duplication/sync problems across AI coding agents, wants a skills-focused health check across providers (report-only or with repair), asks to register/discover/update/unregister/repair skills, or wants the cross-provider skill setup reconciled. If the request is a broad audit of ALL customization types (plugins, MCP servers, marketplaces, configs), route to customization-audit instead; skill-doctor handles the skill layer.
---

# Skill Doctor — get every agent's skills back in order

The ONE runbook for diagnosing and repairing the cross-provider skill setup.
It drives `tools/skillctl.py` in the skill-center repo against
`registry/skills.json` (the machine-readable source of truth).

Repo root resolution (agents invoke from anywhere): the repo is the parent
directory of this SKILL.md — when invoked through a junction/symlink, resolve
the link target first. On Kimi Code `${KIMI_SKILL_DIR}` points at this skill's
directory; other clients expose an equivalent variable or the invocation path.
All commands below use `<repo>` for that root.
If that root is a linked git worktree rather than the main checkout,
skillctl refuses `--apply` and `archive` there (junctions would point at
the worktree, and its `_archive/` is deleted with it) and prints the main
checkout's path: use that as `<repo>` instead.

## Provider layout facts (verified 2026-08-04)

| Provider | Scans | Dedupe | Notes |
| --- | --- | --- | --- |
| Codex CLI | `~/.agents/skills` (+ repo `.agents/skills` upward, `/etc/codex/skills`, bundled) | none | `~/.codex/skills` is NOT scanned; follows symlinked/junctioned skill folders. **Provider-managed system scope**: `~/.codex/skills/.system` holds Codex's bundled skills (e.g. its own `skill-creator`) and is repopulated on every Codex update — never flag, archive, or "fix" it, and treat name overlaps with personal skills (e.g. Skill Creator appearing twice: Personal + System) as benign and informational only |
| Kimi Code | `~/.kimi-code/skills`, then `~/.agents/skills` | by name, first (more specific) scope wins | nested sub-skill bundles via `has-sub-skill: true` |
| Claude Code | `~/.claude/skills` (+ project `.claude/skills`, plugins) | by target; same target twice loads once | does NOT read `.agents`; plugin skills are namespaced `plugin:skill` |
| VS Code Copilot | `~/.copilot/skills`, `~/.claude/skills`, `~/.agents/skills` | none | least critical |

Install methods recorded in the registry: `agents` / `kimi`
(must exist at that scan location), `junction:<path>` (junction at path ->
canonical), `path:<abs>` (canonical lives directly at that provider-visible
location), `plugin:<id>` (provided by an installed plugin, verify-only),
`inherit` (visible through another provider's location), `none`
(deliberately absent).

## Runbook

### Step 0 — Parse the request into a sequence

Break the user's WHOLE prompt into an ordered list of operations — composite
requests are normal ("register all newly installed skills, after that check
for updates and act on it"). Operation types:

- `check` — health audit / dry-run inspection (never mutates)
- `discover` — find skills in known upstream repos that aren't installed yet
- `register` — adopt newly found skills into the registry
- `repair` — fix layout/junctions to match the registry (`sync`)
- `update` — refresh skills from their GitHub upstreams
- `archive` — evict strays/duplicates into `_archive/`
- `unregister` — retire skills from the registry (optionally archiving them)

State the planned sequence back to the user as one short numbered list, then
execute it in order. Each mutating step follows the confirmation protocol
below — even when the prompt says "act on your findings", you still show the
items and ask before executing. Only skip asking if the user explicitly said
"without asking" / "don't ask".

### Confirmation protocol (every mutating step)

- **Read-only commands never need confirmation.** Just run them and show the
  results: `audit`, `register --scan`, `sync --plan`, `update --dry-run`,
  `discover` (list mode), `plugins`, `snapshot`, `verify`.
- **Before any disk-changing command** (`register --apply`, `sync --apply`,
  `update --apply`, `archive`), present the concrete item list — skill names,
  paths, and what will happen to each — then ask via the client's
  ask-user capability (AskUserQuestion or equivalent), offering options like
  "Apply all (Recommended)" and "Apply none". The user may pick an option OR
  type a custom reply.
- **Custom replies rule.** If the user answers with a subset ("yes, but only
  the asdf and lkjh skills", "archive a, b, c but leave d and e alone"),
  execute EXACTLY that subset and nothing more. Partial execution is always
  per-item:
  - register → `register <only the confirmed paths> --apply`
  - discover-fetch → `discover --fetch <name> --apply` once per confirmed skill
  - update → `update --skill <name> --apply` once per confirmed skill
  - archive → `archive <path>` once per confirmed item
  - unregister → `unregister <name> --apply` once per confirmed skill
    (add `--archive-canonical` only if the user asked for the files to go too)
  - sync → `sync --apply` executes the WHOLE plan, archive actions included,
    so use it only when every action was approved. Otherwise apply the
    approved repairs with `sync --only <path-or-name> --apply` (repeatable)
    and the approved evictions piecemeal with `archive <path>` so the user
    can cherry-pick
- **Whatever the answer — yes, no, or partial — CONTINUE the sequence.**
  A "no" skips only that one step, never the rest of the request.

### Step 1 — Health check (no asking)

```
python <repo>/tools/skillctl.py audit
python <repo>/tools/skillctl.py plugins   # read-only plugin surface report
```

`audit` reports missing installs, strays, duplicates, broken/wrong-target
junctions, frontmatter validation errors, per-provider counts. `plugins`
lists installed claude/kimi plugins, the skills they provide, and overlaps
with registry skills — informational; never alter plugins without asking
(see safety rules).

### Step 1.5 — Snapshot before risky sequences (no asking)

```
python <repo>/tools/skillctl.py snapshot --label <context>
```

Writes registry + link map + skill listing to `_archive/snapshots/`. Always
snapshot before a big sync/update sequence. (`update --apply` already
snapshots automatically with label `pre-update` — no need to double up.)

### Step 2 — Discover new upstream skills (if requested, or to answer "am I missing anything?")

```
python <repo>/tools/skillctl.py discover
```

Read-only: lists skills that exist in known GitHub upstream repos but are not
in your registry. Present the list, ask which to install (all / none /
subset), then per confirmed skill:

```
python <repo>/tools/skillctl.py discover --fetch <name> --apply
```

Fetch downloads the skill into `~/.agents/skills/` AND registers it with its
upstream recorded, so `update` tracks it from then on.

### Step 2 — Register new skills (if requested, or audit shows strays the user wants adopted)

```
python <repo>/tools/skillctl.py register --scan
```

Lists every unregistered skill found in any provider scan dir (read-only).
Present the list, ask which to register (all / none / custom subset), then
for the confirmed subset:

```
python <repo>/tools/skillctl.py register <path1> <path2> --apply
```

Add `--upstream OWNER/REPO[:SUBPATH]` when the skill comes from a public repo
(so `update` can track it later). Registration infers the per-provider install
map from where the skill lives; canonical path, frontmatter name, and `dir`
are recorded automatically.

### Step 3 — Repair layout (sync)

```
python <repo>/tools/skillctl.py sync --plan
```

Show the plan. Split it mentally into (a) junction create/repair actions —
nothing is moved out, except that a real directory or file sitting where a
junction belongs is archived first ("real directory occupies junction
path") — and (b) archive actions — evictions the user may want to
cherry-pick. `review` and `unfixable` lines change nothing: they need the
user (register, restore, or unregister). Ask, then apply accordingly:
`sync --apply` executes the whole plan, archives included, so use it only
when everything was approved; otherwise `sync --only <path-or-name> --apply`
for the approved repairs and `archive <path>` per approved eviction. Sync is
idempotent: a second `--plan` must print no junction, relink or archive
actions. (`sync --dry-run` is an explicit alias for plan mode and errors
when combined with `--apply`.)

### Step 4 — Update from upstream (if requested or drift suspected)

```
python <repo>/tools/skillctl.py update --dry-run
```

No asking for this check — just show the "would update" list. Then ask
(all / none / subset), then apply:

```
python <repo>/tools/skillctl.py update --apply                 # all
python <repo>/tools/skillctl.py update --skill <name> --apply  # per skill (partial)
```

Each update archives the current canonical into `_archive/` before replacing
and snapshots the whole state first (label `pre-update`). A tracked skill
whose canonical is missing on this machine (plan says "not on this
machine") is installed fresh from upstream - the way to restore those on a
new PC.

### Step 4.5 — Unregister retired skills (if requested)

```
python <repo>/tools/skillctl.py unregister <name> --apply
```

Removes the registry entry only — files stay in place by default, so the
skill keeps working where it is installed but the doctor no longer tracks or
repairs it. Add `--archive-canonical` (only on explicit user request) to also
move the canonical copy into `_archive/`. Repo-canonical management skills
(the skill-center's own) are refused for safety, and so is a canonical
outside the provider scan dirs (a project repo such as usage-pulse). Ask
per skill; subset answers honored.

### Step 5 — Verify + report

```
python <repo>/tools/skillctl.py verify
```

Must exit 0. Then report in this fixed shape (prefix with
`DRY RUN — nothing was changed` when the whole invocation was check-only):

```
## Skill Doctor report
- codex : ok=<n> fixed=<n> archived=<n> registered=<n> attention=<n>
- kimi  : ok=<n> fixed=<n> archived=<n> registered=<n> attention=<n>
- claude: ok=<n> fixed=<n> archived=<n> registered=<n> attention=<n>
- vscode: ok=<n> fixed=<n> archived=<n> registered=<n> attention=<n>
- updates: <skill@old->new, "would update: ..." in dry-run mode, or "none">
- verify: PASS|FAIL
- notes: <anything needing user judgment>
```

### Dry-run / check-only mode

Trigger words: `dry run`, `dryrun`, `dry-run`, `check for updates`,
`check only`, `just check`, `what would change`, `what would be updated`,
`show me`, `report only`, `don't change anything`. In this mode run ONLY the
read-only commands (`audit`, `register --scan`, `sync --plan`,
`update --dry-run`, `verify`), then STOP with the report. NEVER pass
`--apply`, even if drift is found, and do not ask apply-questions — instead
tell the user to re-invoke with "apply"/"fix" to execute.

## Safety rules (non-negotiable)

- **Archive, never delete.** Anything removed from a scan dir goes to
  `<repo>/_archive/<YYYYMMDD>/` and is logged in `_archive/LOG.md`.
- **Never touch** `~/.claude/plugins`, `~/.kimi-code/plugins`, `~/.codex`,
  home-dir config files, provider-managed system scopes (e.g. Codex's
  `~/.codex/skills/.system`, repopulated on every client update), or anything
  outside provider scan dirs and the repo `_archive/`.
- **Ask the user before altering installed plugins** (e.g. `caveman@caveman`);
  the tool treats plugin installs as verify-only.
- Junctions are created with `cmd /c mklink /J` only — never PowerShell.
- **No mutation without confirmation.** The confirmation protocol in the
  runbook is binding: read-only commands run freely, every `--apply` /
  `archive` call is preceded by an ask, and subset/custom answers are
  executed exactly as given — never rounded up to "all".
- Deterministic: identical inputs produce identical plans; if a plan looks
  surprising, stop and show it to the user instead of applying.
