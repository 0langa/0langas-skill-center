---
name: local-first-scope-guard
description: Use when a feature, dependency, or release decision could cross this portfolio's product invariants - free and open source, GitHub Releases only, no cloud services, no accounts, no telemetry, no paid tiers, no store distribution, minimal third-party dependencies, and honest legal notices for media tools. Triggers - "add analytics", "sync to the cloud", "premium tier", "sign in", "publish to the Store", "add this npm/NuGet package", "crash reporting", "phone home", "check for a licence key", "we could monetize".
when_to_use: When proposing or reviewing anything that adds a network dependency, an account, a paid surface, a store channel, telemetry, or a third-party package; when writing README/legal/privacy text for a downloader or media tool; when handling credentials.
type: prompt
whenToUse: When proposing or reviewing anything that adds a network dependency, an account, a paid surface, a store channel, telemetry, or a third-party package; when writing README/legal/privacy text for a downloader or media tool; when handling credentials.
disableModelInvocation: false
---

# Local-First Scope Guard

These products have a deliberate shape. The shape is the product - a feature that
breaks it is not an improvement, it is a different application.

## 1. Product invariants

Free, open source, distributed as GitHub Releases. Specifically **not**:

- cloud services or a hosted backend
- user accounts, sign-in, or licence keys
- telemetry, analytics, crash reporting that leaves the machine
- paid tiers, trials, upsells
- app-store distribution

Never propose these, even as an "optional" or "opt-in" addition, unless the user
explicitly opens that door. If a feature genuinely needs one, say which invariant
it breaks and offer the local-first alternative instead of implementing it.

**Version discipline**: where a repo states that a major version is a quality bar
rather than a milestone (Beatform's v3.0.0), keep shipping the current major -
never propose cutting the next one to make a feature land.

## 2. Dependency minimalism

Some projects here are deliberately built without third-party packages at all
(TubeForge: C# from scratch, no third-party NuGet). Before adding **any**
dependency:

1. Check the project's stated stance in its README/AGENTS.md.
2. State what it replaces and why the standard library is insufficient.
3. Check its licence and its transitive surface.
4. Prefer a small vendored routine over a package for a small problem.

Adding a dependency is a product decision, not an implementation detail - ask.

## 3. Data locality

- User data stays under the app's local directory (`%LOCALAPPDATA%\<App>`) or in
  the user-chosen output folder.
- No network call beyond the product's declared purpose (fetching the media the
  user asked for, checking the GitHub release feed).
- Optional credentials (a user's own API client ID) are the user's, stored
  locally, never required for the core path, never transmitted anywhere else.

## 4. Legal surface for media tools

Downloader and capture tools carry real obligations. Keep them explicit and
honest:

- A prominent user-responsibility notice: comply with the platform's terms,
  copyright, privacy, and local law; download only what you own or may save.
- State plainly that the tool does **not** bypass DRM, payment, membership, login,
  or other access controls - and keep that true in the code.
- No claim of rights to hosted media; no affiliation with the platforms.
- A privacy document stating what is stored and that nothing is transmitted.
- A threat model file where the app parses hostile input or runs external
  binaries.
- `SECURITY.md` with a reporting path.

Do not soften these to make a release page read better, and do not add a feature
whose only purpose is circumventing an access control.

## 5. Third-party notices

Bundled binaries (ffmpeg and friends) get `THIRD_PARTY_NOTICES.md` entries with
licence and exact version, shipped unmodified. See `sidecar-process-integration`.

## 6. Secrets

Never read, print, copy, or commit `.env` files or credential stores. When a task
touches MCP configs, OAuth, or auth setup, assume credentials are nearby and keep
them out of logs, diffs, and chat output.

## 7. Distribution honesty

Binaries are unsigned; SmartScreen warnings are expected. Say so in the docs.
Never imply signing, notarization, or store review that did not happen.
