---
name: desktop-app-ux-polish
description: Use when building or fixing the user-facing shell of a Windows desktop app in this workspace - WinUI 3, WPF, or a Tauri/React shell. Covers 200 percent display scaling, dark-first theming with runtime accents and verified contrast, parse-time resolvable resources, honest progress and long-job controls, confirmation dialogs that survive the platform ACL, i18n completeness, and verifying against the actually-built binary. Triggers - "the UI looks off", "cards are invisible", "app does not start after a theme change", "layout breaks at high DPI", "add a progress bar", "cancel/resume button", "dark mode", "accent color", "half-translated".
when_to_use: When touching app-shell UI, themes, layout, progress reporting, or long-running job controls in StorageMaster, Beatform, TubeForge, Playlist DL, or a similar desktop app; when a UI defect is reported; when verifying UI behavior in the running app.
type: prompt
whenToUse: When touching app-shell UI, themes, layout, progress reporting, or long-running job controls in StorageMaster, Beatform, TubeForge, Playlist DL, or a similar desktop app; when a UI defect is reported; when verifying UI behavior in the running app.
disableModelInvocation: false
---

# Desktop App UX Polish

App-shell behavior for the desktop apps in this workspace. For XAML control choice,
Fluent specifics, and binding syntax, use the `winui-design` / `dotnet-wpf-modern` /
`dotnet-accessibility` skills - this skill is the house rules that sit on top.

## 1. Scale and layout

- **200 percent display scale is this machine's default.** Every page is verified
  at 200 percent, not only at 100.
- No star-sized panel that can starve to zero height. Lists inside scrollable pages
  need explicit Min/MaxHeight.
- Long strings grow when translated and at large scale - no fixed-width label that
  clips.
- Window can be small: check the minimum size the app actually allows.

## 2. Theming

- Dark-first identity, light supported, both verified for contrast on real
  content - not on the palette swatch page.
- Accents are selectable at runtime; nothing hardcodes an accent value.
- **Resources must resolve at parse time.** A palette entry that only resolves at
  runtime fails the whole app start, not the one control.
- Verify the painted result, not the resource dictionary. The classic defects here
  were invisible cards and a wallpaper-tinted shell that both looked correct in
  markup: black seams between panels, translucency over the wrong layer, badges
  that ignore the current theme.
- Theme work and localization travel together - a new theme string that only exists
  in English produces a half-translated UI.

## 3. Progress and long-running jobs

- Report the rate you actually measured (files/sec, MB/sec). **Do not invent an
  ETA** you cannot support; a rate with no ETA beats a fictional countdown.
- Every long job offers: pause, resume, cancel, retry, and reveal-in-folder for
  its output.
- Bounded concurrency with a visible worker count; releasing a worker slot the
  moment a job stops using the network/disk.
- Interrupted work is recoverable: sessions and queues survive a restart and offer
  to resume rather than silently vanishing.
- Progress that reaches 100 percent means done - never a spinner that lies while a
  verification step still runs.

## 4. Dialogs and confirmation

- In the Tauri shell, `window.confirm` / `window.alert` are blocked by the dialog
  plugin ACL and fail silently. Use the app's `askConfirm()` helper
  (`src/state/platform.ts`); an eslint rule enforces this.
- Destructive actions are confirmed with the real numbers (item count, bytes) -
  see `destructive-operation-safety`.

## 5. Responsiveness

- No repository query, hashing, enumeration, or badge computation on the UI or
  dispatcher thread.
- Virtualize long lists; do not bind a 100k-item collection directly.
- See `measured-performance-work` when a stall needs a number.

## 6. States that are usually forgotten

First run, empty result, permission denied, drive removed mid-operation, no
network, item deleted underneath the view, and the error state with an actionable
message rather than an exception string.

## 7. Verify in the running app

- Build the runnable binary explicitly - a solution build does not always refresh
  a platform-specific UI exe.
- **Check the exe timestamp before trusting what you see.** A stale exe once cost
  ~40 minutes of hunting a bug that was already fixed.
- Where visual baselines exist, capture them per the repo's procedure and treat a
  diff as a claim (see `determinism-and-golden-baselines`).
