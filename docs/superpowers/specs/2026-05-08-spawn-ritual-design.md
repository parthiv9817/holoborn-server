# HoloBorn Spawn Ritual & World-Anchored Progress — Design Spec v2

**Author:** Parthiv (with Claude Code)
**Date:** 2026-05-08
**Status:** v2 — cross-AI feedback (ChatGPT + Gemini) integrated. Locked for implementation.
**Target ship:** Today (2026-05-08) + Saturday (2026-05-09). Sunday is demo capture day.

---

## v2 changes from v1 (cross-AI review integrated)

| v1 → v2 change | Why |
|---|---|
| **6 phases → 5 phases** (P4 rigging + P5 animating merged into "Internal activation") | Both AIs flagged P4-P5 as the weakest beats; merging gives one clear semantic phase instead of two ambiguous ones |
| **Eye-glow at spawn → killed, replaced with first-breath + gaze acquisition** | Both AIs called eye-glow a 80s-robot trope. Breath + gaze sells "presence" without cheese |
| **"Cubes rain from above" → "Cubes emerge upward from floor circle"** | ChatGPT: vertical column at spawn site = stronger spatial anchor, anime-summoning vocabulary. User agreed. |
| **Continuous thrum (5 min loop) → sparse event-driven audio + fade-to-near-silence** | Both AIs: continuous loop at this duration becomes tinnitus. Heartbeat pattern instead. |
| **Cyan dominant → white-dominant with cyan accent (90% white / 10% cyan)** | Gemini: pure cyan = "default URP emissive" / "generic sci-fi." 90/10 ratio is what makes Vision Pro feel expensive. ChatGPT pushed for purple/amber but cyan still maps best to scan/reconstruct metaphor. |
| **Bone-glyphs in P4 → killed, replaced with energy-pathway lines (joint-to-joint traces)** | ChatGPT: literal bone graphics inside cube cloud cause URP alpha depth-sort issues. Gemini: "internal lines ignite, NOT literal bones." Both right. |
| **300 individual GameObject cubes with per-cube `Update()` → single `CubeCloudManager` with flat Transform array, one centralized `Update()` loop** | ChatGPT: 300 individual `Update()` callbacks tank Quest 3 CPU; centralized manager keeps perf above 72 fps |
| **Vert sampling: ambiguous → explicit: sample on Quest from generic placeholder mesh during P3-P4, resample from actual GLB at P5** | ChatGPT's architectural question forced this resolution. Real GLB doesn't exist during P3-P4, so we use a static placeholder (`Assets/HoloBorn/Models/silhouette_placeholder.fbx`, ~5-10K tris, T-pose). |
| **P1 user-side particle burst → killed, replaced with single bright "lock" flash + haptic + camera-shutter audio** | ChatGPT: particles from user is noise that fights the cube show. The cubes are the show. |
| **Drop shadow added as explicit grounding requirement** | ChatGPT: avatar without contact shadow = "2D sticker floating in passthrough." Already on Tier 1 plan as #4 (blob shadow), now confirmed as load-bearing. |

---

## TL;DR

The HoloBorn backend takes 7-10 minutes to produce a rigged avatar (portraitizer + RunPod TRELLIS + Meshy). A 2D progress bar fails in VR because the user has the entire room available and would stare at static glass for that whole duration.

**Solution:** a continuous cube-cloud assembly visible at the eventual spawn location, growing and changing across all backend phases via 5 distinct beats, climaxing in a 2.5-second snap-to-mesh ritual when the rigged GLB arrives. The waiting time becomes emotional theater, not dead latency.

