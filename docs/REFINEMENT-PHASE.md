# HoloBorn — Development Cycle COMPLETE → Refinement Phase

**Proclaimed by Parthiv on 2026-05-27.** This document marks the transition and seeds the next chat.

---

## The proclamation
As of **2026-05-27**, HoloBorn's **development cycle is COMPLETE**. The project now enters a **refinement phase**: the end-to-end product exists and works; from here we **iterate on quality/perception against the existing build**, not build new core capability.

## What "complete" means — current state
- **Full automated pipeline, no human in the loop:** Quest capture → 2-step multi-image portraitizer → **Hunyuan3D-2mv** (RunPod `itd7oz9wexb1oo`) → Meshy retex + rig + animate → PBR graft + roughness clamp → served via Mac FastAPI + ngrok → Quest spawn-ritual hologram.
- **Validated:** full e2e demo at 13:21; council-graded a **legitimate autonomous-MR-embodiment POC**, technically demoable.
- **Active gen path:** Hunyuan (`USE_HUNYUAN=true`), pivoted from TRELLIS on 05-23.
- **North star (beyond this phase):** digital legacy — the conversational *mind* layer is the real frontier; this refinement phase is about the *body*.

## Confirmed findings from the 2026-05-27 Y-test
- **Stutter: CONFIRMED — but only in live passthrough viewing, NOT in the recorded video.** The recorded demo (the actual deliverable) is **clean, no stutter**. So this is a real-time on-device performance issue, not a pipeline defect. Root cause: Hunyuan geometry is **~500k triangles**. → see [[quest-tri-ceiling-decimation-queued]].
- **Quality ceiling:** acknowledged — needs a *separate strategy* (foundation-model-bound: hair / eyes / identity fidelity). Not solvable by param tuning.

## Refinement backlog (ranked)
1. **Decimation** — *CONFIRMED NEED, start here.* ~500k → ~80k tris via gltfpack, inserted **before** Meshy rigging so weights stay clean. Fixes the passthrough stutter. Backend-side → fast Y-test loop (GLB swap, no Unity rebuild).
2. **Quality strategy** — define a real approach for the hair/eyes/identity ceiling: A/B alternate models (Tripo, Rodin), targeted material work, or deliberate stylization to exit the uncanny zone. Foundation-model-bound; needs its own plan.
3. **Grounding (contact shadow)** — Unity-side; makes the avatar read as planted in the room. High presence ROI, low effort. Needs APK rebuild.
4. **Idle life (breathing / sway)** — Unity-side; "alive not mannequin." Builds on the 05-25 Mixamo breathing. Needs rebuild.
5. **Eyes / hair shaders** — Tier 2; requires part-segmentation infra first (output is one fused mesh + one material). Robust eye route = procedural eyeball insertion, not shading baked eyes.

## Working agreement for the refinement phase
- Iterate on the **existing** build; no new core capability.
- Every refinement is **Y-testable**; backend ones = GLB swap (tight loop), Unity ones = rebuild.
- **Do NOT break the autonomous / no-HIL principle** — no per-avatar manual fixes (it kills the moat and the solo workload).
- Eventually grade by **external signal** (premortem's loudest finding: get it in front of real outside users), not just founder review.

## Pointers
- **Diaries:** `diaries/` (complete through 2026-05-27; 05-23 Hunyuan-pivot detail lives in the Alienware repo).
- **Memory:** [[hunyuan-active-generation-path]] · [[quest-tri-ceiling-decimation-queued]] · [[holoborn-true-objective-digital-legacy]] · [[almost-guy-silver-medalist-downgrade]] · [[timesheet-obligation-priyanka]].
- **Admin:** `admin/timesheets/` (gitignored) — May effort sheet (Parthiv-only) prepared; due to Priyanka by EOM.
- **Today's Y-test artifacts:** `~/Desktop/holoborn_ytest_20260527/`.

## First move in the next chat
Decimation. Verify `gltfpack` / `tools/normalize_glb_for_quest.py`, decimate a test GLB (~500k → ~80k tris), swap into `test.glb`, Y-test the walk-around stutter.
