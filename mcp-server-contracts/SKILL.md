---
name: mcp-server-contracts
description: Use when designing, extending, hardening, testing, or packaging an MCP server or its tools - scalpel, context-crafter, Web.de Access, computer-custom, or a new one. Covers tool-surface design, schema and argument contracts, workspace confinement, dry-run and ambiguity refusal, atomic mutation with transaction recovery, error taxonomy, the unit-to-hardening test ladder on Windows and Linux, and release packaging. Triggers - "add an MCP tool", "the tool returned a partial write", "design the tool schema", "MCP smoke test", "publish the server", "the edit corrupted the file", "make this tool safe".
when_to_use: When adding or changing an MCP tool or its arguments, when a server mutates files or external state, when deciding what a tool may do implicitly, or when preparing an MCP server release.
type: prompt
whenToUse: When adding or changing an MCP tool or its arguments, when a server mutates files or external state, when deciding what a tool may do implicitly, or when preparing an MCP server release.
disableModelInvocation: false
---

# MCP Server Contracts

An MCP tool is an API consumed by a model that will call it with plausible-looking
wrong arguments. Design for that caller.

## 1. Tool surface

- Small, single-purpose verbs (`read`, `patch`, `insert`, `move`, `diff`), not one
  overloaded do-everything tool. The tool name is the operation.
- Arguments are explicit and typed with a schema (zod or equivalent) that the
  server validates before doing anything.
- No implicit behavior the caller did not ask for: no auto-creating parents, no
  auto-formatting, no "helpfully" widening a match.
- Every tool documents its preconditions, its failure modes, and whether it
  mutates.
- Read-only and mutating tools are visibly distinguishable by name and docs.

## 2. Safety model

- **Confinement**: every path resolves inside a configured workspace root, after
  symlink resolution, before any operation. Reject, do not clamp.
- **Ambiguity is an error.** Exact-string tools fail when a match is ambiguous
  rather than picking one. Guessing is the failure mode that silently corrupts.
- **Dry run before mutation** where the operation is non-trivial; expose it as a
  first-class argument, not a debug flag.
- Size limits, timeouts, and an explicit streaming path for oversized targets -
  never load an unbounded file into memory.

## 3. Atomicity

- Write to a temp file and rename; never partially overwrite in place.
- Multi-step mutations use an explicit transaction state machine with a documented
  recovery path for a process killed mid-operation.
- Revalidate at commit time (a `move` must re-check the destination it validated
  earlier).
- A tool either fully succeeded or fully did not - report which, never "mostly".

## 4. Errors

A typed taxonomy (not-found, denied, out-of-root, ambiguous, conflict,
too-large, timeout), each with a message that tells the caller what to do
differently. Structured logging to stderr; the protocol stream stays clean.

## 5. Test ladder

1. Unit tests for the logic.
2. Contract tests per tool: happy path, each documented error, boundary sizes.
3. **MCP smoke**: launch the built server over stdio, handshake, list tools, call
   one. Catches the packaging and transport breaks unit tests never see.
4. **Package smoke**: install the built artifact the way a user installs it, then
   run it.
5. **Hardening suites** where the server mutates data: a public-corpus stress run,
   race/interference coverage, and a killed-process fault matrix.

Run the ladder on **Windows and Linux** - path, locking, and rename semantics
differ, and this workspace is Windows-primary while CI is not.

An aggregate `validate` script that chains lint, typecheck, test, build, and both
smokes is what makes this repeatable.

## 6. Packaging and release

- Explicit `files` allowlist, `bin` entry, `engines` floor, ESM/CJS decision
  documented.
- Ship the docs the safety claim rests on (architecture, safety model, tool
  contracts, hardening evidence).
- Release notes state the platforms proven, the unsupported cases, and the
  migration notes.

## 7. Claim only what a test proves

"Atomic", "safe", "crash-recoverable" and "race-free" are claims. Each needs a
suite behind it and a pointer to that suite in the docs. Remove the adjective or
add the test.
