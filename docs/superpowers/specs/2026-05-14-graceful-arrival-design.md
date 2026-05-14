# Graceful Arrival — Stage 3 closing beat (design spec)

**Date:** 2026-05-14 morning
**Author:** Parthiv (with Claude Code)
**Status:** Spec, approved for build
**Scope:** Stage 3 ONLY — replaces Wednesday's rejected fall+impact+squat design. Stages 1 + 2 unchanged.
**Time budget:** 2–3 hours focused dev including 1–2 sideload iterations. Targets close-of-day Thursday so Friday is free for Bricks 5 (sigil emission color per pipeline stage) + 6 (end-to-end + MP4 capture).
**Supersedes:** `Assets/HoloBorn/Scripts/Stage3ReleaseController.cs` — that script (procedural fall + impact squat + idle anim) is fully deprecated and deleted by this work.

---

## What we're building

End of Stage 2 leaves the retex PBR avatar floating at +30cm above the sigil. Stage 3 closes the ritual via a **scan-out + sigil free-fall + rigged respawn** sequence (~5.9s total to held state, see timing table for breakdown):

1. **Sigil rises** foot-to-head through the retex avatar (reusing Stage 2's scan motion). As the sigil rises, the retex avatar **dissolves out bottom-up**, tied to sigil world-Y. By the time the sigil reaches above head height, the retex is gone — empty hover.
2. **Sigil free-falls** under quadratic gravity (~0.7s for a 2.4m drop), lands flat with a small bounce (~15% of fall height, single bounce), and emits a single emission pulse on impact before dimming to an ambient cyan floor halo.
3. **Final rigged GLB materializes top-down** at floor level — feet aligned exactly to the sigil's top surface using the existing `AlignAvatarFeetTo` helper. No float. No sink. Standing on the sigil platform.
4. **Breath onset** on the rigged avatar — `Spine02` bone oscillation drives chest motion (subtle, ~1–2° around sagittal axis at ~0.25Hz). Held indefinitely.

**Conceptual frame (founder-locked):** scientist examining a biosymbiote specimen. The avatar is the SUBJECT on a display platform; the user (in MR) is the OBSERVER who can walk around it. The sigil's job evolves through the ritual — summon glyph (Stage 1) → scanner (Stage 2 + 3a) → free-falling instrument finishing its cycle (Stage 3b) → display podium (Stage 3c+). A-pose-as-final reads as anatomical reference pose, not as tech-demo placeholder.

Stages 4+ (interactive avatar behavior, gesture, voice, etc.) are out of scope.

---

## Why this design

Wednesday's failed Stage 3 made the **avatar** fall. Founder rejected it because falling bodies read as "ragdoll obeying gravity" and shatter the hologram illusion. This design **transposes the fall onto the sigil**, which is an *object* — physics on objects reads as physics, not as ragdoll. The fall mechanic is preserved; only the asset it's applied to changes.

This design also creates a **coherent dissolve-direction system** across the ritual:

| Beat | Direction | Semantic |
|---|---|---|
| Stage 1 mannequin reveal | bottom-up | scaffold built from the floor |
| Stage 2 retex reveal | top-down | scanner paints from above |
| Stage 3a retex vanish | bottom-up | scanner extracts upward |
| Stage 3b final spawn | top-down | finished being descends, anchors |

And it **inverts Stage 2's primitive** rather than inventing a new one — every shader, controller, and helper used in Stage 3 already exists from Stages 1–2. Total new code surface is one controller + one breath driver. Yesterday's bone-axis risk and animation-library hunt are both deleted from the threat model.

---

## Locked decisions

### Stage 3a — Sigil rise + retex vanish

- **Sigil motion:** rises foot-to-head (~2.5s) using Smootherstep (Ken Perlin quintic), peak Y ≈ 2.4m. Identical primitive to Stage 2's rise.
- **Retex dissolve:** existing `MannequinRimDissolve.shader` with `_UseWorldY = 1` and `_InvertDissolve = 1`. Threshold driven by sigil's current world-Y — sigil rising past avatar Y means that slice of avatar dissolves out. Bottom-up direction: feet vanish first, head last.
- **Pause at top:** 0.3s. Retex fully gone. Empty space at +30cm.

### Stage 3b — Sigil free-fall

- **Physics:** real quadratic gravity. `velocity += -9.81 * dt`; `pos.y += velocity * dt`. From peak Y ≈ 2.4m to floor Y = 0 takes ≈ 0.7s, impact velocity ≈ 6.9 m/s.
- **Orientation:** stays horizontal flat throughout fall (cleanest read). On impact, ~5° rocking wobble damps to flat over 0.3s.
- **Bounce:** single bounce, ~15% of drop height (≈ 36cm), then settles. Reads as energy preservation, not cartoonish.
- **Emission pulse on impact:** emission intensity spikes 3× for 0.15s, then ramps down over 0.4s to ambient floor-halo level (sigil emission ≈ 30% of Stage 1 baseline). Halo holds through Beat 6.

### Stage 3c — Final rigged GLB spawn

- **Asset:** rigged GLB output (TRELLIS → Meshy Retexture → **Meshy Rigging** endpoint). The rigging step is required — breath driving `Spine02` needs the rigged skeleton to work. Premium-grafted PBR materials applied as today's `tools/graft_pbr_materials.py` does.
- **Position:** feet aligned to sigil top surface using `AlignAvatarFeetTo(transform, sigilTopY)`. Neither float (no +30cm offset) nor sink (no clipping through floor). Sigil top Y is measured from sigil's bounds.max.y at rest.
- **Dissolve direction:** top-down. Existing shader with `_UseWorldY = 1` and `_InvertDissolve = 0` (i.e., default Brick 3 mode). Head reveals first, feet last.
- **Duration:** 1.5s, Smootherstep easing.
- **Pre-load:** rigged GLB pre-loaded on `OnRevealedEnter` (Stage 2 entry) and parked off-camera (e.g. at `(40, -100, 0)`, distinct from retex park position). This gives ~15+s of Stage 2 hold time for the GLB load to complete before Stage 3 fires. Concurrent-preload guard already removed from `LoadGlbAtAsync` (Wednesday's Round 5 fix).
- **Fallback if pre-load fails:** `LogError` + visible status text on `_DebugStatusSimulator`. NO silent fallback to retex (per Wednesday's mistakes #1 rule).

### Stage 3d — Breath onset + indefinite hold

- **Breath driver:** new `RiggedAvatarBreath.cs` MonoBehaviour. Drives `Spine02` local rotation around its sagittal axis (X by default; configurable in case Meshy rig uses non-canonical axis — see Risk Register).
- **Amplitude:** 1.5° peak rotation (subtle).
- **Frequency:** 0.25Hz (4-second breath cycle — slow, deliberate, "specimen at rest").
- **Easing:** sine wave with slight asymmetry (inhale 1.6s, exhale 2.4s — natural breath pattern).
- **Start delay:** 0.3s after dissolve completes (let the static spawn pose register before motion begins).

### Sigil's final state (Beat 6 onward)

- Rests flat on floor, beneath the avatar's feet.
- Emission at 30% of Stage 1 baseline (ambient halo, not active glyph).
- Continues slow Y-rotation at Stage 1 rate (12°/sec, 1 turn per 30s) — keeps the podium "alive" visually.

---

## Beat-by-beat timing table

| t (s, relative to `OnAwakenedEnter`) | Event | Tech |
|---|---|---|
| 0.0 | `Stage3GracefulArrivalController.OnAwakenedEnter` fires | event |
| 0.0 → 2.5 | Sigil rises 0 → 2.4m, Smootherstep. Retex dissolve threshold tied to sigil.y | coroutine, shader property driver |
| 2.5 → 2.8 | Sigil holds at peak Y. Retex fully gone | pause |
| 2.8 → 3.5 | Sigil free-falls under quadratic gravity, lands flat. Bounce begins. | physics coroutine |
| 3.5 → 3.8 | Sigil bounces ~36cm, settles. Wobble damps to flat. Emission pulse → halo. | coroutine |
| 3.8 → 4.1 | Settle pause. Sigil at rest, empty hover above. | pause |
| 4.1 → 5.6 | Rigged GLB materializes top-down. Feet aligned to sigil top. | dissolve coroutine + AlignAvatarFeetTo |
| 5.6 → 5.9 | Settle pause before breath onset. | pause |
| 5.9 → ∞ | Breath onset: Spine02 oscillation. Sigil slow Y-rotation. Avatar held. | breath driver + sigil rotation coroutine |

Total Stage 3 duration to held final state: **≈5.9 seconds**.

---

## Components to build

| Asset | Path | Notes |
|---|---|---|
| Stage 3 controller | `Assets/HoloBorn/Scripts/Stage3GracefulArrivalController.cs` | **NEW.** Owns the 6-beat sequence. Subscribes to `OnRevealedEnter` (preload) + `OnAwakenedEnter` (execute). |
| Breath driver | `Assets/HoloBorn/Scripts/SpawnRitual/RiggedAvatarBreath.cs` | **NEW.** Drives Spine02 sine-wave rotation. Configurable axis + amplitude. |
| Old Stage 3 controller | `Assets/HoloBorn/Scripts/Stage3ReleaseController.cs` | **DELETE.** Replaced entirely. |
| Quadratic gravity helper | `Assets/HoloBorn/Scripts/SpawnRitual/QuadraticGravityFall.cs` | **NEW** (or inlined). Encapsulates gravity coroutine + bounce + wobble damping. |
| TestGlbLoader | `Assets/HoloBorn/Scripts/TestGlbLoader.cs` | **EXISTS** — verify `LoadGlbAtAsync` handles concurrent rigged preload correctly (Wed Round 5 fix). May need a `LoadGlbHiddenAsync` overload that parks the asset off-camera. |
| AlignAvatarFeetTo helper | (already exists, static method on `ScanLineTransitionController`) | **EXISTS.** Reuse for foot-to-sigil-top alignment. |
| Dissolve shader | `Assets/HoloBorn/Shaders/MannequinRimDissolve.shader` | **EXISTS.** `_UseWorldY` + `_InvertDissolve` already shipped. No shader changes. |
| Sigil prefab | `Assets/HoloBorn/Prefabs/SummoningSigil_Prefab.prefab` | **EXISTS.** Verify emission property is exposed for pulse animation. |
| Scene wiring | `Assets/Scenes/SampleScene.unity` | Remove old `Stage3ReleaseController` MonoBehaviour entry. Add new `Stage3GracefulArrivalController` with all Inspector refs (sigil, retex+rigged GLB loaders, dissolve material, breath driver, timings). |
| `_DebugStatusSimulator` UI status | `Assets/HoloBorn/Scripts/SpawnRitual/_DebugStatusSimulator.cs` | Add visible TextMesh field for fallback error messages (Wed mistakes #1 rule). |

---

## Backend dependencies

**Critical:** This design requires the final asset to come from the **Meshy Rigging** endpoint (rigged GLB with bones). Wednesday's diary notes:

> `meshy_animation_client.py` exists but ORPHAN — not called from `process_task`. Pipeline never emits `rigging` status. So Stage 3 must run on simulator path, not real backend, today.

For the **EOW demo MP4** (Brick 6), the backend chain must be wired so `process_task` calls Meshy Rigging after Meshy Retexture. The `tools/graft_pbr_materials.py` graft is still required to restore premium PBR materials onto the rigged GLB.

For **Brick 4 (this spec)**, we use the pre-staged `results/avatars/test_rigged.glb` (42MB grafted, currently action_id=38 Dozing_Elderly but the animation clip is IRRELEVANT — we play no animation, only use the skeleton). The clip baked into the GLB is dead weight; future re-bakes can request the rig WITHOUT any animation clip if Meshy's API supports it (action_id=0 rig-only, or strip the clip post-bake).

**Open question:** can Meshy's rigging endpoint produce a rig-only output (no animation clip)? If yes, future re-bakes drop the clip to save GLB size and remove the "dead animation" surface. If no, we ship with `action_id=38` baked in and just never call `Animation.Play()` — the clip sits unused.

---

## Out of scope (deferred)

- Brick 5: sigil emission color shifts per backend pipeline stage (cyan portraitize / white generate / gold retex / cyan-violet rig). Next brick after this lands.
- Brick 6: end-to-end + MP4 capture, including backend `meshy_animation_client.py` wiring into `process_task`, `.env` `MESHY_PUBLIC_HOST` swap to `princess-stooge-chute`, RunPod warmup ritual, lanyard removal.
- Audio cues for Stage 3 beats (sigil rise hum, fall whoosh, impact thud, materialize chime, ambient lab hum). Placeholder: reuse Stage 2's scanner audio for the rise; the fall and respawn play silent until audio assets are sourced. Audio polish is its own brick.
- World-lock drift on Stage 1 spawn (deferred from Wednesday). Architectural fix via `OVRSpatialAnchor`. Not blocking demo.
- Missing-script warning on `SpawnRitualController` GameObject (orphaned `CubeCloudPhaseDriver` reference). Cosmetic scene-cleanup.
- Re-baking `test_rigged.glb` without the Dozing_Elderly clip. Cosmetic — clip is never played.
- User-interactive avatar behavior (gesture, voice, gaze tracking). Post-EOW.

---

## Acceptance criteria

On Quest sideload, with Stage 2 having completed cleanly and `OnAwakenedEnter` firing (via real backend pipeline or `_DebugStatusSimulator` Y-button):

1. Sigil begins rising from floor through the retex avatar's feet within 0.05s of Awakened entry.
2. Retex avatar dissolves out **bottom-up** as sigil rises — feet vanish first, head vanishes last. Dissolve threshold visibly tracks sigil Y.
3. By t≈2.5s, sigil is at peak (~2.4m above floor), retex is fully gone.
4. Sigil free-falls visibly under accelerating motion (NOT linear) over ≈0.7s.
5. Sigil lands flat on floor, performs a single small bounce (~36cm peak), and settles.
6. Emission pulse fires at moment of impact — visible spike that dims to ambient floor halo.
7. After settle pause, rigged avatar materializes via **top-down** dissolve — head appears first, feet last.
8. Final avatar's feet rest precisely on the sigil's top surface — no float, no sink, no clip.
9. After dissolve completes + brief settle pause, breath onset begins on `Spine02`. Subtle chest motion visible at viewing distance.
10. Sigil maintains slow Y-rotation as ambient floor halo. Avatar holds indefinitely.
11. **No frame drops, no z-fighting between sigil-disc and avatar-feet, no visible artifacts.**
12. **Total Stage 3 duration from Awakened entry to held final state: ~5.9 seconds, ±0.3s tolerance.**
13. **If rigged GLB preload fails: visible error text on `_DebugStatusSimulator` UI** + `LogError` (NOT silent fallback to retex).

---

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Spine02 local sagittal axis is not X — breath rotation produces side-to-side wobble instead of front-to-back chest motion | Medium | Medium | Build with `breathAxis` as Inspector-configurable Vector3. First sideload tries `(1,0,0)`; if wrong, swap to `(0,0,1)` or `(0,1,0)`. Cheaper than yesterday's full bone-axis spike because the failure mode is obvious ("breath looks like a wobble"). |
| Rigged GLB pre-load fails or is too slow (>15s) and Stage 3 fires before load completes | Medium | High | Pre-load starts on `OnRevealedEnter` (Stage 2 entry), Stage 3 fires on `OnAwakenedEnter` (Stage 2 ends). Stage 2 hold ≈ 8–12s gives load headroom. Fallback: hard-fail with `LogError` + visible UI text. NO silent retex fallback. |
| Sigil's free-fall looks too fast / blink-and-miss | Low | Medium | 0.7s is the real-physics duration. If too fast on Quest, slow gravity constant to `g * 0.6` (still feels physics-like). Configurable in Inspector. |
| Sigil emission pulse blows out Quest passthrough auto-exposure | Medium | Low | Cap pulse intensity at 3× ambient. If still problematic on device, reduce to 2×. |
| Top-down dissolve of rigged avatar reveals seams or geometry issues at neck/shoulders (if Meshy rig has different mesh topology than retex) | Low | Low | The rigged GLB was already grafted with same PBR materials as retex. If seams appear: tune dissolve edge band width to mask transition. |
| Feet alignment to sigil top surface produces z-fighting (feet exactly at sigil-top means coplanar geometry) | Medium | Low | Add 1mm Y offset above sigil top in `AlignAvatarFeetTo`. Invisible at human scale; eliminates z-fighting. |
| Bounce wobble damping on sigil reads cartoonish | Low | Low | Configurable damping coefficient (default 0.6). Tune in Inspector. If still cartoonish, kill the wobble entirely — dead-flat landing is also acceptable per scientist-frame aesthetic. |
| User sees the parked rigged GLB at `(40, -100, 0)` somehow (e.g. teleports head + leans) | Very Low | Low | Park position is well outside any plausible MR room volume. Belt-and-suspenders: set the parked GLB's `MeshRenderer.enabled = false` during preload, re-enable on Stage 3 spawn. |

---

## What this spec does NOT decide

Implementation order, individual brick steps, TDD test approach — produced next via the `superpowers:writing-plans` skill once this spec is read and approved.

---

## Receipts of source thinking

This design emerged from a 5-message brainstorming exchange on 2026-05-14 morning:

1. Council audit master prompt to Gemini + ChatGPT — both converged on "no fall, hologram floats forever, A-pose finale" but proposed sacred-spiritual framing (sigil blessing, ethereal breath).
2. Parthiv reframed the aesthetic as **scientist examining biosymbiote specimen** — clinical/lab vibe, not sacred. A-pose-as-anatomical-reference logic.
3. Parthiv proposed the **scan-out + sigil free-fall + respawn** structure — transposing yesterday's fall mechanic from avatar onto sigil. Strongest design move of the session.
4. Parthiv corrected the final spawn position from floating-at-+30cm to feet-on-floor (standing on sigil platform), creating the "incomplete-forms-float, finished-form-grounds" semantic.
5. Parthiv confirmed final asset = Meshy Rigging output (rigged GLB) so breath can drive Spine02 chest bone.

Wednesday's mistakes doc (`mistakes/2026-05-13.md`) directly informed: no silent fallback paths (#1), no procedural bone rotation gambling without axis validation (#2), no trusting Meshy animation labels (#3, #6), Day-1 diagnostic logging at integration points (#8).
