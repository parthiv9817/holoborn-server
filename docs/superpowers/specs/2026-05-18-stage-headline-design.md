# Stage Headline — pipeline indicator readable from 5m (design spec)

**Date:** 2026-05-18
**Author:** Parthiv (with Claude Code)
**Status:** Spec, pending Parthiv review
**Scope:** New visual layer announcing the active backend stage during the ~3-5 min processing wait. Sits above the avatar in MR space. The existing Diagnostic Crescent (`PipelineProgressController`) is unchanged — this design is purely additive.
**Time budget:** Today (afternoon → evening) for spec + impl plan + C# authoring. Tomorrow morning for Unity Editor preview → APK → Quest validation → Inspector tuning → MP4 capture.
**Supersedes:** Nothing. This sits alongside the crescent.

---

## What we're building

After last Friday's raw demo viewing, Vipin's feedback was that the pipeline stages — currently surfaced only via the small cyan-node Diagnostic Crescent to the user's right of the avatar — are **not readable from 5m**. The recorded MP4 (and any live cast to a TV during demos) shows the crescent but the labels are too small for an audience to comprehend which step the pipeline is in.

This design adds a **billboarded stage headline above the avatar's head** during the processing wait. The headline consists of:

1. A **large word** (the current pipeline stage label) rendered as ~22 cm characters in world space, dominantly readable from across a room.
2. A **small evolving mandala glyph** above the word — a single procedural texture that gains a ring/spoke layer per stage, acting as a ritual "seal" anchor that frames the word as ceremonial instrumentation rather than HUD chrome.

Both elements yaw-billboard to the camera so the headline always faces the viewer in the MR capture. Both fade out 1 s before Stage 3's sigil-rise begins, leaving the sky above the avatar clear for the reveal.

**Conceptual frame:** the existing Stage 1+2+3 ritual frame ("scientist examining a biosymbiote specimen") is preserved. The headline reads as a label-card on a specimen chamber — like the engraved plate on a museum vitrine, sized for the room rather than the operator. The evolving mandala echoes the SummoningSigil prefab's slow-rotation aesthetic (same `secondsPerRotation = 30f` cadence), tying the headline visually to the floor sigil so they read as one ritual apparatus.

The existing Diagnostic Crescent stays exactly as shipped. Viewers close enough to read it get the full 6-stage timeline; viewers across the room get the headline.

---

## Why this design

**Why not bigger crescent?** The crescent works as a timeline-map for close inspection but its node-and-axon geometry is dense — scaling it 3× to be 5m-readable would make it visually heavy and compete with the avatar silhouette. The active stage's label is one line of one word — that's the load-bearing communicative element and the only thing that needs to scale.

**Why not pure A (headline only, no glyph)?** Vipin's feedback wasn't just "make it bigger" — he flagged that the current cyan-mapping has the right aesthetic register but the wrong size. A naked giant headline above the avatar reads as a sports-broadcast lower-third. The glyph mandala adds back the ritual register and visually anchors the headline to the floor sigil. Captivation + readability, not one or the other.

**Why not pure C (glyph dominant, word small)?** Glyph mandalas are aesthetically captivating but don't communicate stage meaning to a stranger. A demo viewer who has never seen the app needs the WORD to do the work. Glyph is the seal; word is the message.

**Why evolving mandala over 5 distinct glyphs?** One asset, one shader parameter (`_StageProgress` 0→1), procedurally additive growth. Matches the existing crescent's "neural growth" aesthetic (new nodes spawn, never deleted). Cheaper to build (one texture file vs five), more cohesive visually, and the growth-as-progress metaphor reinforces the pipeline arc.

**Why additive (zero edits to existing controllers)?** The Diagnostic Crescent works and was hard-won (5+ iteration spiral last Thursday). Touching it carries regression risk. The headline subscribes to the same `OnBackendStatusChanged` event chain — both indicators stay in sync without coupling.

---

## Locked decisions

### Placement

- **World anchor:** `mannequinController.SpawnedSigil.transform.position + Vector3.up * headlineHeight` — same anchor pattern the crescent uses, so the headline and crescent are co-located in world space.
- **Default `headlineHeight = 2.2 m`.** Avatar heads sit at ~1.7–1.8 m; +0.4 m clearance above the head puts the word at ~2.0 m baseline and the glyph mandala at ~2.3 m. Inspector-exposed.
- **Lateral offset:** zero — the headline sits **directly above the avatar's head**, not lateral. The crescent stays to the user's right; the headline stays centered. They don't compete spatially.
- **Yaw-billboard:** `FaceCameraYawBillboard` component (existing, reused from crescent labels). Headline always faces user but doesn't tilt — preserves the "world object" feel rather than HUD-follow.

