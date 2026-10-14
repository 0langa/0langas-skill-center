---
name: autonomous-work-ledger
description: Use when working unattended or across sessions on a repo in this workspace - "keep going", "work through the backlog", "pick the next thing", "continue where we left off", "do a pass on this repo", "what is left here". Drives the ledger files (BACKLOG.md, NEXT_STEPS.md, PROJECT_STATE.md, WORK_STATUS.md, ROADMAP.md), enforces one item at a time with gates and same-change doc updates, defines the stop conditions, and keeps git mutations gated behind an explicit request.
when_to_use: When the user hands over multi-step or open-ended work, resumes an earlier session, asks what to do next in a repo, or wants a self-driving pass; when finishing an item and deciding what to record and what to do next.
type: prompt
whenToUse: When the user hands over multi-step or open-ended work, resumes an earlier session, asks what to do next in a repo, or wants a self-driving pass; when finishing an item and deciding what to record and what to do next.
disableModelInvocation: false
---

# Autonomous Work Ledger

Unattended work is only useful if the next session can tell what happened. The
ledger is the mechanism; the loop below is the discipline.

## 1. Orient before touching anything

Read, in this order, and stop at what exists:

| File | What it holds |
| --- | --- |
| `<project>/AGENTS.md` or `CLAUDE.md` | project rules - these override the workspace root file |
| `GATES.md` | the canonical quality gates |
| `BACKLOG.md` | the canonical work ledger where a project keeps one |
| `NEXT_STEPS.md` | audited current state and planned next steps |
| `PROJECT_STATE.md` | audit findings and deliberate deferrals |
| `WORK_STATUS.md` | the current pass log (often gitignored) |
| `ROADMAP.md` | direction, not a task list |

**Freshness contract.** Every state claim in these files is point-in-time and many
carry a date. Verify against the repo before acting on one. When you find a stale
claim, fix it or report it - never silently obey it, never silently ignore it.

## 2. The loop

1. **Pick one item.** Prefer what the ledger names next; when nothing is named,
   propose the item and its rationale before starting.
2. **Restate scope and the done-condition** in one or two lines. If the item needs
   a product decision, stop and ask instead of guessing.
3. **Implement.** No opportunistic extra changes riding along - note them for the
   ledger instead.
4. **Run the gates** (`repo-quality-gates`). Red gate means not done.
5. **Update docs in the same change.** When behavior, commands, or structure that
   `AGENTS.md`, `README.md`, `CHANGELOG.md`, or `NEXT_STEPS.md` describes changed,
   those files change now, not later.
6. **Update the ledger**: close the item, record what was deferred and why, add any
   follow-up you discovered.
7. **Report**: what changed, the gate evidence, what is left, what is next.

Then take the next item. One item per cycle - a batch of unrelated changes is
impossible to review or revert.

## 3. Stop conditions - ask, do not improvise

- The same gate fails twice for the same cause.
- The item needs a product/scope decision (paid tier, cloud, new dependency,
  breaking format change).
- Anything irreversible: deletion, release, publish, force-push.
- Any git mutation: `commit`, `push`, `reset`, `rebase`, tag, branch delete.
  **Never run these unless the user asked in this session.**
- The change would touch another top-level project you were not asked about.

## 4. Sessions and handoff

When context is about to end or work moves to another agent client, record:
current repo and branch, what was done and verified with the exact commands, what
is in progress and where, known traps hit this session, and the next safe action.
The `agent-handoff` plugin automates this; the content requirement stands either
way.

Prefer writing durable, verified project facts into the repo's own docs. Session
chatter belongs nowhere.

## 5. Reporting rules

- Evidence over adjectives: quote the command and its decisive output line.
- Say what you did **not** do and why - skipped gates, deferred sub-items,
  assumptions made.
- Never report an item complete on the strength of the diff alone.

## Anti-patterns

- Silent scope widening ("while I was in there").
- Leaving the ledger describing a state that no longer exists.
- Marking something done because it compiles.
- Starting a second item before the first one's docs and ledger are updated.