This single feature absorbs four locked Tier 1 items (#3 spawn ritual, #5 spatial audio, #6 haptics, #7 world-anchored progress) into one coherent visual+audio+haptic system.

**The strongest psychological design call:** the cube cloud assembles in the EXACT location where the avatar will spawn. The user's brain assigns permanence, anticipation, and spatial ownership to that spot during the wait — that's spatial-native UX that doesn't exist in 2D.

---

## Aesthetic references (videos for visual vocabulary)

Watch these in order — fastest payoff first. The user has limited VR exposure and these establish the visual language.

1. **Westworld host construction scenes** (HBO S1) — primary reference, "person being built in front of you"
2. **Avengers: Endgame Iron Man Bleeding Edge nanotech** — particle/cube assembly, snap-to-position discipline
3. **Apple Vision Pro launch video** (apple.com/vision-pro) — "premium VR" baseline. Note: 90% white, 10% cyan accent.
4. **Iron Man 2/3 Jarvis hologram lab** — translucent geometric panels, layered depth
5. **Detroit: Become Human Kamski reveals** — minimal cyan/white, particle-formed
6. **Ra.One / Transformers Galvatron build** — programmable-matter cube assembly

Shared language: **room-anchored**, **depth-layered**, **controlled motion** (NOT chaotic), **monochrome accent at 10%** (the rest is white/neutral), **spatial audio** coming FROM the holograms.

The cubes should move like *a machine with intelligence*, NOT *magic particles*. That distinction determines whether the demo reads as "premium product" or "student VFX reel."

---

## Storyboard — 5 phases, all with active visual content

```
PHASE 1 — Capture (instant, ~0.3s)
  • Floor circle ignites with bright "lock" flash (1 frame, white)
  • Haptic pulse on left controller
  • Camera-shutter audio cue (single-shot, spatial)
  • NO user-side particle burst (the cubes are the show, user is not)
  • Backend: POST /generate-multiview → returns task_id

PHASE 2 — Energy accumulation (~30-60s, portraitizer)
  • Cubes start emerging UPWARD from the floor circle into a slow vertical column
  • ~50-100 cubes, light density, white-with-cyan-accent
  • Cube arrival rate: 5-10/sec
  • Soft thrum FADES IN, holds briefly, FADES TO NEAR-SILENCE (no continuous loop)
  • Floor circle pulses faintly synced to the thrum's fade
  • Active motion every second — never static

PHASE 3 — Humanoid reconstruction (~3-5 min, RunPod TRELLIS, the long one)
  • Vertical column compresses; cubes start finding silhouette positions
  • Target positions sampled from generic humanoid placeholder mesh
    (static .fbx, ~5-10K tris, T-pose, ships in Assets/HoloBorn/Models/)
  • Cube arrival rate increases to 20-30/sec
  • Cubes "snap and stay" along the silhouette surface
  • RunPod % directly maps to silhouette completeness:
      0% = empty silhouette, vortex remnant
      100% = full humanoid silhouette of ~300 stationary cubes
  • Color drift within white-cyan palette (ice-cyan accent intensifies as % climbs)
  • Audio: event-driven subtle "click" on every Nth cube locking, NO continuous loop
  • Motion progression: chaotic early → organized streams mid → locked silhouette late
    (This subconsciously communicates "reconstruction convergence" — Gemini's insight)

PHASE 4 — Internal activation (~30-60s, MERGED Meshy rigging + animating)
  • Silhouette holds steady (humanoid cube shell)
  • 3-4 energy-pathway lines ignite along joint-to-joint paths INSIDE the cloud:
      spine, both arms, both legs (additive blend, low alpha to avoid depth-sort issues)
  • A subtle pulse travels along each pathway (1-2s cycle)
  • NO literal bone glyphs, NO whole-cloud thinking pulse, NO rehearsal motion
  • Audio: 1-2 subtle structural "lock" sounds, then silence
  • Builds anticipation through STILLNESS not motion (premium = restraint)

PHASE 5 — Spawn ritual (the 2.5s climax)
  • Cubes flow inward, snap to actual mesh vertex positions
    (resampled from the real rigged GLB after glTFast InstantiateMainSceneAsync)
  • PBR avatar mesh fades in underneath as cubes land (alpha 0→1 over 1.5s)
  • Settled cubes dissolve into emissive sparkles → vanish
  • Avatar takes a SUBTLE FIRST BREATH (chest expand, shoulders settle, ~0.4s)
  • Avatar's gaze acquires the user (head turns slightly toward user position)
  • Idle animation begins (Meshy's baked Idle clip, AnimationMethod.Legacy)
  • NO eye-glow (killed — too "robot awakening")
  • Audio: spatial whoosh during cube flow → soft chime at breath → quiet
  • Haptic pulse on left controller at the breath moment
```

---

## Implementation order (foundations first, ~11hrs)

### Step 1 — `CubeCloudManager` + cube prefab (~2hr)

- Low-poly cube prefab (12 tris, single-color white-with-emission cyan accent material, unlit)
- `CubeCloudManager.cs` — owns a flat array of N=300 Transform references. Pool-based: `Spawn(origin) → Cube`, `Despawn(cube)`. Manages ALL per-frame motion in a single `Update()` loop iterating the array. **No per-cube `MonoBehaviour.Update()`** — critical perf rule.
- Pool size: 400 (300 active peak + 100 buffer)
- **Done when:** spawn 300 cubes in Editor, verify Profiler stays >72 fps at all times, verify zero per-cube Update callbacks via Profiler.

### Step 2 — Cube target-position lerp (~1hr)

- Each Cube has `targetPosition` + `lerpDuration` + `startTime` fields. Manager iterates and lerps each frame with ease-out curve.
- `cube.SetTarget(Vector3 worldPos, float duration)` — public API.
- **Done when:** spawn 100 cubes at random positions, call `SetTarget(humanoidVert, 2f)` on each; cubes converge to silhouette in 2s with smooth easing.

### Step 3 — Vortex behavior (~30min)

- `VortexBehavior` component on the Manager. Given center+axis+radius+height, computes orbit position around vertical axis above floor circle for any cube assigned to vortex group.
- For Phase 2: cubes orbit slowly (1 revolution / 4s), light vertical drift to simulate energy column rising.
- **Done when:** 50 cubes in vortex behavior, smooth orbit, no jitter or popping.

### Step 4 — Silhouette behavior with placeholder mesh (~2hr)

- Static asset: `Assets/HoloBorn/Models/silhouette_placeholder.fbx` — ~5-10K tris humanoid, T-pose. Source: Mixamo free download or Marvelous Designer template (~30min one-time prep).
- `SilhouetteBehavior` component — given target mesh + coverage % (0-1), assigns each cube a target vertex sampled from the mesh. Coverage = fraction of cubes that have a silhouette target (rest stay in vortex).
- **Done when:** load placeholder mesh, call `SetCoverage(0.5)`, verify 50% of cubes are at silhouette positions and 50% remain in vortex.

### Step 5 — Snap-to-mesh shader + dissolve (~3hr)

- Vertex displacement shader on the cube material. A cube's quad verts lerp from "cloud position" to "real mesh vert position" over 2.5s.
- After snap: alpha fade 1→0 over 1s with emissive boost (sparkle effect).
- **Critical:** at P5 entry, real GLB has been instantiated by glTFast — manager resamples target positions from `SkinnedMeshRenderer.sharedMesh.vertices` of the real avatar (not the placeholder).
- **Done when:** 300 cubes positioned along placeholder silhouette, real GLB instantiated, trigger snap, all cubes converge to real mesh verts in 2.5s and dissolve cleanly with no visible pop.

### Step 6 — Phase orchestrator state machine (~1.5hr)

- `SpawnRitualController.cs` — listens to backend status (existing `/generate/{task_id}/status` poll), drives 5 phase transitions.
- States: `IDLE → P1 → P2 → P3 → P4 → P5 → IDLE_AVATAR`
- **Backend status mapping:** `portraitizing` → P2, `generating` (with `progress` 0-100) → P3, `rigging` OR `animating` → P4, `complete` → P5
- **Backend change required (~30min):** `app/routes/generation.py` schema needs to expose `portraitizing | generating | rigging | animating | complete` status values instead of current `processing | complete | failed`. Backwards-compat shim acceptable.
- **Done when:** simulate fake status updates in sequence, verify all 5 phases visually transition correctly in Editor.

### Step 7 — Audio + haptics layer (~1hr)

- `SpawnRitualAudio.cs` — Unity AudioSource at world-point above floor circle, `spatialBlend = 1.0`
  - **P1:** single camera-shutter shot + haptic pulse on left controller (capture lock)
  - **P2:** thrum fades in over 5s, holds 5s, fades to near-silence over 5s — does NOT loop
  - **P3:** event-driven subtle "click" on every Nth cube locking position (N tuned so total click count over phase = ~30-50)
  - **P4:** 1-2 subtle structural "lock" sounds, then silence
  - **P5:** spatial whoosh during cube flow (1.5s) → soft chime at breath moment → ambient idle layer fades in
- Haptics: `OVRInput.SetControllerVibration(amplitude, frequency, controller)` on capture lock (P1) + breath moment (P5)

### Step 8 — Polish pass (~1.5hr)

- Color drift: white-dominant cube material with cyan emissive accent that intensifies through P3 (subtle, never overwhelming — we're targeting Apple Vision Pro restraint, not cyberpunk maximalism)
- Energy-pathway lines (Phase 4): 3-4 LineRenderer strokes between joint positions on the placeholder mesh, additive shader, low alpha. Pulse animation on `_BaseColor` over 1-2s cycle.
- Breath + gaze acquisition (Phase 5):
  - Breath: small `Animator` blend on the spawned avatar's chest+shoulder bones (procedural, ~0.4s, ease-out)
  - Gaze: `head.LookAt(camera.position)` with 0.5s eased rotation, then settle into idle
- Cube dissolve sparkle particle (Phase 5): Unity built-in particle burst on cube despawn, ~5 particles per cube, 0.3s lifetime, additive

**Total: ~12 hours.**
- Today (~5hr remaining after this planning): Steps 1-3 + start of Step 4
- Saturday (~7hr): Steps 4-8

---

## Generic humanoid placeholder mesh

Static asset shipping with the Unity app. Used as silhouette target during P3-P4 before real GLB exists.

- **Path:** `Assets/HoloBorn/Models/silhouette_placeholder.fbx`
- **Topology:** ~5-10K tris, single mesh, no materials, no animations
- **Pose:** T-pose
- **Source options:**
  - Mixamo (free) — download any base mesh, retopologize if >10K
  - Adobe Marvelous Designer — humanoid base
  - Sketchfab CC0 — humanoid base
- **Prep time:** ~30 min one-time
- **Why static:** real GLB doesn't exist during P3-P4 phases; we need a stable target geometry for cubes to converge on. Placeholder is invisible to the user (it's not rendered), only its vertices are sampled as cube targets.

---

## Quest 3 performance budget

| Element | Count | Tris | Notes |
|---|---|---|---|
| Cubes (peak, P3-P5) | 300 | 12 each = 3,600 total | Low-poly, single material, GameObject-pooled but driven by single manager Update |
| Avatar mesh (final, P5+) | 1 | ~30,000 (Meshy decimation) | Validated 2026-05-07 |
| Placeholder mesh (P3-P4 internal) | 1 | ~5-10K (sampling target only) | Never rendered |
| Floor circle | 1 | ~32 | Quad with circular alpha cutoff |
| Energy-pathway lines (P4) | 3-4 | ~10 each | LineRenderer, additive blend |

**Frame target:** stays >72 fps in Quest Profiler during all 5 phases. Hard floor: never below 60 fps even at P5 climax (300 cubes flowing + mesh fading in + sparkles + breath/gaze + audio + haptics simultaneously).

**Architectural rule (from ChatGPT review):** all cube motion goes through `CubeCloudManager.Update()`'s single iteration. ZERO per-cube `MonoBehaviour.Update()` callbacks. Per-cube callbacks at 300×72fps = 21,600 callbacks/sec — measurably murders Quest 3 CPU.

**Fallback ladder if perf is tight:**
1. Drop cube count: 300 → 200 → 150 → 100. Below 100, the cube aesthetic is lost.
2. Drop energy-pathway lines (Phase 4 still has audio + stillness)
3. Drop color drift, lock to single white-cyan material
4. **Last resort:** switch to `Graphics.DrawMeshInstanced` (GPU-batched, no GameObjects). Loses per-cube target-position control unless we ship a custom compute shader. ~2hr extra work if needed.

---

## Acceptance criteria (objective, not subjective)

To prevent the 2026-05-07 mistake #1 pattern (Claude misreading Quest screenshots and calling things "great" when they had visible artifacts), each phase has objective pass criteria. **Measured, not judged from a screenshot.**

| Phase | Pass criteria |
|---|---|
| P1 | Floor circle bright-flash for ≤1 frame; haptic fired (verified via OVRInput debug log); shutter audio fired (verified via AudioSource.isPlaying log) |
| P2 | Cube count grows 0 → 50-100 over 30s (verifiable via manager pool count); thrum fades in, holds, fades to near-silence (verified via Audio Mixer dB tracking); Profiler shows steady >72 fps |
| P3 | At backend `progress=50%`, exactly 50% of cubes are in silhouette positions (instrumented log); at 100%, all cubes stationary on silhouette; FPS holds; "click" events fired ~30-50 total (verified via log) |
| P4 | Silhouette cube count holds steady ±2 (no drift); energy-pathway lines render with positive alpha (≥0.05); 1-2 lock sounds fired; rest of phase has zero scheduled audio events |
| P5 | All 300 cubes converge to real mesh vert positions in 2.5s ±0.1s (instrumented timing); mesh alpha 0→1 over 1.5s; cubes alpha 1→0; breath bone motion plays for ≥0.3s; gaze rotation acquires camera target within ±5° in 0.5s; total spawn frame budget <40ms |

**Subjective visual reads (Claude's job NOT to assert):**
- "Does it FEEL premium?" — user-only call
- "Does the color look right?" — user-only call
- "Is the timing right?" — user-only call

When user reports something looks off, defer to their empirical observation. Claude's value is narrowing the bug-search-space via logs/code/architecture, not subjective screenshot interpretation.

---

## Out of scope for this design

Explicitly NOT in this spec:

- **Glassmorphism HUD background** — dropped 2026-05-06, stays dropped
- **Font swap / typography hierarchy** — dropped 2026-05-06, stays dropped
- **Animated text fade transitions** — dropped, replaced by world-anchored cube cloud
- **Hand-tracking pinch interactions** — v2 post-demo
- **Custom skin SSS shader / hair-card LOD shader** — v2 post-demo
- **Reflection probe baked at scene origin** — Tier 2 in 2026-05-06 brief, ship if time after Tier 1
- **Multi-seed TRELLIS lottery** — server-side, separate brick

---

## EOW timeline slot

| Day | Block | Deliverables |
|---|---|---|
| Fri 2026-05-08 (today, ~5hr remaining after planning) | Foundations | Steps 1-3 (CubeCloudManager + lerp + vortex) + start of Step 4 |
| Sat 2026-05-09 (full day) | Climax + polish | Steps 4-8 (silhouette + snap shader + orchestrator + audio/haptics + polish) |
| Sun 2026-05-10 | Demo capture | MP4 record |

**Priority interrupt rule:** Vipin lands paid Meshy creds → drop everything, run `tests/scripts/test_meshy_manual.py` against real key, validate end-to-end Meshy integration. Resume spawn ritual work afterward.

**Cuts if time runs out (in order of cut priority):**
1. Drop Step 8 polish entirely (no color drift, no energy-pathway lines, no breath, no gaze). Static white cubes + snap-to-mesh + idle animation. Demo with Steps 1-7 — still meaningfully premium vs current pop-in.
2. Reduce cube count 300 → 150. Visual is less dense but still reads as assembly.
3. Drop energy-pathway lines, keep Phase 4 silent + still (anticipation through pure stillness).

---

## How this slots into the existing Unity codebase

- **TestGlbLoader.cs** — currently spawns rigged GLB instantly. Becomes the consumer of `SpawnRitualController.OnSpawnComplete(GameObject avatar)`. The Loader stays responsible for download + glTFast instantiate; the Controller runs the ritual.
- **ScanController.cs** — existing A/X handler. Triggers `SpawnRitualController.BeginRitual(spawnLocation)` on capture (P1).
- **`/generate/{task_id}/status` poll** — existing client poll, but the Controller reads from it. Backend change: status field needs new values (`portraitizing | generating | rigging | animating | complete`). ~30min server-side change in `app/routes/generation.py` + matching schema in `app/models/generation_schemas.py`.
- **HUD canvas** — stays for status text + debug only. Stops being the primary visual; cube cloud is.
- **New Unity assets:**
  - `Assets/HoloBorn/Models/silhouette_placeholder.fbx`
  - `Assets/HoloBorn/Materials/Cube_WhiteCyan.mat` (URP/Lit, white base + cyan emission)
  - `Assets/HoloBorn/Shaders/CubeSnapDissolve.shadergraph`
  - `Assets/HoloBorn/Prefabs/CubePrimitive.prefab`
  - `Assets/HoloBorn/Audio/spawn_ritual/*.wav` (lock_flash, thrum_loop_short, click_lock, structural_lock, whoosh, breath_chime)

---

## Implementation principle

**Build bottom-up, test in Editor as much as possible.** Steps 1-4 can be developed entirely in Unity Editor with placeholder mesh — no Quest cycle needed. Step 5 onwards requires Quest tests. Each Quest test cycle is ~5-10min on Intel Mac, so minimize them: validate per-step behavior in Editor first.

The user has weak VR visualization (their words). Building incrementally lets them watch each layer come alive in Editor and provide feedback as the system grows. The opposite (top-down "wire all 8 steps then test") would land us at hour 11 with a broken integration and no idea what failed.

---

## Cross-AI review feedback resolution

Both ChatGPT and Gemini reviewed v1 of this spec. Their convergent points became locked changes (above). Their divergent point (cyan vs purple/amber) was resolved in favor of cyan with the 90/10 white-accent ratio, because:

- HoloBorn's core fantasy is **scan + reconstruct**, not magic or luxury
- Cyan is the universal scan-language across Westworld, Vision Pro, Apple LiDAR
- ChatGPT's "default URP emissive" critique is real but the fix is execution discipline (90/10 ratio, single accent), not switching color
- A purple/amber A/B test can happen in v3 polish if Saturday afternoon allows

**Tracked alternatives if Saturday late polish allows:**
- Test amber accent variant on the same cube material (~30min A/B)
- Try cubes-emerge-from-floor vs cubes-form-mid-air-around-circle as alternate motion start

---

## Approval gate

Spec is **locked**. Next step: invoke `writing-plans` skill to convert this spec into a step-by-step implementation plan that maps each of the 8 steps to a discrete commit-able unit of work with file paths, verification commands, and rollback triggers.