### Components

- **`StageHeadlineController.cs`** (new) — orchestrates word + glyph + fade transitions. Lives on the SpawnRitual root GameObject alongside `PipelineProgressController`. Subscribes to `OnRitualBegin`, `OnBackendStatusChanged`, `OnAwakenedEnter`, `OnFailedEnter`.
- **`EvolvingMandalaController.cs`** (new) — manages the mandala texture/shader. Single public method `SetStageProgress(int stage, float t)` that drives a shader `_StageProgress` float from current ring count to next ring count over a fade duration.
- **`StageHeadline.prefab`** (new) — root prefab with: TextMeshPro 3D for the word + Quad mesh with `StageMandala_Mat` for the glyph + FaceCameraYawBillboard. Spawned at runtime by the controller, not pre-placed in scene.
- **`StageMandala_Mat.mat`** (new) — material using a new Shader Graph or simple unlit shader exposing `_StageProgress` (0–5) and `_BaseTex` (the layered mandala texture).
- **`stage_mandala.png`** (new) — 1024×1024 texture with 5 concentric ring/spoke layers in additive cyan. Each layer is gated by `_StageProgress` in the shader: layer N visible when `_StageProgress >= N`.

### Stage event mapping

Reuse `PipelineProgressController.MapStatusToStageIndex` for parity. The headline announces **only the 4 mid-pipeline waits** — indices 1 through 4. Capture (index 0) and Awakening (index 5) are instant moments that don't warrant a headline.

| Status | Stage idx | Label (kept from crescent) | Mandala layers visible |
|---|---|---|---|
| `portraitizing` | 1 | "Refining Portrait" | 1 |
| `generating` | 2 | "Sculpting Body" | 2 |
| `retexturing` | 3 | "Painting Skin" | 3 |
| `rigging` | 4 | "Adding Bones" | 4 |
| `complete` → `OnAwakenedEnter` | (5) | (headline fades out) | (fades out) |

**Label register:** kept verbatim from `PipelineProgressController.StageLabels` — friendly-descriptive, not raw-functional, not invented-ritual. Consistency with the crescent wins over re-themeing. Capitalization is applied at render time (`text.text = label.ToUpper()`).

### Sizing (Inspector-exposed, defaults for first tune)

