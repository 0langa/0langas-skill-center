---
name: measured-performance-work
description: Use when something is slow, when optimizing, or when reviewing a change that claims to be faster - scanners, database queries, render loops, audio pipelines, download queues, or UI responsiveness. Requires a measurement before the change, a number after it, and a guard so the win cannot silently regress. Carries the specific wins this portfolio keeps rediscovering. Triggers - "this is slow", "optimize", "make it faster", "UI freezes", "scan takes forever", "reduce memory", "perf regression", "add a benchmark".
when_to_use: When diagnosing or improving performance, when a UI stalls or a job takes too long, when reviewing a perf commit, or when deciding whether an optimization is worth its complexity.
type: prompt
whenToUse: When diagnosing or improving performance, when a UI stalls or a job takes too long, when reviewing a perf commit, or when deciding whether an optimization is worth its complexity.
disableModelInvocation: false
---

# Measured Performance Work

No optimization without a measurement. A change that is "obviously faster" and
unmeasured is a guess with extra risk.

## 1. Measure first

| Stack | Tool |
| --- | --- |
| .NET | BenchmarkDotNet for hot paths, `dotnet-counters`/ETW for a running app, Stopwatch around the phase under suspicion |
| Rust | `cargo bench` / criterion, `--release` always, per-thread counters for walkers |
| Node/TS | vitest bench, `performance.now()` around the phase, Chrome/WebView profiler |
| GPU | timestamp queries and frame time, not wall-clock around the submit |
| SQLite | `EXPLAIN QUERY PLAN` before assuming an index is used |

Record the baseline number and the exact command that produced it. If you cannot
measure it, you cannot claim it.

## 2. Find the actual shape of the problem

Ask which of these it is before touching code:

- **Per-item syscall count** - the same file stat'ed three times instead of once.
- **Quadratic work** - folder totals or dedupe partners recomputed per item
  instead of resolved once per group, or an unindexed join fanning out.
- **Wrong thread** - repository queries, hashing, or badge computation running on
  the UI/dispatcher thread. The fix is moving the work, not making it faster.
- **Unbounded growth** - a history/health table that never prunes; a cache with no
  ceiling.
- **Lost parallelism** - metadata captured on the coordinator instead of on the
  walker threads, so `--threads` does nothing.
- **Repeated normalization** - path normalization or option resolution redone in
  the hot loop instead of at the boundary.
- **Per-item round trips** - one delete/insert per file where a batch path exists.

These are the seven that keep recurring in this portfolio. Check them before
inventing a novel optimization.

## 3. Realtime loops have a budget, not a target

For render and audio paths: the budget is per frame or per buffer. Rules that
matter more than micro-speed:

- No allocation churn inside the loop.
- No synchronous GPU readback in the frame path.
- No wall-clock dependence (see `determinism-and-golden-baselines`) - a faster
  loop that breaks preview/export parity is a regression, not a win.
- Measure the worst frame, not the average; a p99 stall is what the user sees.

## 4. Prove it

The commit body carries: the measurement command, before and after numbers with
units, and the machine caveat. "perf: cut per-file syscalls from three to one" is
only a good subject line when the body has the numbers under it.

State honestly when a change is a structural cleanup with no measured win - that
is fine, it just is not a perf commit.

## 5. Guard it

Add the thing that catches the regression: a benchmark in CI, an assertion that
bounds the query count or the allocation, or a test that fails if the work returns
to the UI thread. An unguarded optimization comes back within a few releases.

## 6. Never trade these for speed

Correctness, determinism, deletion safety, and migration compatibility. If an
optimization needs one of them relaxed, it is the wrong optimization - say so and
propose the alternative.
