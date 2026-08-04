# _archive — archived skills (never deleted)

This folder is the only destination for removals performed by
`tools/skillctl.py` (or by hand via `python tools/skillctl.py archive <path>`).

## Convention

- **Archive, never delete.** Outdated, misconfigured, duplicated, or stray
  skills are moved here — nothing in the skill-management system hard-deletes
  skill content.
- Layout: `_archive/<YYYYMMDD>/<provider>-<name>/` for sync-time removals
  (strays, duplicates, real directories occupying junction paths) and
  `_archive/<YYYYMMDD>/upstream-<name>/` for canonical copies replaced by an
  upstream refresh.
- Every move appends one line to `_archive/LOG.md`: timestamp, source path,
  destination, reason.
- To restore something, move it back to its original location and re-run
  `python tools/skillctl.py sync --plan` to confirm the plan is clean.
- Entries here are intentionally NOT in `registry/skills.json`; the registry
  only covers live installs.
