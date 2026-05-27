# HoloBorn — Handoff: Refinement Phase (2026-05-27)

**Purpose:** cold-start handoff for the NEXT chat. Read this + `docs/REFINEMENT-PHASE.md` and you have full context to continue. Auto-memory (`MEMORY.md`) loads separately and covers project history + how Parthiv works — trust it.

---

## Where we are
- **Development cycle is COMPLETE.** Project is in a **refinement phase**: iterate quality/perception on the existing build; no new core capability.
- **Active gen path: Hunyuan3D-2mv** (`USE_HUNYUAN=true`, RunPod endpoint `itd7oz9wexb1oo`). NOT TRELLIS (`pz2c4wvo2rcdw9` is the old path). `grep USE_HUNYUAN .env` before assuming anything.
- Pipeline: Quest capture → 2-step multi-image portraitizer → Hunyuan (RunPod) → Meshy retex + rig + animate → PBR graft + roughness clamp → Mac FastAPI + ngrok → Quest spawn-ritual hologram.
- POC validated (e2e 13:21, council-graded legit autonomous-MR-embodiment POC).

## ▶ FIRST TASK — Decimation (the confirmed #1)
The ONE confirmed live bug: Hunyuan GLBs are **~500k tris** → avatar **stutters when you walk around it in Quest passthrough**. Critically, the stutter is **NOT in the recorded video** — the deliverable is clean. So it's a live-UX perf issue, not a pipeline defect. See `[[quest-tri-ceiling-decimation-queued]]`.

Steps:
1. Check for tooling: `tools/normalize_glb_for_quest.py` (untracked, likely the decimation/Quest-prep tool) and/or `gltfpack`. Read/verify before using.
2. Decimate a test GLB: ~500k → **~80k tris** (+ 2K KTX2 textures). In production this must run **before Meshy rigging** so skin weights stay clean — but for a quick Y-test, decimate a staged `test*.glb` directly.
3. Swap the decimated GLB into `results/avatars/test.glb` (and `test_rigged.glb` for the grounded reveal — note `[[project_ytest_three_urls]]`: there are THREE test URLs).
4. Y-test: Parthiv presses Y/B on Quest, walks around, confirms stutter is gone.
5. Watch for quality loss from decimation — if texture/silhouette degrades, tune the target tri count.

## Y-test runbook (bring infra up)
Infra is currently **OFF**. To Y-test:
1. `ngrok config add-authtoken $(grep ^NGROK= .env | cut -d= -f2)` then `ngrok http --domain=<MESHY_PUBLIC_HOST host> 8000` — **read the domain from `.env`** (`MESHY_PUBLIC_HOST`, currently `trimmer-unbalance-casing.ngrok-free.dev`); it churns. Sequence authtoken→tunnel in one process to avoid the pairing race (`[[feedback_ngrok_url_authtoken_pairing]]`).
2. `.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` (background).
3. Verify: `curl -H "ngrok-skip-browser-warning: true" https://<domain>/health` → `{"status":"alive"}`.
4. Tear down after (kill uvicorn + ngrok). RunPod is NOT needed for Y-tests (GLB is pre-staged).

## Critical gotchas (don't relearn these the hard way)
- **ngrok domain** → always from `.env`, never hardcode. Verify the authtoken owns the reserved domain (start with explicit `--domain` → fail-fast).
- **uvicorn restart** required after ANY `.env` change (pydantic-settings caches at startup). `[[feedback_uvicorn_restart_on_env_change]]`
- **RunPod**: `workersMax` is often 0 too — bump BOTH min+max to warm; scale back to **0/0 after** (budget is tight). `[[project_runpod_min_workers]]`
- **adb logs**: `adb logcat -d` (dump), never `-c` (wipes buffer). `[[feedback_adb_logcat_dump_not_stream]]`
- **Output is one fused mesh + one material** → eyes/hair can't get targeted shaders without building part-segmentation first.
- **Don't judge grounding from 2D stills** — flat passthrough screenshots lie. `[[feedback_no_depth_from_2d_stills]]`
- **No-HIL principle**: no per-avatar manual fixes (kills the moat + the solo workload).

## Refinement backlog (ranked)
1. **Decimation** — confirmed need, start here (backend, fast Y-test loop). ← in progress
2. **Quality strategy** — hair/eyes/identity ceiling; needs its own plan (A/B alt models like Tripo/Rodin, targeted material work, or deliberate stylization). Foundation-model-bound.
3. **Grounding (contact shadow)** — Unity-side; planted-in-room presence. Needs APK rebuild.
4. **Idle life (breathing/sway)** — Unity-side; builds on 05-25 Mixamo breathing. Needs rebuild.
5. **Eyes/hair shaders** — Tier 2; needs part-segmentation infra first; procedural eyeball insertion is the robust eye route.

## Optional parallel task (Parthiv was keen)
Build **workflow skills** for his repeated procedures (he runs these every session): `holoborn-ytest-up`, `holoborn-demo-prep`, `holoborn-fetch-quest`, plus session-start / diary / teardown. Use the `writing-skills` skill. Encode the STABLE shape, READ volatile bits (ngrok domain) from `.env` at runtime — never hardcode.

## State / pointers
- **Infra:** OFF (uvicorn down, ngrok down, RunPod 0/0).
- **Diaries:** `diaries/` complete through 2026-05-27 (05-23 Hunyuan-pivot detail lives in the **Alienware** repo).
- **Memory:** auto-loaded `MEMORY.md` — covers Hunyuan path, true objective (digital legacy), Quest tri-ceiling, and how Parthiv works (calibrate, don't cheerlead; he vents then ships — don't mistake a crash for a stop).
- **Admin:** `admin/timesheets/` (gitignored) — May effort sheet (Parthiv-only) ready; **due to Priyanka by EOM**. Clean Desktop copies: `Parthiv - May 2026 Timesheet.xlsx/.csv`.
- **Today's Y-test artifacts:** `~/Desktop/holoborn_ytest_20260527/`.
- **Phase doc:** `docs/REFINEMENT-PHASE.md`.

## First move in the new chat
"Read the refinement-phase handoff + REFINEMENT-PHASE.md, then let's start decimation." Verify the decimation tool → decimate a test GLB → swap → Y-test the stutter.
