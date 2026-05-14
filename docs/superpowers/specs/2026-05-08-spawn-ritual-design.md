# HoloBorn Spawn Ritual & World-Anchored Progress — Design Spec v3

**Author:** Parthiv (with Claude Code)
**Date:** 2026-05-08 (v3 amended end-of-day)
**Status:** v3 — simplified architecture per Parthiv's end-of-day refinement. Locked for Saturday implementation.
**Target ship:** Saturday 2026-05-09 + Sunday 2026-05-10 (demo capture).

---

## v3 changes from v2 (Parthiv's end-of-day simplification)

| v2 → v3 change | Why |
|---|---|
| **5 phases collapsed to 4** | Phase 4 "internal activation" (cube cloud holds + energy pathways during Meshy rigging) was the weakest beat, both AIs flagged it as soft. Removed entirely. |
| **Snap-to-mesh shader DELETED** | The 2.5-second cube-flow-onto-mesh-vertex climax replaced with simpler "cubes coordinated dissolve + static GLB materializes underneath" transition. Saves ~3 hours of Shader Graph + visual-debug work. Eliminates the highest-risk visual phase. |
| **Re-sample cubes from real GLB at climax DELETED** | No longer needed — cubes don't snap to the real mesh, they vanish before the mesh appears. Saves orchestrator complexity. |
| **Phase 5 "Spawn climax" → Phase 4 "Animation kickoff"** | When Meshy returns the rigged GLB, the static mesh is *replaced* by the rigged version, idle clip starts, subtle breath + gaze acquisition. Crisper transition than v2's snap-fade-dissolve sequence. |
| **NEW: cyan grounding glow during rigging period** | Subtle floor-circle pulse under the static avatar while Meshy works (~30-60s). Signals "system is still working" without requiring complex visuals. Doubles as the blob-shadow grounding the locked plan already had. |
| **Backend exposes 2 GLB URLs at different phases** | `/avatars/{id}_static.glb` available when status = `rigging` (TRELLIS output, no rig); `/avatars/{id}.glb` available when status = `complete` (Meshy rigged + animated). Quest fetches whichever is current. ~30 min server-side change. |

**Why Parthiv proposed this and why it's actually better:**

The v2 design was technically correct but had two soft beats (Phase 4 internal activation, Phase 5 cube-snap climax) where neither ChatGPT nor Gemini had a strong recommendation for what to do. Both AIs' feedback essentially admitted "this part is weak but try this anyway." Parthiv's instinct: when a design has weak beats, the answer is usually to remove them, not polish them.

The v3 simplification trades the "matter snaps onto avatar shape" climax for "cubes vanish + finished avatar appears" — slightly less integrated cinematically, but: (1) cleaner narrative beats (3 visible moments instead of 5), (2) ships faster (eliminates ~3hr of Phase H shader work), (3) lower risk (the snap-to-mesh shader was the highest-likelihood visual failure mode), (4) easier to debug at Quest test time.

This applies the lesson from `mistakes/2026-05-08.md` — when a design has a "Phase X is the weakest beat" comment in it, that's signal that Phase X shouldn't exist, not that it needs more polish.

---

## TL;DR

The HoloBorn backend takes 7-10 minutes to produce a rigged, animated avatar. A 2D progress bar fails in VR for two reasons: the user has the entire room available, and they will literally stand and stare for that whole duration.

**Solution:** a cube-cloud that assembles a humanoid silhouette in the spawn location during the long-duration phases (portraitizer + TRELLIS, ~4-6 min), then dissolves to reveal the static avatar mesh when TRELLIS completes. The static avatar stands with a subtle cyan grounding glow while Meshy rigs (~30-60s). When rigging completes, the static mesh is replaced by the rigged+animated GLB and the avatar comes to life with a subtle breath + gaze acquisition + idle clip.

The waiting time becomes emotional theater: the user watches the avatar materialize in three crisp visual beats — **assembly → form → life.**

This single feature absorbs locked Tier 1 items #3 (spawn ritual), #5 (spatial audio), #6 (haptics), #7 (world-anchored progress) into one coherent system.

---

## Aesthetic references

Watch in this order (foggy-friendly priority):

