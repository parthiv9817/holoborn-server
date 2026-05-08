# HoloBorn Spawn Ritual & World-Anchored Progress — Design Spec

**Author:** Parthiv (with Claude Code)
**Date:** 2026-05-08
**Status:** Draft v1 — pending second-opinion review (ChatGPT + Gemini), then user re-approval, then implementation
**Target ship:** Today (2026-05-08) + Saturday (2026-05-09). Sunday is demo capture day.

---

## TL;DR

The HoloBorn backend takes 7-10 minutes to produce a rigged avatar (portraitizer + RunPod TRELLIS + Meshy rigging + Meshy animation). A 2D progress bar — Gemini's first instinct on 2026-05-07 — fails in VR for two reasons:

1. The user has the entire room available; flat HUD elements feel "trapped on glass" instead of present in the space.
2. They will literally stand and stare for 7-10 minutes. Static placeholders feel like the system is broken.

**Solution:** a continuous cube-cloud assembly visible at the eventual spawn location, growing and changing across all backend phases, climaxing in a 2.5-second snap-to-mesh ritual when the rigged GLB arrives. Replaces:

- The "3D-print vertical clip shader" from the 2026-05-06 cross-AI brief (same time budget, more visceral)
- A flat 2D progress bar on the HUD (Gemini's first instinct — escalated past)
- Standalone spawn ritual + standalone progress viz + standalone audio + haptics (collapsed into one coherent system)

This single feature absorbs four locked Tier 1 items (#3 spawn ritual, #5 spatial audio, #6 haptics, #7 world-anchored progress) into one coherent visual+audio+haptic system.

---

## Why this replaces multiple Tier 1 items

| Tier 1 item from 2026-05-06 brief | How this design handles it |
|---|---|
| #3 Spawn ritual (3D-print vertical clip) | Phase 6 — cubes snap to mesh, mesh fades in, eyes glow |
| #5 Spatial audio cues | Audio bound to phase transitions: thrum (P2), chime per bone (P4), whoosh + chime + idle ambient (P6) |
| #6 Haptic feedback | Lock haptic on capture (P1), pulse on spawn climax (P6) |
| #7 World-anchored progress visualization | The cube cloud IS the progress indicator — phases 2-5 all map to backend status |

Items kept separate (still on the locked plan, not absorbed by this):
- #1 Procedural LateUpdate idle layer (breathing, sway) — runs after spawn
- #2 Gaze attention (head look-at user) — runs after spawn
- #4 Blob shadow + grounding glow — under the avatar at all times
- #8 Multi-seed TRELLIS lottery — server-side, unrelated

---

## Aesthetic references (videos to watch for visual vocabulary)

The user has limited VR exposure and asked for concrete references they can visualize. Recommended viewing in order of relevance:

1. **Westworld host construction scenes** (HBO, S01) — literal "person being assembled in real time in front of you with mechanical assembly." THE primary reference for HoloBorn.
2. **Avengers: Endgame — Iron Man Bleeding Edge nanotech** — particle/cube assembly into coherent shape, the snap-to-position aesthetic
3. **Apple Vision Pro launch video** (apple.com/vision-pro) — what "premium VR UI" looks like as a baseline (clean, depth-layered, controlled motion, monochrome accent)
4. **Iron Man 2 / 3 — Jarvis hologram lab scenes** — translucent geometric panels, layered holograms in 3D space, cyan/orange accents
5. **Detroit: Become Human — Kamski reveals** — minimal cyan/white holograms forming from particle systems
6. **Ra.One / Transformers (Age of Extinction Galvatron build)** — programmable-matter cube assembly, the "alien is arriving" energy

Shared aesthetic language across all six: **room-anchored** (not floating-HUD-anchored), **depth-layered**, **controlled motion** (not chaotic), **monochrome accent** (we're going cyan), **spatial audio** that comes FROM the holograms.

---

## Storyboard (6 phases, all with active visual content)

```
PHASE 1 — Capture (instant, ~0.5s)
  • Particle burst from where you stood (cyan, ~50 particles, 0.5s lifetime)
  • Cyan floor circle pulses at spawn location 1.5m in front of user
    (small marker, NOT a humanoid placeholder — staring at empty wireframe was the v1 mistake)
  • Soft "lock" sound + haptic pulse on left controller
  • Backend: POST /generate-multiview → returns task_id

PHASE 2 — Portraitizer (~30-60s)
  • Cubes start raining down from above into a SLOW VORTEX above the floor circle
  • Vortex is column-shaped, ~50-100 cubes orbiting slowly, tinted cyan
  • Cube arrival rate: 5-10/sec
  • Soft thrumming spatial audio loop, floor circle pulses synced to thrum
  • Active motion every second — never static
  • Backend: poll /generate/{task_id}/status, status="portraitizing"

PHASE 3 — RunPod TRELLIS (~3-5 min, the long one)
  • Vortex compresses; cubes start finding humanoid-silhouette positions
  • Cube arrival rate increases to 20-30/sec
  • Cubes "snap and stay" along the silhouette surface (sampled from final mesh verts)
  • RunPod % directly maps to silhouette completeness (0% = empty silhouette;
    100% = full humanoid silhouette of ~300 stationary cubes)
  • Color drifts cooler (cyan → ice-cyan) as % climbs
  • Backend: poll /generate/{task_id}/status, status="generating", progress=0..100

PHASE 4 — Meshy rigging (~30-60s)
  • Cube cloud is humanoid-shaped at this point
  • Bone-glyphs fade in INSIDE the cloud (skeletal preview visible through gaps)
  • Cloud pulses in waves — feels like the cloud is "thinking"
  • Soft chime per bone appearing (subtle, ~14 chimes total)
  • Backend: poll /generate/{task_id}/status, status="rigging"

PHASE 5 — Meshy animating (~30-60s)
  • Cubes "wake up" — subtle motion mimicking the upcoming idle animation
  • Cloud rehearses the animation faintly (low-amplitude preview)
  • Builds anticipation for spawn climax
  • Backend: poll /generate/{task_id}/status, status="animating"

PHASE 6 — Spawn ritual (the 2.5s climax)
  • Cubes flow inward, snap to actual mesh vertex positions (vertex displacement shader)
  • PBR avatar mesh fades in underneath as cubes land (alpha 0→1 over 1.5s)
  • Settled cubes dissolve into emissive sparkles → vanish
  • Avatar's eyes briefly glow cyan (0.5s pulse), settle
  • Idle animation begins
  • Spatial whoosh (during cube flow) + soft chime (at eye-glow) + haptic pulse on controller
  • Backend: status="complete", glb_url ready for spawn
```

---

## Implementation order (foundations first)

Build foundations before composition. Each step has a clear "done" criterion and can be tested in Editor (no Quest cycle) for the first 5 steps.

### Step 1 — Cube primitive + spawning system (~1.5hr)

- Create low-poly cube prefab (12 tris, single-color cyan unlit material with emission)
- `CubeCloudSystem.cs` — pool-based spawner. `Spawn(Vector3 origin)` → returns Cube instance. `Despawn(Cube)` → returns to pool.
- Pool size: 400 (300 active peak + 100 buffer)
- **Done when:** can spawn 300 cubes in Editor at user-defined origin and verify perf in Profiler stays >72 fps.

### Step 2 — Cube target-position behavior (~1hr)

- `Cube.cs` exposes `SetTarget(Vector3 worldPos, float duration)`. Cube lerps from current position to target over `duration` seconds with ease-out curve.
- `SetTarget(null)` → idle behavior (caller's responsibility to set next target).
- **Done when:** spawn 100 cubes at random points within 2m sphere, call `SetTarget(humanoidVert)` on each with random vert from a test mesh; cubes converge to silhouette in 2s.

### Step 3 — Vortex behavior (~30min)

- `VortexBehavior.cs` — given center+axis+radius+height, computes orbit position around vertical axis. Updates target each frame.
- For Phase 2: cubes orbit slowly (1 rev / 4s), light vertical drift.
- **Done when:** 50 cubes spawned, vortex behavior runs, cubes orbit smoothly without jitter or popping.

### Step 4 — Silhouette-sampling behavior (~1.5hr)

- `SilhouetteBehavior.cs` — given a target mesh + coverage % (0-1), assigns each cube a target position sampled from random verts on the mesh. Coverage = fraction of cubes that have a target (rest stay in vortex).
- **Done when:** load TRELLIS GLB into test scene, call `SetCoverage(0.5)`, verify 50% of cubes are at silhouette positions and 50% still in vortex.

### Step 5 — Snap-to-mesh + dissolve shader (~3hr)

- Vertex displacement shader: a cube's quad verts lerp from "cloud position" to "mesh vertex position" over 2.5s.
- After snap: alpha fade 1→0 over 1s, with emissive boost (sparkle effect).
- **Done when:** 300 cubes positioned along silhouette, trigger snap, verify all cubes converge to mesh verts and dissolve cleanly with no visible pop.

### Step 6 — Phase orchestrator (~1.5hr)

- `SpawnRitualController.cs` — listens to backend status (existing `/generate/{task_id}/status` poll), drives phase transitions.
- State machine: P1 → P2 → P3 → P4 → P5 → P6 → IDLE.
- Each phase configures the cube cloud's behavior + audio + haptics.
- **Done when:** simulate fake status updates ("portraitizing" → "generating" with progress → "rigging" → ...), verify all 6 phases visually transition correctly in Editor.

### Step 7 — Audio + haptics layer (~1hr)

- `SpawnRitualAudio.cs` — Unity AudioSource at world point above floor circle, spatial blend = 1.0
  - P2: looping thrum
  - P4: chime-per-bone (one-shot)
  - P6: whoosh + final chime
- Haptics via `OVRInput.SetControllerVibration(amplitude, frequency, controller)`:
  - P1: short pulse on left controller (capture lock)
  - P6: pulse on left controller at eye-glow

### Step 8 — Polish pass (~1hr)

- Color drift across phases (cyan → ice-cyan)
- Bone glyph rendering inside cube cloud (Phase 4)
- Eye glow on final avatar (Phase 6) — emissive material on eye sub-mesh, pulse via animation curve
- Cube dissolve sparkle particle (Phase 6)

**Total: ~11 hours.** Today (4-5hr) covers steps 1-4 + start of 5. Saturday morning covers steps 5-8.

---

## Quest 3 performance budget

| Element | Count | Tris | Notes |
|---|---|---|---|
| Cubes (peak, Phase 3-5) | 300 | 12 each = 3,600 total | Low-poly cubes, single material |
| Avatar mesh (final) | 1 | ~30,000 (Meshy decimation) | Already validated 2026-05-07 |
| Floor circle | 1 | ~32 | Quad with circular alpha cutoff |
| Particle bursts | 50 max | n/a | Unity built-in particles, GPU |

**Frame target:** stays >72 fps in Quest Profiler during all 6 phases. Hard floor: never drops below 60 fps even at Phase 6 climax (300 cubes animating + mesh fading in + particles + audio + haptics simultaneously).

**Fallback ladder if perf is tight:**
- Reduce cube count to 200 → 150 → 100. (Below 100, cube cloud reads as "particles" not "assembly," loses the cube aesthetic.)
- Drop bone glyphs in Phase 4
- Drop color drift, lock to single cyan

If 100 cubes still tank perf, switch to Unity VFX Graph (GPU-driven) instead of GameObject pool. VFX Graph can handle 10,000+ particles trivially but loses the per-cube control we need for snap-to-mesh. Last resort.

---

## Acceptance criteria (objective, not subjective)

To prevent the 2026-05-07 mistake #1 pattern (Claude misreading Quest screenshots and calling things "great" when they had visible artifacts), each phase has objective pass criteria. These are **measured**, not judged from a screenshot.

| Phase | Pass criteria |
|---|---|
| P1 | Particle burst spawned at user's last position; floor circle visible at 1.5m forward; haptic fired (verify via OVRInput debug); audio fired (verify via AudioSource.isPlaying log) |
| P2 | Cube count grows from 0 to 50-100 over 30s; Profiler shows steady >72 fps; thrum audio looping (verify via Audio Mixer) |
| P3 | At backend progress=50%, exactly 50% of cubes are in silhouette positions (via instrumented log); at 100%, all cubes are stationary on silhouette; FPS holds |
| P4 | Bone glyph count matches actual rig bone count from Meshy GLB (typically 14); chime fired per glyph (verify via log) |
| P5 | At least one preview-motion animation cycle plays (verify via animation curve sample); cube positions oscillate within ±2cm of silhouette |
| P6 | All 300 cubes converge to mesh vert positions in 2.5s ±0.1s; mesh alpha goes 0→1; cubes alpha goes 1→0; avatar eye emissive pulses; total spawn frame budget <40ms |

**Subjective visual reads (Claude's job, NOT to assert):**
- "Does it FEEL premium?" — user-only call
- "Does the color look right?" — user-only call
- "Is the timing right?" — user-only call

When user reports something looks off, defer to their empirical observation. Claude's value is narrowing the bug-search-space via logs/code/architecture, not subjective screenshot interpretation.

---

## Open questions for second-opinion review (ChatGPT + Gemini)

The following are explicitly open and should be stress-tested by external review:

1. **Aesthetic on-trend or cliche?** Is the "cube assembly" visual language overused in 2025-2026 era VR/MR demos? Are there specific products that already shipped this exact effect? Risk of looking derivative.
2. **Phase 4-5 weakest links.** The "cube cloud thinks" + "cube cloud rehearses" beats feel weakest in our v1. Better treatments?
3. **Quest 3 perf gotchas.** 300 GameObject cubes vs Unity VFX Graph — any concrete reasons to start with one over the other? URP-specific issues we'd hit?
4. **Color choice — is cyan the right call?** Cyan is the obvious pick (matches Apple Vision Pro / Detroit / Iron Man references) but might feel default. Alternatives: warm orange (Halo Forerunner), white-only with no color (more clinical/Apple), green (Matrix/digital). User has weak visualization here so we want options to choose from.
5. **Where do cubes come from?** Currently they "rain from above." Alternatives: emerge from the floor, materialize at random points around the user, flow from where the user stood at capture, flow from a fixed "source point" in the room (like a beacon). Affects spatial storytelling.
6. **Capture moment particle burst — appropriate or noisy?** P1 particle burst from user might fight with the cube assembly downstream. Should it be a single bright "lock" flash instead?
7. **What does the avatar look like during Phase 5 cube wake?** If cubes "rehearse" the animation, are they doing whole-cloud motion or cube-position offsets? Whole-cloud might read as "cloud is bouncing," cube-position offsets might read as "noise." Open.
8. **Eye-glow at spawn — natural or cheesy?** Eye-glow is a gold-standard "alien arriving" beat (every robot intro since the 80s) but might read as cheesy in 2026. Alternative beats: brief breath-in animation, slight head turn toward user, hand unclench.
9. **Spatial audio mix.** P2 thrum loop running for 3-5 minutes during TRELLIS — does that grate or feel ambient? Audio fade-in/out per phase, or continuous?
10. **Anything we're missing entirely?** Open prompt for blind spots — gaze, lighting integration, room scanning UX, anything else.

---

## Out of scope for this design

Explicitly NOT in this spec:

- **Glassmorphism HUD background** — dropped by 2026-05-06 cross-AI review, stays dropped
- **Font swap / typography hierarchy** — dropped by 2026-05-06 cross-AI review, stays dropped
- **Animated text fade transitions** — dropped, replaced by world-anchored cube cloud
- **Hand-tracking pinch interactions** — v2 post-demo
- **Custom skin SSS shader** — v2 post-demo
- **Hair-card LOD shader** — v2 post-demo
- **Reflection probe baked at scene origin** — Tier 2 in 2026-05-06 brief, ship if time after Tier 1 lands
- **Multi-seed TRELLIS lottery** — server-side, separate brick

---

## EOW timeline slot

| Day | Block | This design's deliverables |
|---|---|---|
| Fri 2026-05-08 (today, ~5hr remaining) | Foundations | Steps 1-4 (cube system + vortex + silhouette behavior) |
| Sat 2026-05-09 (full day) | Climax + polish | Steps 5-8 (snap shader + orchestrator + audio/haptics + polish) |
| Sun 2026-05-10 | Demo capture | MP4 record |

**Priority interrupt:** Vipin's Meshy paid-plan approval lands → drop everything, run `tests/scripts/test_meshy_manual.py` against real key, validate end-to-end Meshy integration. Resume spawn-ritual work afterward.

**Cuts if time runs out:**
- Drop Steps 7-8 polish (audio/haptics + color drift / bone glyphs / eye glow). Demo with Steps 1-6 only — still demo-ready.
- Drop Phase 5 entirely (skip animating preview, cut from P4 directly to P6). Saves ~30min implementation.
- Reduce cube count from 300 to 150. Visual is less dense but still reads as assembly.

---

## How this slots into the existing Unity codebase

- **TestGlbLoader.cs** (~yesterday's working code) — currently spawns the rigged GLB instantly. Becomes the consumer of `SpawnRitualController.OnSpawnComplete(GameObject avatar)`. The Loader stays responsible for download + glTFast instantiate; the Controller runs the visual ritual on top.
- **ScanController.cs** — the existing A/X button handler. Triggers `SpawnRitualController.BeginRitual(spawnLocation)` on capture (P1).
- **Existing `/generate/{task_id}/status` poll** — currently client polls every 3s, gets `status + progress + glb_url`. The Controller reads from this same poll. **Backend change required:** status field needs to support new values: `portraitizing | generating | rigging | animating | complete`. Currently only `processing | complete | failed`. ~30min server-side change in `app/routes/generation.py` and the corresponding schema.
- **HUD canvas** — stays for status-line readout only. Stops being the primary visual; the cube cloud is.

---

## Implementation principle

**Build bottom-up.** Step 1 (cube spawn) before Step 6 (orchestrator). Test each step in Editor before assembling. The user's brain has weak VR visualization; building incrementally lets them watch each layer come alive in Editor and provide feedback as the system grows. The opposite (top-down "wire all 8 steps then test") would land them in Quest at hour 11 with no idea what they're seeing — high risk of "Claude says it works, user can't tell" failure mode.

---

## Approval gate

After this spec is reviewed by Gemini + ChatGPT and feedback integrated:

1. User re-approves the updated spec
2. Hand off to writing-plans skill to convert this spec into a step-by-step implementation plan
3. Begin Step 1 in code

No code is written before that gate.
