---
name: sidecar-process-integration
description: Use when an app drives a bundled or external executable - ffmpeg, whisper.cpp, onnxruntime, a Rust scanner, a uv-managed Python backend, spotDL/yt-dlp, or any child process. Covers fetching and pinning binaries, dev-versus-packaged path resolution, line-delimited JSON protocols, versioned contracts, cancellation and orphan cleanup, resumable journals, and third-party licence notices. Triggers - "call ffmpeg", "the sidecar does not start", "backend not found", "bundle the binary", "parse the tool output", "cancel the running job", "yt-dlp failed", "LGPL notice".
when_to_use: When adding or debugging an external-binary dependency, its packaging, its stdout protocol, its lifecycle, or its licensing obligations.
type: prompt
whenToUse: When adding or debugging an external-binary dependency, its packaging, its stdout protocol, its lifecycle, or its licensing obligations.
disableModelInvocation: false
---

# Sidecar Process Integration

These apps are thin shells over heavy external binaries. Most "app bugs" in that
design are actually contract, path, or lifecycle bugs at the sidecar boundary.

## 1. Acquire, pin, verify

- Sidecar binaries are **fetched by a script, not committed** (they are large and
  licensed separately). One script per sidecar, documented as one-time setup in
  the README/CLAUDE.md.
- Pin an exact version and verify the download (hash or signature). An unpinned
  sidecar makes every bug unreproducible.
- In Tauri, the build script validates bundled resources at **compile time** - no
  cargo command works until every sidecar exists. When cargo fails on a fresh
  clone, run the fetch/build scripts before debugging anything else.
- Never vendor a modified copy of an LGPL binary.

## 2. Path resolution: dev, packaged, and beside-the-exe

Three cases, all of which must work:

- **Dev**: launched through the toolchain (`uv run`, `cargo run`, a workspace path).
- **Packaged**: resolved from the app's bundled resource directory.
- **Beside the exe**: an optional accelerator the user copies next to the binary
  (e.g. a turbo scanner). Its absence is a feature downgrade, not a crash.

Provide an environment override for local testing (the pattern used here is
`<APP>_BACKEND_PATH`). A missing sidecar produces a specific, actionable message
naming what is missing and how to get it - never a stack trace.

## 3. Protocol: line-delimited JSON, versioned

- One JSON object per line on stdout; logs go to stderr. Never parse human-facing
  progress text.
- Version the contract explicitly and let the newer side tolerate the older
  producer (nullable new fields plus a per-item fallback).
- Detect a producer too old to be trusted and refuse it with the required version
  in the message.
- See `persisted-format-migrations` - a sidecar contract is a persisted format
  that happens to travel over a pipe.

## 4. Lifecycle

- Bounded concurrency, with the slot released the moment a job stops using the
  resource.
- Cancellation propagates: kill the child, clean its temp files, leave no orphan.
- Timeouts on both startup and per-chunk progress - a silent child is a hung job.
- Long transfers keep a **resumable journal** so an interrupted run recovers
  instead of restarting.
- On app start, reap state from a previous crashed run before accepting new work.
- Exit codes and stderr are captured and surfaced; a nonzero exit is never
  swallowed.

## 5. Output validation

Never publish the sidecar's output without checking it: expected size, container,
stream count, duration. Then publish atomically with collision-safe naming (see
`destructive-operation-safety`).

## 6. Licensing and notices

- Bundled third-party binaries get an entry in `THIRD_PARTY_NOTICES.md` with the
  licence and the exact version.
- LGPL binaries ship unmodified, with the licence text and a statement of how they
  are invoked.
- Tools whose terms restrict automated use are the user's responsibility - state
  that in the README, do not paper over it (see `local-first-scope-guard`).
