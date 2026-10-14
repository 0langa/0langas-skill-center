---
name: windows-release-ritual
description: Use when cutting, preparing, verifying, or fixing a release of a Windows desktop app or a versioned package in this workspace. Covers version bump surfaces, changelog as user-facing UI, tag and CI watch, artifact and checksum verification, installer/portable variants, verified in-app updater with rollback, code-signing status, and post-release doc updates. Triggers - "cut a release", "ship v2.4.0", "prepare the changelog", "the release workflow failed", "the updater did not work", "publish the GitHub release", "bump the version".
when_to_use: When preparing or publishing a version, writing release notes, debugging a release workflow or updater, or verifying that a published release is actually installable and upgradeable.
type: prompt
whenToUse: When preparing or publishing a version, writing release notes, debugging a release workflow or updater, or verifying that a published release is actually installable and upgradeable.
disableModelInvocation: false
---

# Windows Release Ritual

These apps ship as free GitHub Releases, unsigned, with in-app verified updates.
A release is not "tagged" - it is tagged, built, published, downloaded, installed,
and upgraded from the previous version.

## 0. Automation first

Check for a repo release script before doing any step by hand
(e.g. `node scripts/release.mjs X.Y.Z --title "..."`). Where one exists it is
resumable and it encodes the checklist - running the steps manually re-introduces
the drift the script was written to remove. Read the script, then run it.

`gh` on this machine needs the environment PAT stripped (equivalent of
`env -u GITHUB_TOKEN`); repo release scripts already do this. If you call `gh`
yourself and get an auth error, that is the cause.

## 1. Preconditions

- All gates green on the release branch (see `repo-quality-gates`), including the
  device/E2E gates for every area this version touched.
- Docs updated; no half-finished item silently riding along.
- Previous release's known issues either fixed or restated in the new notes.

## 2. Bump every version surface

Version lives in more than one file. Find them all before tagging:

- Node/Tauri: `package.json`, `src-tauri/tauri.conf.json`, `Cargo.toml`
- .NET: `Directory.Build.props` (version + assembly/file/informational version), installer script
- Python: `pyproject.toml`, plugin manifests (`plugin.json`, `kimi.plugin.json`, `forge.yaml`)

A mismatched assembly version breaks update detection even when the release page
looks correct.

## 3. Changelog is user-facing UI, not a commit log

In apps whose update dialog imports `CHANGELOG.md`, the entry **is** shipped
product text. Write release notes: what a user can now do, what got fixed in terms
they experience, what they must do manually. No commit hashes, no internal file
names. Editing it while a dev server runs reloads the app - expected.

## 4. Tag, watch, publish, verify

1. Commit + tag + push.
2. Watch CI to completion - do not publish off a running or failed build.
3. Verify the published assets exist and match the matrix the docs promise:
   installer `.exe`, portable self-contained ZIP, framework-dependent ZIP.
4. Verify checksums: published casing normalized, values match the built files.
5. Release is published, not draft; notes attached; tag points at the built commit.

Antivirus scan steps and verification retries should degrade gracefully - a
scanner that cannot run is not a reason to fail an otherwise-good release, but it
must be visible in the log.

## 5. Prove the update path

The most common post-release defect in this portfolio is the updater, not the app:

- Install the **previous** version, then update from inside it.
- Confirm the update button enables, the progress reaches 100 percent from real
  streamed bytes, and the installer handoff completes.
- Confirm rollback: the retained copy exists during the update and is removed once
  the new version proves itself.
- Confirm the startup prompt behaves on first launch of the new version.
- If an older version cannot self-update, say so in the notes with the manual
  install instruction - do not assume users will discover it.

## 6. Honest status

Binaries are currently unsigned across these apps. SmartScreen warnings are
expected. Never write notes implying signing, notarization, or store distribution
that did not happen.

## 7. After publishing

- Update `CHANGELOG.md` links, `README.md` current-version lines, docs that name
  the version.
- Close the release item where it is tracked (issue or PR) and record deferrals
  there or in the release notes.
- Never run `git commit`, `git push`, `git tag`, `git reset` or `git rebase`
  unless the user explicitly asked for it in this session.

## Checklist

- [ ] Repo release script used where it exists
- [ ] Gates green, device gates included
- [ ] Every version surface bumped consistently
- [ ] Changelog written as user-facing release notes
- [ ] CI watched to green before publish
- [ ] Assets + checksums verified on the published release
- [ ] Upgrade from previous version tested, rollback path confirmed
- [ ] Unsigned status stated, not implied away
- [ ] Docs updated, deferrals recorded
