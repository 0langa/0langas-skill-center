---
name: destructive-operation-safety
description: Use before writing, reviewing, or running code that deletes, moves, overwrites, quarantines, or cleans up files, directories, database rows, or caches - and before running such an operation on this machine. Enforces single deletion chokepoints, read-only analysis, the dry-run to quarantine to permanent ladder, restore records, atomic publication, synthetic-fixture testing, and the workspace off-limits rules. Triggers - "clean up disk space", "delete duplicates", "cleanup rule", "purge cache", "remove build output", "quarantine", "empty the queue folder", "overwrite the output file".
when_to_use: When code or a command can remove or replace user data; when adding a cleanup/dedupe rule; when publishing a downloaded or exported file into its final location; when freeing disk space on this machine.
type: prompt
whenToUse: When code or a command can remove or replace user data; when adding a cleanup/dedupe rule; when publishing a downloaded or exported file into its final location; when freeing disk space on this machine.
disableModelInvocation: false
---

# Destructive Operation Safety

Deletion is the one class of bug with no fix after the fact. Design for the case
where the logic is wrong.

## 1. One chokepoint

All deletion flows through a single abstraction (in StorageMaster: `IFileDeleter`).
No direct `File.Delete`, `fs.rm`, `Remove-Item`, or `rm -rf` in feature code. One
chokepoint is what makes policy, logging, quarantine, and tests possible at all.

## 2. Analysis stays read-only

Scan, analyze, preview, and rule-evaluation paths must not mutate anything. A
cleanup rule's analyze step returns candidates; it does not act on them. If an
analyze path needs to write (a cache, a journal), that write goes somewhere the
user never loses data from.

## 3. The ladder - default to the least destructive rung

1. **Dry run**: report what would happen, with counts and total bytes, and change
   nothing. This is the default for any new or changed rule.
2. **Quarantine or Recycle Bin**: reversible. Every quarantine move **must** write
   a restore record - the move and the record are one operation, not two steps
   that can half-fail.
3. **Permanent deletion**: gated by an explicit policy check, never the default,
   never inferred from "the user probably wants space back".

Escalate a rung only when the user asked for it in that session.

## 4. Publishing a new file is also destructive

Downloads, exports and generated artifacts overwrite things.

- Write to a temp path, verify, then atomically rename into place.
- Collision-safe naming: never silently replace an existing user file.
- Validate the output before publishing it (size, container, expected duration) -
  a truncated file that replaced a good one is a deletion.
- Clean up temp files on cancel and on crash-restart.

## 5. Path handling

- Normalize once, at the boundary; do not re-normalize per item in hot loops.
- Handle long paths, hidden/system attributes, read-only flags, and files in use.
- Do not follow junctions/symlinks into places the user did not select; guard
  against loops.
- Cross-device moves are copy+delete - the delete only runs after the copy
  verifies.

## 6. Testing and live verification

- Filesystem tests use synthetic fixtures and temp directories only.
- For live-app testing use the repo's demo/sample pack - never real user data.
- Verify the running binary is the one you built (check its timestamp) before
  concluding anything about live behavior.

## 7. Rules for this machine

- `<drive>:\user-files` is off-limits unless the user names a specific path in it.
- A directory containing a file named `KEEP` is never deleted or overwritten.
- Source files never leave the repo working tree; only regenerable output goes to
  external devstorage.
- Delete only what you created this session; aged cleanup belongs to the scheduled
  janitor.
- Never `git reset --hard`, `git clean`, branch deletion, or history rewriting
  without an explicit request.

## 8. Before executing anything irreversible

State: the exact target set, the item count, the total bytes, whether it is
recoverable, and how to undo it. Then wait for confirmation. "Reclaim some space"
is not authorization to delete a specific directory.