- **Word font size:** `0.22` (TMP 3D world-space units → ~22 cm character height). Tunable.
- **Word color:** `#E6F4F5` (warm-white, matches the mannequin's emissive). Glow effect via TMP's outline + dilate, color `#7FDCE8` (cyan, matches crescent nodes).
- **Word letter spacing:** `0.05` (subtle expansion — reads as carved-stone, not bunched).
- **Glyph quad size:** `0.30 m` wide × `0.30 m` tall.
- **Vertical gap word→glyph:** `0.08 m` (glyph baseline 8 cm above word top).
- **Glyph rotation:** `0.0166 rev/s` (= one revolution per 60 s — slower than the floor sigil's 30 s, so they read as related but not synchronized — gives the composition slight visual life).

### Transitions

**On `OnBackendStatusChanged(status, progress)`:**

If `MapStatusToStageIndex(status)` returns 1–4, queue an `AdvanceTo(newStage)` (mirror the crescent's `_pendingTargets` queue for safety against out-of-order events).

For each step from current → target:

1. **Old word fades out + slight downward drift** — 0.4 s. Mirrors crescent's `DemoteNode` cadence.
2. **Mandala grows next ring** — `EvolvingMandalaController.SetStageProgress(newStage, 0.6f)` drives the shader float, animated over 0.6 s with Smootherstep (existing helper).
3. **New word fades in with scale-pop** — text starts at scale 1.1× → settles to 1.0× over 0.5 s while alpha 0 → 1. Reads as "next thing is announcing itself."

Total transition duration: ~1.5 s per step (overlapping where appropriate: glyph growth + word fade-in run in parallel after the word fade-out completes).

**On `OnAwakenedEnter`:**

Both word and glyph fade out + drift upward over 1.0 s, then `Destroy(gameObject)` the headline root. By the time Stage 3's sigil-rise begins (which fires from `OnRevealedEnter` ~0–0.3 s after `OnAwakenedEnter`), the airspace above the avatar is clear.

**On `OnFailedEnter`:**

Fade out over 0.6 s, no error state visual. Failure is communicated by the absence of the reveal, not by a red banner. Preserves ritual register even on failure.

**On `OnRitualBegin`:**

If a previous headline exists from a prior run, destroy it. Reset `_currentStageIndex = -1`. Wait for sigil to be available (same pattern as crescent's `ProcessGrowthQueue`).

### Side crescent

**Unchanged.** Stays at 6 nodes (Capture → Awakening). No edits to `PipelineProgressController.cs`. The two indicators coexist: headline as the dominant 5m-readable element, crescent as the close-inspection timeline map.

### Failure modes

| Scenario | Behavior |
|---|---|
| Status arrives before sigil anchor ready | Queue, drain when sigil appears (mirror crescent's `while (SpawnedSigil == null) yield return null`) |
| Status arrives out of order (idx ≤ current) | No-op (target ≤ current → return) |
| `OnFailedEnter` mid-pipeline | Fade out over 0.6 s, no error visual |
| Quest camera missing at headline spawn | Fallback to `Vector3.forward` for billboard, log warning (mirror crescent's `Camera.main` null handling) |
| Mannequin destroyed mid-ritual | Anchor falls back to controller's transform position (mirror crescent's pattern) |

### Testing

- **EditMode unit tests** in `Tests/EditMode/StageHeadlineControllerTests.cs`:
  - `MapStatusToStageIndex` returns expected indices (1–4 for the four wait statuses, -1 for unknown)
  - `AdvanceTo` is idempotent for already-passed stages
  - Out-of-order targets do not regress current index
  - Pending queue drains in order
- **Visual tests:** tomorrow morning in Unity Editor Play mode (verifies spawn position + transitions + billboard) → APK build → Quest test (verifies actual MR readability from 3-5 m).
- **No automated MR tests** — Quest validation is manual, captured via MP4.

---

## What this design explicitly does NOT do

- **No re-styling of the existing crescent.** It stays exactly as Thursday-night shipped.
- **No subtitle line** under the word (e.g., "refining the visage"). The brainstorm hybrid mockup had one — dropped from spec for cleaner silhouette per Parthiv's read; the word + glyph carry the register alone.
- **No error/failure state visual.** Failures play out as silence, not red banners. Ritual immersion holds even on failed runs.
- **No 5-glyph asset library.** One evolving mandala, one texture, one shader.
- **No new audio cues.** The existing SummoningSigil audio source carries the ritual ambience; the headline is silent.
- **No headline for Capture (idx 0) or Awakening (idx 5).** Capture is instant pre-pipeline; Awakening is the reveal moment itself (visual is the avatar, not text).

---

## Receipts of building blocks (existing, reused, zero changes)

| Asset | Used as |
|---|---|
| `SummoningSigil.prefab` | Pattern reference for the glyph quad (textured plane + slow Y-rotation) |
| `SummoningSigil_Mat.mat` | Pattern reference for `StageMandala_Mat` (unlit cyan emissive) |
| `SummoningSigilController.cs` | Pattern reference for rotation (`degreesPerSecond = 360f / secondsPerRotation`) |
| `FaceCameraYawBillboard.cs` | Drop-in component on the headline root |
| `SpawnRitualController.OnBackendStatusChanged` | Event subscription |
| `SpawnRitualController.OnRitualBegin` | Event subscription |
| `SpawnRitualController.OnAwakenedEnter` | Event subscription (fades headline out) |
| `SpawnRitualController.OnFailedEnter` | Event subscription (fades headline out) |
| `AnatomicalMannequinController.SpawnedSigil` | World anchor for headline position |
| `PipelineProgressController.MapStatusToStageIndex` | Reuse verbatim — would refactor into a shared util later, not in this scope |
| `PipelineProgressController.StageLabels` | Source of truth for label strings |
| Smootherstep helper | Existing static (or inline copy) for fade curves |

---

## Open question for tomorrow's Quest test

How much glow/bloom does TMP need for 5m readability through Quest passthrough? URP bloom is enabled per the crescent's `nodeActiveIntensity > 1f` design. The word's outline + dilate parameters and emissive multiplier will be Inspector-exposed; tomorrow morning's first APK test is to tune them by eye on the headset. Expectation: `wordEmissiveIntensity = 2.5–4.0`, `outlineWidth = 0.15–0.25`. Locked at first-look tuning, then MP4 capture.

---

## Implementation order (will be expanded in writing-plans pass)

1. Create `EvolvingMandalaController.cs` + `StageMandala_Mat.mat` + `stage_mandala.png` (texture asset is the one thing we may need to generate via Midjourney/SVG → PNG today)
2. Create `StageHeadlineController.cs` with Inspector knobs for all sizing/timing/color
3. Create `StageHeadline.prefab` (TMP + quad + billboard children)
4. Wire onto SpawnRitual root GameObject in the demo scene
5. EditMode tests for state machine
6. Tomorrow: APK → Quest → tune Inspector values → MP4 capture

End of spec.
