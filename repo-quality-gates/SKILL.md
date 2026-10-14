---
name: repo-quality-gates
description: Use before claiming any change is done, green, or ready in this workspace. Finds the repo's canonical gate manifest (GATES.md, AGENTS.md/CLAUDE.md, CI workflow, package scripts), runs the correct gate set for the stack (npm/vitest, cargo, dotnet, uv/pytest), applies the no-rerun anti-flake protocol, and reports evidence instead of assurances. Triggers - "is this done", "run the checks", "make sure it passes", "verify before commit", "ready to release", "tests are flaky", "CI is red but it works locally".
when_to_use: When work is about to be called complete, committed, released, or handed off; when a test suite fails or looks flaky; when CI and local disagree; when you do not know which commands count as this repo's gates.
type: prompt
whenToUse: When work is about to be called complete, committed, released, or handed off; when a test suite fails or looks flaky; when CI and local disagree; when you do not know which commands count as this repo's gates.
disableModelInvocation: false
---

# Repo Quality Gates

One rule: nothing is done until this repo's own gates ran and you can quote the result.

## 1. Find the canonical definition first (do not guess)

Read in this order and stop at the first that exists:

1. `GATES.md` - a release-gate manifest. If present it is the single source of truth.
2. `AGENTS.md` / `CLAUDE.md` in the project root - project rules override the workspace root file.
3. `.github/workflows/ci.yml` - what actually blocks merges.
4. `package.json` scripts / `pyproject.toml` / `Directory.Build.props` / `Cargo.toml`.

**Drift rule.** When two of these disagree, the canonical file wins and the other
is drift: fix the drift in the same change, do not fork a second definition and do
not quietly follow the weaker one. Parallel contradicting gate definitions are how
releases ship off a main branch that was already failing `format:check`.

## 2. Run the gate set for the stack

| Stack | Gates |
| --- | --- |
| Node/TS (vite, vitest) | `npm run typecheck`, `npm run lint`, `npm run format:check`, `npm test`, `npm run build` |
| Node/TS (pnpm repos) | the repo's aggregate script if it has one (e.g. `pnpm validate`), else the same five |
| Rust | `cargo fmt --all -- --check`, `cargo clippy --workspace --all-targets -- -D warnings`, `cargo test --workspace` |
| .NET | `dotnet build <solution> -c Release`, `dotnet test <test project> -c Release`, `dotnet format --verify-no-changes` |
| Python (uv) | `uv run ruff check`, `uv run ruff format --check`, `uv run python -m pytest`, `mypy` where configured |

Stack traps that have cost real time here:

- **Always `--workspace` / `--all` on cargo.** A non-virtual workspace root means
  bare `cargo test` / `clippy` / `fmt` silently covers only the root package and
  skips sidecar members. Green run, never compiled.
- **A .NET solution build does not always refresh the runnable exe.** Where the UI
  targets a specific platform, build that csproj directly
  (`-p:Platform=x64`) and check the exe timestamp before trusting live behavior.
  A stale exe once burned ~40 minutes of phantom-bug hunting.
- **Tauri repos need their sidecars fetched/built before any cargo command works** -
  the build script validates bundled resources at compile time.
- **Multi-language repos have two gate sets** (web + Rust, .NET + Python backend).
  Running one is not running the gates.

## 3. Device and E2E gates

Some gates need this machine's hardware (GPU pixel matrices, loopback audio
capture, built-app smokes, live-network E2E). They are mandatory per touched area
and before a release that touched that area. If one cannot run, say so explicitly
in the report - never let an unrun gate read as a passed gate.

## 4. Anti-flake protocol

A failing suite is a real failure until proven otherwise.

Not answers: rerunning, lowering worker count, shrinking the fixture, adding a
retry, marking it skip. Those hide the signal.

Answers: find the root cause. The classic one in this workspace is a default
per-test timeout (5 s in vitest) firing on suites that legitimately do seconds of
real work. Fix it with an explicit budget on the **describe**, not on individual
`it`s - the per-test form leaves every unmeasured test on the default and keeps
one suite red long after its neighbours were fixed. Say in the file why the budget
exists.

## 5. Report evidence, not adjectives

For each gate: the exact command, and the decisive line of output (pass count,
error count, or the first error verbatim). "Should pass", "looks fine", and
"tests are green" without a quoted result are not acceptable outputs.

If any gate is red or unrun, the change is not done - say that plainly and say
which one.

## Checklist

- [ ] Canonical gate definition located and quoted
- [ ] Drift between manifest / docs / CI resolved or reported
- [ ] Every stack in the repo gated, not just the one you edited
- [ ] Device/E2E gates run where mandatory, or explicitly listed as not run
- [ ] No rerun-to-green, no worker reduction, no fixture shrinking
- [ ] Evidence quoted per gate
