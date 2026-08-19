---
name: determinism-and-golden-baselines
description: Use when changing rendering, audio/DSP, export, or any code guarded by golden traces, pixel-hash matrices, snapshot files, or visual baselines. Enforces the preview/export determinism law, routing through shared chokepoints, purity of presets, permanence of persisted IDs, and the discipline for re-blessing a baseline. Triggers - "the pixel hashes changed", "update the snapshots", "bless the baseline", "export looks different from preview", "add a new visual mode", "shader change broke tests", "golden trace mismatch".
when_to_use: When a change alters rendered output, audio features, export frames, or any recorded baseline; when a baseline test fails; when adding a preset/mode/effect; when deciding whether a snapshot may be updated.
type: prompt
whenToUse: When a change alters rendered output, audio features, export frames, or any recorded baseline; when a baseline test fails; when adding a preset/mode/effect; when deciding whether a snapshot may be updated.
disableModelInvocation: false
---

# Determinism and Golden Baselines

A baseline test is a recorded claim about output. Changing the recording is
changing the claim - it needs the same scrutiny as changing the code.

## 1. The determinism law

Preview and export must resolve **identical frames from the same document**.

- Everything time-dependent resolves from **track time**, never wall clock, never
  frame counter drift, never `Date.now()`.
- All time-dependent resolution goes through the shared chokepoints (in Beatform:
  `src/state/frameResolve.ts`, `src/export/buildExportOptions.ts`, and the overlay
  compose path). Code that computes its own time or reads state directly will
  silently diverge between preview and export - and the divergence usually only
  shows up in an exported file a user opens later.
- Presets/effects are **pure functions of `(features, time, params)`**. No hidden
  state between frames unless it is itself derived from track time and reset
  deterministically.
- Randomness, locale, and device capability must be injected and seeded, not
  sampled ambiently.

Before adding any feature that touches rendering, name which chokepoint it goes
through. If the answer is "none", the design is wrong.

## 2. The audio-to-render contract

Renderers see one type only (the `AudioFeatures` contract). Live and offline
sources drive the same feature pipeline - if a feature is available in one path
and not the other, preview and export cannot match. Extend the contract, not the
caller.

## 3. Persisted identifiers are forever

Preset IDs, mode IDs, theme keys and format names appear in saved projects,
shared looks, and localStorage. Never rename one in place. Add a canonical-ID
migration that maps old to new, keep the old ID resolvable, and test the
migration. Renaming a user-facing label is free; renaming the ID is not.

## 4. Baseline classes in this workspace

| Class | What it guards | Typical command |
| --- | --- | --- |
| GPU pixel-hash matrix | every visual mode renders the same pixels | `npm run test:gpu` / `npm run test:gpu:update` |
| Golden traces | frame resolution over a scripted timeline | part of `npm test` |
| Shader golden files | shader source/compilation output | part of `npm test` |
| Visual baselines | app UI screenshots | repo-specific capture procedure |
| Snapshot tests | serialized structures, guide/doc sync | `vitest -u` on the named file |

## 5. Re-bless protocol

A baseline may only be updated when all of these are true:

1. You **intended** the output change and can name the cause.
2. You **looked at it** on device - not just at the diff of hashes. A hash tells
   you something moved; only the eye tells you it moved correctly.
3. The number of moved cases matches expectation. Eleven new cases for one new
   mode is a story; 300 moved cases for a one-line tweak is a bug.
4. The commit body justifies it: what changed, why the new output is correct, how
   many cases moved.

Never bless to turn red green. Never bless a baseline you did not visually verify.
Never bless as part of an unrelated change.

## 6. New visual mode / preset checklist

- [ ] One file in the presets directory + one registry entry
- [ ] Pure function of `(features, time, params)`, resolved through the chokepoints
- [ ] Persisted ID chosen deliberately and never renamed later
- [ ] Pixel-matrix cases added and blessed with visual verification
- [ ] Every mode-counting surface updated (README, docs site, in-app guide, chips)
- [ ] Export path checked, not only preview
