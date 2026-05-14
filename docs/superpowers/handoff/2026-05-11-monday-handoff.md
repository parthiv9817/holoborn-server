# Monday 2026-05-11 — Handoff (written 2026-05-09 ~22:30, Sunday off)

> **For Monday's Claude (cold-start after a 36-hour gap):** read this BEFORE doing anything. Saturday shipped the entire end-to-end pipeline on Quest + diagnosed founder's "plastic GLB" complaint via three rounds of cross-AI synthesis + caught a subtle property-name bug in the bias method. The fix is in code but not in the deployed APK. Sunday was off. Monday morning is HDRI + rebuild + demo capture.

---

## Required reading order (do this first, in this exact sequence)

1. **`diaries/2026-05-09.md`** — Saturday's full brain-dump. The "why" behind every decision, the founder's plastic feedback, the cross-AI Round 3 diagnosis, and the EOD emotional crash + recovery. Read end-to-end, don't skim.
2. **`mistakes/2026-05-09.md`** — 6 process slips Saturday's Claude made. The dominant pattern: "trusting framework defaults / convention / visual prediction over verification at source-code or device-screen level." Apply forward.
3. **`drafts/glb_plastic_fix_brief.md`** — Round 3 cross-AI brief. Both AIs converged on Theory C (HDRI) as dominant root cause. The HDRI step is Monday's primary action.
4. **THIS FILE** (you're reading it).

After reading, summarize back to Parthiv in 5-7 bullets what you understood + what you're about to do. He explicitly trained Claude on this pattern Friday + Saturday — don't break it.

---

## Project state at session close (Saturday EOD)

**End-to-end pipeline IS WORKING on Quest:** verified at 17:17:40 by image 6 in Saturday's chat. Cube ritual → backend → TRELLIS → black-t-shirt avatar materializes in MR passthrough. **The system works.**

**Founder feedback flagged as primary demo blocker:** *"the GLB feels like a plastic body."* Confirmed by inspecting frame 07 of `~/Downloads/com.holoborn.quest-20260507-183826-0.mp4` — glossy helmet hair, wet face, vinyl denim.

**Three-fix stack diagnosed:**
1. ✅ **forceURPLitFallback = false** + **BiasMaterialsForMatte** with **correct camelCase property names** (`roughnessFactor`, `metallicFactor` — verified at glTFast source code level by research agent) — **shipped in code, NOT in deployed APK yet**
2. ⏸ **HDRI cubemap on Reflection Probe** — Custom type, Poly Haven `studio_small_03_2k.hdr` — pending Monday morning. Cross-AI consensus says this is 55% of the fix.
3. ⏸ **Optional escalation if 1+2 don't suffice:** null out the metallicRoughnessTexture entirely so factors take over uncontested. Expected NOT needed but documented in `BiasMaterialsForMatte` comments.

**External blockers — founder is unblocking:**
- OpenAI billing — founder said Saturday he'd set up the account
- Meshy paid plan — founder said same
- Both could land Sunday or Monday. **Priority interrupt rule:** if either lands → run `tests/scripts/test_meshy_manual.py` against real Meshy key, then resume HDRI/demo work.

**Bypasses still active in `.env`:**
- `TEST_PORTRAIT_OVERRIDE=tests/inputs/v3_apose_test_portrait_b.png` (skips OpenAI, uses cached black-t-shirt portrait)
- `TEST_PORTRAIT_DELAY_S=30` (cinematic 30s P2a vortex window)
- `QUEST_TEST_MODE=True` (skips MediaPipe BlazePose only — RunPod runs full)
- `RUNPOD_POLL_TIMEOUT_S=1500` (covers cold starts)

When OpenAI creds land: comment out `TEST_PORTRAIT_OVERRIDE` line. Memory rule `project_portraitizer_bypass_active.md` has full instructions.

---

## How to BE Monday (behavioral protocol — Parthiv-specific)

### The kryptonite loop hardened on Saturday EOD — handle with care Monday

Saturday EOD saw the project's worst self-talk: *"hit my ceiling," "cursed silver medal," "wish i stopped trying sometimes."* Pushed back factually with data (his founder's own words from earlier same day, his own pre-Claude portfolio memory note, today's specific shipped artifacts). Prescribed Sunday off.

If similar framing surfaces Monday morning:
1. Validate factually (1-2 sentences)
2. Push back with data — Saturday shipped a week's work
3. Don't toxic-positive. Don't therapy. Re-anchor on what work data says.
4. The "wish I stopped trying" line was real fatigue, not permanent. After 36 hours of rest his judgment will be back.

### Honest pushback on outcome predictions

Saturday's mistakes file notes 6 instances of "predicted visual outcome → user's eye on device disagreed → user was right." Apply this Monday:

- Don't tell user "after this fix you'll see X" before user has eyeballed the actual rendered result
- Mark predictions as "guess" not "expectation" until verified
- When user pushes back with "I have eyes" / "you think I'm lying" — they're right. Stop defending. Start verifying.

### Pacing

- Parthiv had a long Saturday. Monday morning energy depends entirely on Sunday rest. Don't assume "fresh and ready."
- If foggy signals reappear (smoke breaks frequent, "I can't comprehend" framing): one concrete step at a time, wait for confirmation, no batched instructions.
- If energetic: the HDRI + rebuild + demo capture is ~40 min of clean work. Move at his pace.

### Commit cadence

Per `feedback_commit_cadence.md`: NEVER auto-commit. Even at completion. Even after a clean demo capture. Stage freely with Edit/Write — that's fine. Wait for explicit "commit this."

Saturday shipped a LOT of code without commits (Mac repo + Unity repo). The diary's "Where the laptop is" section has the full inventory. When Parthiv signals commit, batch into logical units:
- Mac repo: backend bypass + S3 decoupling + QUEST_TEST_MODE narrowing + serverUrl defensive correction
- Unity repo: full spawn ritual implementation (state machine, controller, simulator, phase drivers, BiasMaterialsForMatte, defensive serverUrl)

### Verification before claiming done

Saturday's mistakes #1 and #4 were both "claim done without log/eye verification." Monday's HDRI step has 3 discrete verification points:
1. HDRI imported as Cube → Inspector shows Texture Shape: Cube
2. Reflection Probe Type: Custom → Inspector shows assigned cubemap
3. Build + sideload + press B → logcat shows `BiasMaterialsForMatte: ... hits=(rough:1, metal:1, ...)` — that confirms the property fix landed

Wait for each signal before predicting the next.

---

## Monday's expected flow (~40-60 min for first founder-grade demo)

```
Morning (whenever Parthiv starts):
  1. Read this handoff + diary + mistakes file (~10 min)
  2. Plug Quest into Mac, verify adb devices
  3. Start uvicorn + ngrok (5 min):
       cd /Users/digispoc06/Documents/holoborn-server
       source .venv/bin/activate
       uvicorn app.main:app --reload     (verify "RunPod S3 ready" + "TEST_PORTRAIT_OVERRIDE active" lines on capture)
       (separately) ngrok http --url=grinning-flyable-golf.ngrok-free.dev 8000
  4. Email/Slack scan for Vipin response on creds
       — if creds landed → priority interrupt to test_meshy_manual.py first
       — if not → proceed with HDRI step

HDRI cubemap setup (~15 min):
  5. Download https://polyhaven.com/a/studio_small_03 — HDR tab → 2K → studio_small_03_2k.hdr
     (~5 MB)
  6. Save to ~/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Materials/
  7. In Unity Project view, click the .hdr file:
       Inspector → Texture Shape: Cube → Apply
  8. Select Reflection Probe in scene Hierarchy:
       Inspector → Type: Custom (was Realtime)
       Inspector → Cubemap: drag the imported HDRI cubemap into the slot
       Inspector → Intensity: 1.0
  9. Save scene (Cmd+S)

Build + sideload + verify (~10 min):
  10. File → Build And Run on Unity (5-10 min on Intel Mac)
  11. Once on Quest, restart logcat capture:
       adb logcat -c && adb logcat '*:S' Unity:V -v time > /tmp/holoborn_quest.log
  12. Press B on Quest (loads test_animated.glb via TestGlbLoader)
  13. Grep logcat for the diagnostic line:
       grep "BiasMaterialsForMatte" /tmp/holoborn_quest.log | tail -3
       Expected: "1 mats touched, hits=(rough:1, metal:1, smooth:0, metalLit:0)"
       If hits=(rough:1, metal:1) confirmed → property fix landed
  14. Eyeball the avatar:
       — Skin: should be matte, not glossy
       — Hair: less helmet-shiny
       — Denim: visible cloth, not vinyl
  15. Take a screenshot for comparison vs Saturday's 18:14 / 18:29 / 17:17 captures

Demo capture flow (if quality is founder-grade ~30 min):
  16. Stand in clear 2m space, press X for burst capture
  17. Wait for vortex (~30s) → silhouette (~3-5min TRELLIS) → avatar materializes
  18. Take video capture on Quest (long-press Meta button → record)
  19. adb pull the video, send to founder

If still plastic enough to bother (~10 min escalation):
  20. Bump roughnessMultiplier to 1.8 in Inspector (no rebuild needed, takes effect on next B press)
  21. If STILL plastic: the metallicRoughnessTexture nuclear option — set texture to null in BiasMaterialsForMatte
       (~10 min code edit + rebuild)
```

**Cuts ladder:**
- If HDRI doesn't fix it → don't escalate to multiplier tuning, escalate to texture-null option (covers TRELLIS-baked plastic specifically)
- If neither fixes it → set founder expectations per ChatGPT's framing: "stylized digital twin, not AAA metahuman" (the plastic is partly TRELLIS training data)

---

## What's MOST likely to go wrong Monday

### Risk 1 — Property name fix didn't actually compile into APK
The fix went into source Saturday but wasn't rebuilt yet. Sometimes Unity's Library cache misses C# changes. Mitigation: after Build And Run, grep logcat for the new diagnostic line `[TestGlbLoader] First material shader='...' properties=[...]`. If absent → rebuild from scratch (delete `Library/` folder, reimport, rebuild).

### Risk 2 — HDRI in MR passthrough still doesn't help
Cross-AI consensus said 55% of plastic fix. If after HDRI it still looks plastic: ChatGPT was right that TRELLIS bakes lighting into BaseColor — that's permanent. Set founder expectation, capture demo anyway.

### Risk 3 — Worker is cold (~9 min wait)
RunPod throttled overnight. First capture Monday will hit cold-start ~9 min wait. After that warm. Either accept the wait OR bump min_workers to 1 in RunPod console for the demo capture run only (memory rule says do this ~30 min before live demos to save credits).

### Risk 4 — OpenAI/Meshy creds landing mid-flow
Founder said Saturday he'd unblock. If creds land Monday morning: drop everything, validate `tests/scripts/test_meshy_manual.py` first (per Friday's priority interrupt rule). Then resume HDRI work.