1. **Westworld host construction scenes** (HBO S1) — primary reference, "person being assembled in real time"
2. **Avengers: Endgame Iron Man Bleeding Edge nanotech** — particle/cube assembly, snap-to-position discipline
3. **Apple Vision Pro launch video** — premium VR baseline, 90% white / 10% cyan accent
4. **Iron Man 2/3 Jarvis hologram lab** — translucent geometric layered holograms
5. **Detroit: Become Human Kamski reveals** — minimal cyan/white particle systems
6. **Ra.One / Transformers Galvatron build** — programmable matter aesthetic

Shared language: **room-anchored, depth-layered, controlled motion, monochrome accent at 10%, spatial audio coming FROM the holograms.** Cubes move like a machine with intelligence, not magic particles.

---

## Storyboard — 4 phases (down from 5)

```
PHASE 1 — Capture (instant, ~0.3s)
  • Floor circle ignites with bright "lock" flash (1 frame, white)
  • Camera-shutter audio cue (single shot, spatial)
  • Haptic pulse on left controller
  • NO user-side particle burst (the cubes are the show)
  • Backend: POST /generate-multiview → returns task_id

PHASE 2 — Cube assembly (~4-6 min spans portraitizer + TRELLIS)
  Sub-phase 2a (during portraitizer, ~30-60s):
    • Cubes emerge UPWARD from floor circle into a slow vertical column
    • ~50-100 cubes orbiting slowly, white-with-cyan-accent
    • Cube arrival rate: 5-10/sec, soft thrum fades in/out
    • Floor circle pulses faintly, synced to thrum

  Sub-phase 2b (during TRELLIS, ~3-5 min):
    • Vertical column compresses; cubes start finding humanoid-silhouette positions
    • Target positions sampled from generic humanoid placeholder mesh (Y Bot)
    • Cube arrival rate increases to 20-30/sec
    • Cubes "snap and stay" along the silhouette surface
    • RunPod % directly maps to silhouette completeness (0% empty → 100% full)
    • Color drift cooler as % climbs (white-to-ice-cyan accent intensifies)
    • Audio: event-driven "click" on every Nth cube locking, NO continuous loop
    • Motion progression: chaotic early → organized streams mid → locked silhouette late

PHASE 3 — Static avatar materializes (transition, ~1.5s; then holds during Meshy)
  Transition (when TRELLIS completes, ~1.5s):
    • Cubes do a coordinated inward-implosion + dissolve into emissive sparkles → vanish
    • Static avatar mesh fades in over the same 1.5s window (alpha 0→1)
    • Spatial whoosh audio + haptic pulse on left controller
    • Backend exposes /avatars/{id}_static.glb at status = "rigging"

  Hold (during Meshy rigging+animating, ~30-60s):
    • Static avatar stands motionless at spawn location
    • Subtle cyan grounding glow under feet (slow pulse, ~2s cycle)
    • Faint emissive cyan tint on avatar surface (very subtle, signals "still processing")
    • Audio: silent or very low ambient texture
    • Visual story: "the form exists, now waking up"

PHASE 4 — Animation kickoff (when Meshy completes, ~1s climax)
  • Static avatar replaced by the rigged+animated GLB (Quest fetches /avatars/{id}.glb)
  • Cyan grounding glow fades to zero over 0.5s
  • Avatar's surface emissive tint fades to zero (the "wake up" cue)
  • Subtle breath animation as first idle keyframe (chest expand, shoulders settle)
  • Head turns slightly toward user (gaze acquisition, 0.5s eased rotation)
  • Idle animation begins (Meshy's baked Idle clip, AnimationMethod.Legacy)
  • Audio: soft chime at the breath moment, ambient idle layer fades in
  • Haptic pulse on left controller at the breath moment
  • NO eye-glow (killed in v2, stays killed)
```

The 4 narrative beats:
1. **"The work happens HERE"** (Phase 1 — floor circle ignites)
2. **"Matter assembles into shape"** (Phase 2 — cubes form humanoid silhouette)
3. **"Form materializes"** (Phase 3 transition — cubes vanish, avatar appears)
4. **"Life begins"** (Phase 4 — breath, gaze, idle starts)

---

## Implementation order — Saturday plan (~5-6 hours, was ~12 hours in v2)

