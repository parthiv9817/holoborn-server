# Origin Story UI — implementation plan (v2, 3-stage)

**Date:** 2026-05-11 (afternoon revision)
**Author:** Parthiv (with Claude Code)
**Status:** Plan, not yet executing
**Supersedes:** v1 of this file (4-stage plan with plastic hold + purification wave — both cut after Gemini concept art validated that stage 2→3 wouldn't read on Quest)
**Replaces:** `docs/superpowers/specs/2026-05-08-spawn-ritual-design.md` (v3 cube-cloud design)
**References:** `drafts/glb_stage_transitions_round5_brief.md` + `drafts/origin_story_ui_visualization_brief.md` + Round 5 cross-AI synthesis

---

## Mental model — Kuchiyose no Jutsu (3 acts)

The 10-minute wait is a summoning. Test every design decision against: *"does this feel like a summoning, or does this feel like a loading screen?"*

Three acts now, not four:
1. **Vessel forming** — anonymous ceremonial mannequin holds while the server does its work
2. **Form revealed** — scan-line passes, real you emerges (clean, accurate, recognizable)
3. **Contract binds** — gaze acquires, breath begins, familiar is alive

The TRELLIS plastic state is computed server-side but **never shown to the user**. We only ever display the BEST version of them. No uncanny plastic intermediate setting wrong expectations.

---

## What was cut in v2 (and why)

After Gemini generated concept art for stage 2→3 (the "purification wave"), the visual delta between TRELLIS-plastic and Meshy-clean was too subtle to carry its own beat. Even in deliberately stylized concept art, the cyan wave was the dominant element, not the surface change. Per cube-cloud lesson: don't build math for a beat that won't read.

**Cut from v1 of this plan:**
- Stage 2 (TRELLIS plastic hold) — entire visible stage removed
- Stage 2→3 transition (purification wave) — entire transition removed
- `MaterialPurificationLerp.shadergraph` — not needed
- Dual-GLB rendering at same transform — not needed
- ~3 implementation phases — eliminated

**What this saves:**
- ~30-40% less implementation work
- No z-fighting risk between two GLBs
- No "wave that doesn't reveal anything" failure mode
- Cleaner 3-act narrative

**What's deferred to v2 (not in this plan):**
- Audio (diegetic hum, transition stings, awakening breath)
- Polished biological micro-movements beyond the core 3 events
- Real-time reflection probe baking

---

## What we throw away from v3 cube design

```
Assets/HoloBorn/Scripts/SpawnRitual/CubeCloudManager.cs              — DELETE
Assets/HoloBorn/Scripts/SpawnRitual/CubeCloudPhaseDriver.cs          — DELETE
Assets/HoloBorn/Scripts/SpawnRitual/SilhouetteBehavior.cs            — DELETE
Assets/HoloBorn/Scripts/SpawnRitual/_DebugStatusSimulator.cs         — REFACTOR (new phase names)
Assets/HoloBorn/Models/silhouette_placeholder.fbx                    — REPURPOSED as Stage 1 mannequin mesh
Assets/HoloBorn/Prefabs/Cube.prefab                                  — DELETE
Scene: 2000-cube CubeCloud GameObject hierarchy                       — DELETE
```

What stays:
- `SpawnRitualStateMachine.cs` (refactor to 3 states + tests)
- `SpawnRitualController.cs` (refactor phase entry events)
- `ScanController.cs` (no change)
- `TestGlbLoader.cs` (refactor — loads up to 2 GLBs sequentially now, not 3)
- `AvatarSpawnPhaseDriver.cs` (refactor — drives final awakening)
- All backend code (minor modification — see Backend Changes section)

---

## The 3-stage design spec

### Stage 1 — Suspended Anatomical Mannequin
**Duration:** holds from capture trigger until Meshy retextured GLB available (~4-7 min total — TRELLIS + Meshy Retexture combined)

**Visual:**
- Y-Bot humanoid mesh (existing silhouette_placeholder.fbx, repurposed)
- Translucent matte off-white material:
  - Use stock URP Lit shader
  - Surface Type: Transparent, Blending Mode: Alpha
  - Base Map: off-white (#E8E8EA), Alpha 0.35
  - Emission: cyan (#00E0FF), intensity 1.5 — apply with stock URP Lit emission slot
  - Smoothness: 0.2 (matte), Metallic: 0.0
- Eyes closed (no facial detail on Y-Bot — absence reads as unconscious)
- Slow chest breathing animation (Animator, 0.5 breaths/sec amplitude ±3%)
- Continuous slow Y-axis rotation drift (<2 deg/sec, no easing, smooth continuous)
- Floating 3cm above floor (transform.y = anchor.y + 0.03)
- Grounding shadow: simple quad with circular gradient texture, parented to the avatar root, cyan-tinted, on the real floor below

**Anchor position:** 1.5m forward of capture position, eye-line height (1.6m)

**Why this stage exists longer now:** holds for TRELLIS + Meshy Retexture combined (~4-7 min). The mannequin needs to sustain attention WITHOUT getting boring. Mitigation: continuous slow rotation + breathing + slight ambient drift create perpetual subtle motion. Never frozen.

### Stage 1 → 2 transition — Vertical Scan + Glowing Boundary
**Duration:** 3-4 seconds total

**Trigger:** Meshy retextured GLB available from server (which means TRELLIS + Meshy Retexture both complete)

**Mechanism:**
1. Pre-load Meshy retextured GLB invisibly at exact mannequin transform
2. Apply shared `ScanClipShader.shadergraph` to BOTH mannequin and retextured GLB:
   - World-space Y position node
   - Step function against `_ScanY` uniform
   - Mannequin: clip frags where world.y > _ScanY (mannequin erodes upward)
   - Retextured GLB: clip frags where world.y < _ScanY (real mesh emerges upward)
3. Spawn a thin emissive cyan quad at world.y = _ScanY, scale matching avatar bounding radius — this is the visible scan line (NOT VFX Graph particles; simpler quad with emissive material)
4. Animate `_ScanY` from -0.1 (just below feet) to 1.95 (just above head) over 3.5s, ease-out cubic
5. On scan completion: destroy mannequin GameObject, reset retextured GLB material to standard, despawn scan line quad

**The crucial reading:** the eye tracks the emissive scan line moving upward. The topology change between mannequin and Meshy mesh is cognitively invisible because the binding event is the boundary itself.

**Simplification from v1:** no VFX Graph particle ribbon. Just one emissive quad. Premium feel preserved via clean emissive + ease curve. Less custom math, lower implementation risk.

### Stage 2 — Clean Avatar Hold
**Duration:** holds until rigged+animated GLB available (~1-2 min after stage 1→2 transition)

**Visual:**
- Meshy retextured GLB fully visible (clean PBR, matte skin, fabric reads as fabric)
- Subtle micro-rotation: ±1 degree on Y axis, 4-second period, sine wave (avoids feeling frozen)
- Grounding shadow continues (recomputed for new bounds)
- NO new effects — the user just looks at themselves, correctly

**Why this stage:** The dopamine moment. User sees the accurate version of themselves and absorbs the reveal. ~1-2 min holds attention naturally because users want to look at themselves.

### Stage 2 → 3 transition — Biological Awakening
**Duration:** 2-3 seconds

**Trigger:** Meshy rigged+animated GLB available

**Mechanism:**
1. Pre-load rigged-animated GLB invisibly at exact same transform
2. Material swap — keep clean GLB visible, swap to rigged GLB instantaneously (visually identical — same mesh, same texture, just adds skeleton+animator)
3. Wait 200ms (anticipation pause)
4. Trigger awakening sequence (timed Animator events):
   - t=0.2s: chest inhale (subtle breath, 0.4s, additive Animator layer amplitude ±5% spine scale)
   - t=0.6s: head micro-tilt (3 degrees, 0.2s)
   - t=1.0s: gaze acquisition — head + eyes look-at constraint engages, rotates toward Quest camera, eased 0.6s
   - t=1.6s: gaze held briefly
   - t=2.0s: idle animation begins (Meshy's `basic_animations.idle_glb_url` OR action_id=0)

**The critical beat:** gaze acquisition is THE emotional climax. "You summoned me, I see you, I am yours."

**No VFX effect.** Just life. ChatGPT council north star: humans are wired for breath + eye targeting; that beat lands harder than every particle effect combined.

### Stage 3 — Living Avatar
**Duration:** persistent

**Visual:**
- Idle animation looping
- Subtle gaze tracking — dampened LookAt constraint following Quest camera, ±15 degree max
- Occasional micro-movements: weight shift every 8-12s, eye blink every 4-7s, slight head turn every 15-20s
- Grounding shadow continues

---

## Implementation phases (TDD-organized, sequential)

### Phase A — Scene cleanup + state machine refactor
**Goal:** remove cube-cloud, refactor state machine to 3-state model

**Tasks:**
1. **A.1** — Update `SpawnRitualStateMachine.cs` state enum: `Idle`, `ShellManifest`, `Revealed`, `Awakened`
2. **A.2** — Update tests in `SpawnRitualStateMachineTests.cs` — 3-state transitions, all tests green
3. **A.3** — Delete `CubeCloudManager.cs`, `CubeCloudPhaseDriver.cs`, `SilhouetteBehavior.cs`
4. **A.4** — Delete `Cube.prefab`, all CubeCloud GameObjects from `SampleScene.unity`
5. **A.5** — Refactor `_DebugStatusSimulator.cs` to scrub through 3 new phases
6. **A.6** — Refactor `SpawnRitualController.cs` phase entry events: `OnShellManifestEnter`, `OnRevealedEnter`, `OnAwakenedEnter`
7. **A.7** — Verify Editor + Quest build compiles, simulator buttons fire new events

**Acceptance:** scene contains no cube cloud, state machine tests green, controller fires 3 new events

### Phase B — Stage 1 Mannequin
**Goal:** suspended anatomical mannequin for the full backend processing duration

**Tasks:**
1. **B.1** — Create `AnatomicalMannequinController.cs` MonoBehaviour
2. **B.2** — Create mannequin material: stock URP Lit, Transparent, off-white base + cyan emission. NO custom shader graph required for v1 — use stock URP Lit shader properties (Saturday's mistakes file: avoid custom shader work where stock URP nodes suffice).
3. **B.3** — Create `GroundingShadowQuad.prefab`: textured quad with circular gradient (cyan tint), Renderer parented to avatar root
4. **B.4** — Wire `AnatomicalMannequinController` to spawn mannequin at ritual anchor on `OnShellManifestEnter`
5. **B.5** — Animation: chest breathing via Animator state machine, single looped breath clip
6. **B.6** — Animation: continuous Y-axis drift in `Update()` (5 lines of code, no Animator)
7. **B.7** — Float offset (transform.y = anchor.y + 0.03f)
8. **B.8** — Test on Quest: mannequin appears, breathes, rotates, grounded shadow visible

**Acceptance:** mannequin spawns on event, sustains attention with subtle motion for 5+ min, grounding shadow visible on real floor

### Phase C — Stage 1 → 2 Scan-line transition
**Goal:** vertical scan that materializes Meshy retextured GLB from the mannequin

**Tasks:**
1. **C.1** — Create `ScanLineTransition.cs` MonoBehaviour
2. **C.2** — Create ONE shared `ScanClipShader.shadergraph`: world.y vs _ScanY uniform + _ClipDirection bool (clip-above for mannequin, clip-below for revealed)
3. **C.3** — Create `ScanLineQuad.prefab`: thin emissive cyan quad, scaled to avatar bounding circle, follows _ScanY uniform
4. **C.4** — Coroutine animator: lerp `_ScanY` from -0.1 to 1.95 over 3.5s, ease-out cubic
5. **C.5** — On `OnRevealedEnter`: trigger scan; pass mannequin GameObject and Meshy retextured GLB references
6. **C.6** — On scan completion: destroy mannequin, reset Meshy GLB material to standard, despawn scan line quad
7. **C.7** — Test on Quest: scan fires, scan line visible, mannequin erodes upward while real avatar emerges upward

**Acceptance:** transition completes in 3-4s, eye tracks scan line not topology swap, no perceptible pop

### Phase D — Stage 2 Clean Avatar Hold
**Goal:** Meshy retextured GLB holds visibly during rigging wait

**Tasks:**
1. **D.1** — Add `SubtleMicroRotation.cs`: ±1 degree Y-axis sine wave, 4s period
2. **D.2** — Attach to Meshy retextured GLB after scan transition
3. **D.3** — Recompute grounding shadow quad bounds for retextured GLB size
4. **D.4** — Test on Quest: avatar holds visible for full rigging duration (~60-120s), feels alive (not frozen)

**Acceptance:** clean GLB visible during stage 2 hold without disappearing, shadow tracks, slight breath of motion visible

### Phase E — Stage 2 → 3 Biological Awakening
**Goal:** rigged+animated avatar emerges from clean static avatar via biological micro-motion

**Tasks:**
1. **E.1** — Modify `TestGlbLoader.cs` to expose `LoadInvisibly(url)` for pre-loading rigged GLB
2. **E.2** — On `meshy_rigging_complete` status from backend: pre-load rigged GLB invisibly
3. **E.3** — Create `AwakeningSequence.cs`: timeline-driven animation events (breath, tilt, gaze acquire, idle start)
4. **E.4** — Material swap from clean GLB → rigged GLB at start of awakening sequence (single-frame swap, visually identical due to same mesh+texture)
5. **E.5** — LookAt Constraint: head+eyes targeting Quest XR camera, dampened, eased 0.6s on engage
6. **E.6** — Subscribe to `OnAwakenedEnter`
7. **E.7** — Test on Quest: awakening reads as life, gaze acquisition is the emotional climax

**Acceptance:** breath → tilt → gaze acquisition → idle plays smoothly, no jarring pop on GLB swap

### Phase F — Stage 3 Living Avatar
**Goal:** persistent living behavior, gaze tracking

**Tasks:**
1. **F.1** — `LivingAvatarController.cs`: dampened LookAt constraint, ±15 degree max
2. **F.2** — Micro-movement scheduler: random weight shifts, eye blinks, head turns at randomized intervals
3. **F.3** — Test on Quest: avatar feels alive, tracks user, never reads as static

**Acceptance:** user can walk around avatar and it tracks them, micro-movements vary, never reads as canned loop

### Phase G — Failure mode handling
**Goal:** never break the magic with sudden "loading failed" text

**Tasks:**
1. **G.1** — If TRELLIS fails: stay at mannequin stage indefinitely; subtle MR HUD message ("Generation paused — retrying"); retry up to 2x
2. **G.2** — If Meshy retexture fails: skip clean reveal, fall back to TRELLIS plastic (worst case — show the plastic version only if Meshy unavailable)
3. **G.3** — If Meshy rigging fails: stay at stage 2 (clean static avatar visible), graceful end state with HUD "Animation not available"
4. **G.4** — Test on Quest with simulated failures

**Acceptance:** every failure path produces coherent visual experience, never broken loading text

### Phase H — Device verification + iteration
**Goal:** match design intent on actual Quest device

**Tasks:**
1. **H.1** — Build to Quest, full end-to-end ritual capture
2. **H.2** — Compare each stage + transition against references (Westworld, Vision Pro)
3. **H.3** — Tune timings, easing curves, mannequin emissive intensity until each beat lands
4. **H.4** — Re-test with founder if available for emotional read

**Acceptance:** ritual reads as one continuous summoning, not a sequence of loads

### Phase I — Demo capture
**Goal:** founder-grade recording

**Tasks:**
1. **I.1** — Full end-to-end ritual on Quest with headset video recording
2. **I.2** — Multiple angles, short highlight cuts
3. **I.3** — Side-by-side: Saturday's cube ritual baseline vs new 3-stage origin story
4. **I.4** — `adb pull` videos, package for founder review

**Acceptance:** demo recording shows full ritual at founder-grade quality

---

## Backend changes required

Server polling endpoint changes:

```
GET /generate/{task_id}/status

Response (new shape):
{
  "status": "processing | shell_manifest | revealed | awakened | failed",
  "progress": 0-100,
  "retextured_glb_url": "/avatars/{task_id}_clean.glb",   // present after BOTH TRELLIS + Meshy Retexture complete
  "rigged_glb_url": "/avatars/{task_id}_rigged.glb",       // present after Meshy Rigging completes
  "message": ""
}
```

Critical: `retextured_glb_url` is NOT emitted until BOTH TRELLIS completes AND Meshy Retexture completes. Quest never sees the intermediate plastic state. This is a simple change in `app/services/generation_pipeline.py` — chain the Meshy Retexture call inline after TRELLIS download, only update status to `revealed` once Meshy returns.

---

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Topology mismatch causes visible pop during scan transition | Medium | High | Emissive scan quad + cubic ease curve hide the seam; iterate on Quest |
| Mannequin gets boring during 5-min hold | Medium | Medium | Continuous slow rotation + breathing keeps motion alive; if still feels frozen, add subtle ambient drift particles at feet |
| Meshy retexture fails → fall back to TRELLIS plastic | Low | Medium | Phase G.2 — graceful degradation |
| Meshy rigging fails → stay at stage 2 forever | Low | Medium | Phase G.3 — graceful end state |
| Stage 1 → 2 scan transition framerate dip | Low | Low | Single shader graph + single quad — minimal perf impact vs original VFX Graph plan |
| Animator binding to swapped rigged GLB fails | Medium | Medium | Phase E.4 needs prototyping; fallback to full GLB swap with imperceptible crossfade |
| Glancing-angle alpha issues on mannequin | Medium | Low | Stock URP Lit Transparent should handle; if issues, switch to Surface Shader |

---

## Acceptance criteria (whole-system)

The ritual is "done" when:

1. End-to-end pipeline runs on Quest without manual intervention
2. Mannequin visible within 1s of capture trigger
3. Mannequin sustains attention for 5+ min without feeling frozen
4. Stage 1→2 scan transition is cognitively invisible (no perceptible pop)
5. Clean retextured avatar visible during stage 2 hold without disappearing
6. Stage 2→3 awakening with gaze acquisition lands as the emotional climax
7. Stage 3 living avatar tracks user, varies micro-movements
8. All failure modes produce coherent visual experiences
9. Demo recording produced (Phase I)

---

## What this plan does NOT include (v1 scope cuts)

- Audio (deferred to v2 — diegetic hum, transition stings, awakening breath)
- Real-time reflection probe baking (deferred to v2)
- Polished biological micro-movements beyond core 3 events (finger twitches, neck adjustments — v2)
- Custom rigging on the mannequin shell (static for v1)
- Multi-user shared MR rituals
- Voice / Layer 4 of Vipin's pipeline (TTS/STT/Lip Sync)
- Hand-interaction with the avatar
- Avatar leaving its anchor position
- Replay of previous ritual generations

---

## Reference material

- Round 5 cross-AI synthesis (in chat 2026-05-11, ChatGPT + Gemini)
- `drafts/glb_stage_transitions_round5_brief.md`
- `drafts/origin_story_ui_visualization_brief.md`
- `docs/superpowers/specs/2026-05-08-spawn-ritual-design.md` (v3 cube design being replaced)
- `diaries/2026-05-09.md` (context on cube-cloud failing on device)
- Council references: Westworld S1 host construction, Apple Vision Pro launch film, Blade Runner 2049 Joi hologram, Alex Garland's DEVS

---

## Why v2 is the right shape

The cube-cloud failed because we underestimated implementation complexity and ran out of patience to fix on-device math bugs. v1 of THIS plan repeated the pattern with shader-heavy phases (purification wave, VFX Graph particles, dual-GLB rendering). Today's UX honesty pass (Gemini concept art proving the plastic→clean delta wouldn't read) caught it early.

v2 makes ONE bet: stock URP Lit + one custom shader graph + one emissive quad + animator-driven biological awakening. That's a substantially smaller bet than v1, with a higher probability of landing on device. The cube-cloud lesson applied forward.