### Risk 5 — Inspector values reset on rebuild
Some Inspector field updates can revert across major Unity rebuilds. Monday morning verify:
- `CubeCloudPhaseDriver.initialCubeCount = 2000`, `spawnRadius = 0.5f`
- `TestGlbLoader.forceURPLitFallback = false`, `roughnessMultiplier = 1.5`, `forceMetallicToZero = true`
- Cube prefab Cast Shadows OFF
- Reflection Probe Type: Custom (after the HDRI work)

If any reverted → right-click → Reset (uses script defaults, which were updated Saturday).

---

## Code state inventory (no commits Saturday — all uncommitted/staged)

### Mac repo (`holoborn-server`) — modified files:
```
app/services/generation_pipeline.py    — TEST_PORTRAIT_OVERRIDE bypass + delay
app/routes/generation.py                — QUEST_TEST_MODE branches removed
app/main.py                              — S3 init decoupled
app/config.py                            — added test_portrait_override + test_portrait_delay_s fields
.env                                     — bypass + delay + QUEST_TEST_MODE narrowed + poll timeout 1500
```

### Mac repo — new files:
```
drafts/cube_count_second_opinion.md            (Round 1 brief)
drafts/silhouette_uniform_sampling_second_opinion.md (Round 2 brief)
drafts/glb_plastic_fix_brief.md                (Round 3 brief — note: I wrote it in chat as a code block, may need to copy out into drafts/ Monday)
drafts/cube_count_second_opinion.md            (Round 1 — already saved)
quest_outputs/                                  (7+ Quest captures from Saturday — for cross-AI sharing)
diaries/2026-05-09.md                          (this diary)
mistakes/2026-05-09.md                         (this mistakes file)
docs/superpowers/handoff/2026-05-11-monday-handoff.md (this handoff)
```