| Step | What it builds | Estimated |
|---|---|---|
| 1 — Backend GLB-URL split | `app/services/generation_pipeline.py`: save TRELLIS output to `_static.glb`, save Meshy output to plain `.glb`. `app/routes/generation.py`: status endpoint returns `_static.glb` URL during `rigging`/`animating`, returns plain `.glb` URL at `complete`. ~30 min server-side change. | 30 min |
| 2 — Phase orchestrator scene wiring | SpawnRitualController + state machine + per-phase entry behaviors (P1 capture / P2 cube assembly / P3 static-mesh transition / P4 animation kickoff). Listens to `/generate/{task_id}/status`, drives transitions. | 1.5 hr |
| 3 — Cube dissolve transition (Phase 3 entry) | When backend status flips to `rigging`, cubes get a coordinated implosion target + alpha fade + emissive sparkle on despawn. ~30 lines + particle effect. NO snap shader needed. | 45 min |
| 4 — Static avatar with cyan glow during rigging | Add a small Quad floor-circle child to the static avatar prefab + emissive shader with animated alpha. Plus material-level emissive tint controller on the avatar's renderers. | 45 min |
| 5 — Static→rigged GLB swap (Phase 4 entry) | When status = `complete`, fetch new GLB, replace static one in scene, fade out the grounding glow + emissive tint. | 30 min |
| 6 — Breath + gaze on idle start | Procedural head-look-at-user (0.5s eased) + emit-first-idle-keyframe trigger. Added to the same component that handles Phase 4 entry. | 45 min |
| 7 — Audio + haptics (sparse, event-driven) | SpawnRitualAudio.cs hooked to phase transitions. P1 lock + shutter, P2 cube clicks (event-driven), P3 whoosh + haptic, P4 breath chime + haptic. | 1 hr |
| 8 — Quest sideload + integration test | Build APK, sideload, capture-to-spawn end-to-end run. First time the full ritual runs on device. Profiler check: stays >72 fps. | 1 hr |

**Total: ~6 hours.** Was ~12 hours in v2. Eliminated: snap-to-mesh shader (Phase H), Phase 4 internal activation visuals, energy-pathway lines, cube-resampling-from-real-GLB at climax.

**Sunday:** demo MP4 capture. No new code.

---

## What carries over from v2 (still applies in v3)

These were locked in v2 and remain unchanged:

- **`Cube.cs` POCO with EaseOutCubic + SetTarget + Tick** (already shipped, 5 tests green)
- **`CubeCloudManager.cs` pool with single Update loop** (already shipped, 6 tests green)
- **`VortexBehavior.cs` orbit math** (already shipped, 7 tests green)
- **`SilhouetteBehavior.cs` Fisher-Yates vertex sampling** (already shipped, 6 tests green)
- **Generic humanoid placeholder mesh** (`Assets/HoloBorn/Models/silhouette_placeholder.fbx`, Mixamo Y Bot, ~6.7K verts) — vertex-source for Phase 2b silhouette positions only. Still NEVER rendered to screen.
- **300 cubes default** (tunable via `poolSize` field, Parthiv flagged this likely needs UP-bump to 1000-2000 once we see Phase 2b density on Quest)
- **CubeCloudManager's no-per-cube-Update perf rule** (validated Friday on Quest, 60 FPS sustained)
- **Color discipline:** 90% white / 10% cyan accent (Vision Pro restraint, not cyberpunk)
- **Audio sparse + event-driven** (no continuous 5-min loops)

---

## Quest 3 performance budget

| Element | Count | Tris | Notes |
|---|---|---|---|
| Cubes (peak Phase 2) | 300-1000 (tune up if sparse) | 12 each | Validated at 300 = 60 FPS in Editor; bump to 1000 likely fine on Quest 3 |
| Avatar mesh (Phase 3+) | 1 | ~30K (Meshy decimation) | Validated 2026-05-07 |
| Floor circle / grounding glow | 1 | ~32 | Quad with circular alpha cutoff + animated emission |
| Particle dissolve burst (Phase 3 entry) | ~5 per cube × N cubes | n/a | GPU-driven Unity built-in particles, short lifetime |

**Frame target:** stays >72 FPS during all phases. Hard floor: never below 60 FPS even at Phase 2b peak (300+ cubes animating + URP + passthrough).

**Fallback ladder if perf is tight:**
1. Reduce cube count: 1000 → 500 → 300 → 200
2. Drop the cube-locking click events (audio-only, no haptics)
3. Drop the cyan emissive tint on static avatar during rigging (just floor glow)

---

## Acceptance criteria (objective, not subjective)

