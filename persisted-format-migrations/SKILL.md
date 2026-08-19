---
name: persisted-format-migrations
description: Use before changing anything that outlives the process - SQLite schemas, project/document JSON, themes and presets, settings, queue and job state, localStorage, and JSONL/IPC contracts between a host and a sidecar. Enforces numbered migration chains, never editing a shipped level, forward/backward tolerance between binaries, atomic partial settings mutation, and per-version round-trip fixtures. Triggers - "add a column", "change the project format", "new schema version", "old projects fail to open", "settings got overwritten", "the scanner output changed shape".
when_to_use: When adding, renaming, or removing a field in any persisted or cross-process format; when a stored file or database from an older version fails to load; when two processes exchange versioned records; when settings writes race.
type: prompt
whenToUse: When adding, renaming, or removing a field in any persisted or cross-process format; when a stored file or database from an older version fails to load; when two processes exchange versioned records; when settings writes race.
disableModelInvocation: false
---

# Persisted Format Migrations

Anything a previous release wrote, a future release must still read. That is the
whole rule; everything below is how to keep it true.

## 1. Inventory the persisted surfaces first

Before editing, list which of these the change touches:

- SQLite schema (tables, indexes, views)
- Project/document files and their `schemaVersion`
- Sibling versioned JSON formats: themes, looks, user presets, builder stacks,
  shader files, exported manifests
- Settings store
- Queue / job / session state that survives a restart
- `localStorage` and other client-side caches
- JSONL or JSON-over-stdout contracts with sidecar processes
- Installer-written registry keys and on-disk layout

A change is rarely confined to one of them. Renaming an ID in the document model
usually also invalidates themes, cached thumbnails, and any queue entry holding
that ID.

## 2. SQLite: numbered levels, never edited

- New level = new `V<N>Statements` block plus a chain entry in the migrate path.
- Each level is **one atomic transaction** that ends by stamping its version.
- **Never edit a level that shipped.** Machines already at that version will never
  re-run it, so the edit only affects fresh installs and creates two different
  schemas with the same version number. Add `V<N+1>` instead.
- Additive beats destructive: add a column, backfill, then stop reading the old
  one - drop it a release later if at all.
- Verify against a real database, not only tests:
  `sqlite3 <db> "SELECT MAX(Version) FROM SchemaVersion;"`.
- Add the index in the same level as the query that needs it.

## 3. Document JSON: schemaVersion plus numbered migrations

- Every persisted document carries `schemaVersion`.
- Migrations are numbered pure functions, applied in order, each covering exactly
  one version step.
- Sibling formats (themes, presets, shader files) share the approach; do not
  invent a second migration style per format.
- Never change the persisted shape without a migration **and** a test.

## 4. Cross-process contracts: version and tolerate

Host and sidecar upgrade at different times (a user copies a new exe beside an old
one; a dev build meets a released backend).

- Version the payload explicitly.
- The newer consumer tolerates the older producer: new fields nullable, with a
  per-item fallback that computes the value the old way.
- Detect and reject a producer that is too old to be safe, with a message naming
  the required version - silently degrading is worse than refusing.
- One record per line, machine-readable only. Never parse human-facing text.

## 5. Settings and other partial mutations

Use an atomic load-mutate-save operation for a single key. Loading a whole
snapshot, changing one field, and saving the snapshot back loses every concurrent
write between the load and the save - and those races are intermittent enough to
be blamed on the UI for weeks.

Serialize writes behind one lock where the store is shared.

## 6. Tests that actually catch it

- Keep one **fixture per shipped version**. New migration = new fixture, and the
  old fixtures stay forever.
- Test: load old fixture -> migrate -> assert the resulting document, not just
  "did not throw".
- Test the chain end to end (oldest supported version to current), not only the
  newest step.
- Test the sidecar contract in both directions: new host + old producer, and new
  producer + old host if both ship.

## Red flags

- "It is only a rename" - it is a migration.
- "No one has old data" - shipped releases exist; the installer does not wipe.
- Editing an existing migration level to fix a bug in it.
- A new column with no index and a query that filters on it.
- A settings write path that saves a whole snapshot.