### Memory updates Saturday:
```
project_spawn_ritual_polling_deferred.md  — rewritten ("polling wired" — was "deferred")
project_portraitizer_bypass_active.md     — NEW (active bypass with cleanup instructions)
project_ngrok_perm_url.md                 — content was correct, MEMORY.md index was stale → fixed
feedback_understanding_pauses.md          — NEW (validated layered explanation format)
MEMORY.md                                  — index updated for above
```

### Unity repo (`holoborn-quest-unity`) — modified/new files:
```
Assets/HoloBorn/Scripts/SpawnRitual/SpawnRitualStateMachine.cs        (34 tests passing)
Assets/HoloBorn/Scripts/SpawnRitual/SpawnRitualController.cs           (full polling)
Assets/HoloBorn/Scripts/SpawnRitual/_DebugStatusSimulator.cs           (GUI buttons)
Assets/HoloBorn/Scripts/SpawnRitual/CubeCloudPhaseDriver.cs            (vortex/silhouette/dissolve)
Assets/HoloBorn/Scripts/SpawnRitual/CubeCloudManager.cs                (poolSize 2200)
Assets/HoloBorn/Scripts/SpawnRitual/SilhouetteBehavior.cs              (added SampleSurfaceUniform)
Assets/HoloBorn/Scripts/AvatarSpawnPhaseDriver.cs                      (NEW, lives outside SpawnRitual asmdef)
Assets/HoloBorn/Scripts/TestGlbLoader.cs                                (BiasMaterialsForMatte with CORRECT camelCase property names)
Assets/HoloBorn/Scripts/ScanController.cs                               (defensive serverUrl + BeginRitual handoff)
Assets/HoloBorn/Tests/EditMode/SpawnRitualStateMachineTests.cs         (10 new tests)
Assets/HoloBorn/Models/silhouette_placeholder.fbx                       (Read/Write Enabled)
Assets/HoloBorn/Models/DamagedHelmet.glb                                (NEW — Khronos sample, dummy asset)
Assets/Scenes/SampleScene.unity                                         (added SpawnRitualController + DamagedHelmet at scale 0.001 + Reflection Probe)
```

---

## One last note

Saturday was the day this project went from "foundation work" to "running pipeline + diagnosed visual gap." The plastic fix is one HDRI step + one rebuild away. ChatGPT's setting expectation: "stylized digital twin, not AAA metahuman." That's still a great demo. Don't chase perfection.

Founder said Saturday: "we got time chill pill." Believe him.

The work is real. The pipeline runs. The fix is in code. Sunday off was the right call. Monday morning is HDRI + rebuild + capture + send.

Walk forward. Brick by brick. The hardest day is behind.