| Phase | Pass criteria |
|---|---|
| P1 | Floor circle bright-flash for ≤1 frame; haptic fired (verified via OVRInput log); shutter audio fired (verified via AudioSource log) |
| P2a | Cube count grows 0 → 50-100 over 30s; thrum fades in/out cleanly (audio mixer dB tracking); Profiler steady >72 FPS |
| P2b | At backend `progress=50%`, exactly 50% of cubes are in silhouette positions (instrumented log); at 100%, all cubes stationary on silhouette; "click" events fired ~30-50 total (verified via log) |
| P3 transition | Cubes converge inward + dissolve over 1.5s ±0.1s (instrumented timing); static avatar alpha goes 0→1 in same window; whoosh audio + haptic fire at transition start |
| P3 hold | Cyan grounding glow visible + pulsing; cube count = 0 (despawn complete); avatar stands motionless |
| P4 | Static GLB swap to rigged GLB happens cleanly (Quest fetches new URL within 1s); cyan glow fades to 0; breath animation plays for ≥0.3s; gaze rotation acquires camera target ±5° in 0.5s; idle clip starts |

**Subjective visual reads (Claude's job NOT to assert):**
- "Does it FEEL premium?" — user-only call
- "Does the timing feel right?" — user-only call
- "Are 300 cubes enough?" — user-only call (decided empirically when Phase 2b fires for the first time)

---

## Out of scope for v3 (explicit)

- Snap-to-mesh vertex displacement shader (DELETED in v3)
- Phase 4 internal activation / energy-pathway lines (DELETED in v3 — Phase 4 collapsed)
- Cube re-sampling from real GLB mesh (no longer needed — cubes vanish before real mesh appears)
- Glassmorphism HUD background (dropped in v2, stays dropped)
- Font swap / typography hierarchy (dropped in v2, stays dropped)
- Hand-tracking pinch interactions (post-demo)
- Custom skin SSS shader / hair-card LOD shader (post-demo)
- Reflection probe baked at scene origin (post-demo or Sunday-AM polish if time)
- Multi-seed TRELLIS lottery (server-side, separate brick)

---

## Backend changes required (Saturday morning, ~30 min)

1. **`app/services/generation_pipeline.py`** — after RunPod completes and downloads GLB to local, save it as `{AVATARS_DIR}/{task_id}_static.glb`. Then send to Meshy. When Meshy completes, save final rigged GLB as `{AVATARS_DIR}/{task_id}.glb`.

2. **`app/routes/generation.py` `task_status` endpoint** — return different `glb_url` based on status:
   ```
   if status == "rigging" or status == "animating":
       glb_url = f"/avatars/{task_id}_static.glb"
   elif status == "complete":
       glb_url = f"/avatars/{task_id}.glb"
   else:
       glb_url = ""  # not yet available
   ```

3. **No Quest-side GLB-handling change required** — TestGlbLoader already fetches whatever URL is current. The orchestrator will trigger TestGlbLoader twice (once at P3 transition with static URL, once at P4 with rigged URL) and let the second load replace the first.

---

## EOW timeline

| Day | Block | Deliverables |
|---|---|---|
| **Saturday 2026-05-09** (full day, ~6 hr work) | All implementation | Backend GLB split + orchestrator wiring + cube dissolve + static-avatar-with-glow + GLB swap + breath/gaze + audio + Quest integration |
| **Sunday 2026-05-10** | Demo capture | MP4 record, retake until clean, founder send |

**Cuts ladder if Saturday slips:**
1. Drop breath + gaze (just trigger idle clip directly — still feels alive)
2. Drop cyan grounding glow during rigging (just static avatar standing — slightly less premium but works)
3. Drop the cube dissolve sparkle particles (cubes just deactivate cleanly — works but less refined)
4. Reduce cube count to 200 if Phase 2b feels visually-fine at lower density

---

## Cross-AI review feedback resolution (preserved from v2)

Both ChatGPT and Gemini reviewed v1. Convergent points became locked changes (in v2). Their divergent point (cyan vs purple/amber) was resolved in favor of cyan with the 90/10 white-accent ratio.

The v3 simplification did NOT go back to the AIs for re-review — Parthiv's call. Reasoning: the simplification is in the direction the AIs already pushed (drop the weak Phase 4, simplify the climax). It's a defensible refinement of their feedback, not a contradiction of it.

If Saturday morning we want to validate v3 once more, ~5 minutes to paste the v3 changes into ChatGPT/Gemini for a sanity check. Probably not needed, but it's an option.

---

## Approval gate

Spec is **locked at v3**. Saturday's first action is reading the diary + handoff + this spec, then starting Step 1 (backend GLB-URL split). No further design work; just execution.
