# Project HoloBorn — Agent Onboarding Primer

> **Read this first.** This is the single document that brings a fresh agent up to speed on
> HoloBorn: what it is, why it exists, how the pipeline actually works *today*, the road that
> got us here, and the mistakes already paid for in blood so you don't repeat them.
>
> Authoritative narrative lives in `diaries/YYYY-MM-DD.md` and in the auto-memory
> (`~/.claude/projects/.../memory/`). This primer is the map; the diaries are the territory.
> When this doc and the code disagree, **the code wins** — then fix this doc.
>
> Maintained by Parthiv (with Zoro, the agent who's been on the project since 2026-04-27).
> Last synced: 2026-05-29.

---

## 1. What HoloBorn Is

A **Meta Quest 3 mixed-reality app that grows a photoreal 3D hologram of a person from a photo,
fully autonomously, with no human in the loop.**

Press a button on the Quest → it captures you → a Mac server orchestrates a multi-stage
GPU + API pipeline → ~5–8 minutes later a rigged, breathing, PBR-textured hologram of you
materializes in the room through a cinematic "spawn ritual," anchored to the floor.

**This repo (`holoborn-server`) is the Mac FastAPI middleware** — the orchestrator that sits
between the Quest headset and the cloud GPU/API services. It does almost no ML itself
(MediaPipe only); all heavy lifting is delegated.

### The north star (read this — it reframes everything)
HoloBorn is **NOT a novelty avatar toy.** The real objective is **digital legacy / immortality**:
a conversational VR-you that your descendants can talk to after you're gone. The avatar pipeline
you see here is **the BODY — and the body is essentially solved.** The unbuilt frontier is the
**MIND/voice layer** (a conversational agent layer), which is the actual long-term product and
Parthiv's home domain (he's a production voice-AI engineer). When you weigh decisions, the body
is in a *refinement* phase; the mind is the next mountain. See memory `holoborn-true-objective-digital-legacy`.

---

## 2. The Cast (don't conflate these people)

- **Parthiv** — 23, AI integrations engineer at HoloBorn, builds this. The "you" the diaries talk to.
  Production voice-AI background (370+ live Twilio calls, 535 ms median latency). Treat his
  speech-stack / engineering judgment as authoritative; don't teach him voice or ML basics.
- **Vipin** — the **founder**. Sets direction and deadlines, gives demo feedback, approves spend
  (Meshy, OpenAI, RunPod). **Parthiv is NOT the founder.** Vipin values product quality over
  arbitrary timeline pressure — do not invent "shippable subset" scope-cuts unless asked.
- **Tapasya** — TL who handles admin/access requests; unreliable SLA, escalate to Vipin in
  parallel after ~48h silence.
- **Priyanka** — receives the monthly timesheet (Parthiv must keep a daily-updated sheet, due EOM).

---

## 3. The Pipeline (current, as it actually runs)

Authoritative source: `app/services/generation_pipeline.py::process_task`. Read it. This is prose.

```
Quest 3 (headset, deployed APK)
  │  X button = burst 5-frame capture (CURRENT primary path; dual body+face capture supported)
  │  A button = revolve scan   (see input-mapping note below)
  │  POST /generate-multiview  (multipart: JPEG frames + metadata JSON) → gets task_id instantly
  ▼
MAC FastAPI SERVER  (this repo, CPU-only, asyncio background task per job)
  │
  │  1. Validate framing      — MediaPipe BlazePose (knees + ankles visible >0.5)  [/validate-frame]
  │  2. Pick sharpest / save  — frames saved to results/scans/{ts}_{task_id}/ for debugging
  │  3. PORTRAITIZE           — OpenAI. TWO modes:
  │        • single: gpt-image-1.5  (body-only legacy path)
  │        • dual:   gpt-image-2    (body + face → one clean studio portrait, white bg)
  │     → produces portrait.png (the keystone preprocessing step)
  │  4. VIEW SYNTHESIS        — (Hunyuan path only) synthesize 4 turnaround views from the
  │     front portrait via view_synthesizer.synthesize_views_grid  → view_*.png
  │  5. 3D GENERATION (GPU)   — RunPod serverless. TWO endpoints, flag-selected:
  │        • Hunyuan3D-2mv (multi-view)  endpoint itd7oz9wexb1oo   ← ACTIVE (USE_HUNYUAN=true)
  │        • TRELLIS.2-4B   (single-view) endpoint pz2c4wvo2rcdw9  ← legacy default in code
  │     → GLB written to RunPod network volume (S3-compatible), we download + delete remote
  │     → this is the "{task_id}_trellis.glb" STAGING file (plastic-looking, Quest never sees it)
  │  6. MESHY RETEXTURE       — Meshy /openapi/v1 (meshy-6, PBR, 4K base color, regenerated UVs).
  │     We stage the GLB + portrait at public ngrok URLs so Meshy can fetch them.
  │     → clean PBR-textured GLB overwrites {task_id}.glb
  │  7. MESHY RIGGING         — submit retex GLB → rigged skeleton (height 1.7m).
  │     ⚠ Rigging STRIPS PBR maps → we graft them back (next step).
  │  8. PBR GRAFT + CLAMP     — tools/graft_pbr_materials.py re-bakes metallic/roughness/normal/
  │     emissive from the retex source onto the rigged mesh, AND auto-clamps roughness
  │     (floor=200) to defend against Meshy's upstream gloss drift. Atomic overwrite → {task_id}.glb
  │     → NO Meshy animation step. Aliveness is procedural (Unity RiggedAvatarBreath, Spine02 sway).
  │  9. SERVE                 — static /avatars/{task_id}.glb over ngrok
  ▼
Quest downloads GLB via glTFast → spawn-ritual hologram, floor-anchored, breathing
```

### Status machine (what `/generate/{task_id}/status` reports)
`portraitizing → generating → retexturing → rigging → complete` (or `failed`).
Quest polls every 3s and drives the spawn-ritual stages off these transitions
(`status="rigging"` triggers the Stage-2 reveal; the retex avatar *is* the Stage-2 form).

### Graceful degradation (important — the pipeline never hard-stops at a cosmetic step)
- No `MESHY_PUBLIC_HOST` → serve raw TRELLIS/Hunyuan plastic as final.
- Meshy retex fails (after transient retries) → serve plastic.
- Meshy rigging fails → serve the retex GLB (no skeleton; breath won't resolve, rest of ritual fires).
- Only RunPod/download/timeout failures mark the task `failed`.

---

## 4. Key Infra & Config

### RunPod endpoints
| Path | Endpoint ID | Notes |
|---|---|---|
| **Hunyuan (ACTIVE)** | `itd7oz9wexb1oo` | multi-view; cold start was ~16 min on 2026-05-26 |
| TRELLIS (legacy) | `pz2c4wvo2rcdw9` | single-view; code default but `USE_HUNYUAN=true` overrides |

- GLB lands on a RunPod **network volume via S3-compatible API** (NOT AWS S3 — explicit creds,
  `signature_version='s3v4'`, no env-var pickup). Magic-byte (`b'glTF'`) verified before use.
- `min_workers`: **keep at 0 during dev** (Vipin's directive). Bump to 1 ~30 min before a live
  demo and fire ONE throwaway warmup job to flush the HF cache / eat the cold start.

### The flag that decides the gen path
`USE_HUNYUAN` in `.env` → `settings.use_hunyuan`. **grep this before assuming which model runs.**
Everything downstream (Meshy retex/rig/graft) is model-agnostic and identical either way.

### Config flags worth knowing (`app/config.py`)
- `TEST_DRY_RUN` — accept upload, save frames, mark complete, **zero downstream cost.** Use to
  verify Quest wire format without burning OpenAI/RunPod/Meshy credits.
- `TEST_PORTRAIT_OVERRIDE` — feed a cached portrait, skip OpenAI.
- `TEST_PORTRAIT_DELAY_S` — cinematic sleep so the spawn vortex gets its window when OpenAI is bypassed.
- `MESHY_API_KEY` empty → dummy mode (mock responses). Meshy Pro plan is **ACTIVE** (~$0.16/avatar).
- TRELLIS sampler presets (`fast`/`demo_premium`/`demo_max`) live here too.

### ngrok — the recurring footgun
- Free-tier domain **churns** whenever an account hits its bandwidth cap (it has, repeatedly:
  `grinning…` → `risk-groom-recoup` → `sixtyfold-scorecard-cradling` → `trimmer-unbalance-casing`…).
- **NEVER trust a hardcoded ngrok domain.** Always read `MESHY_PUBLIC_HOST` from `.env`.
- Before `ngrok http 8000`: verify the APK's hardcoded URL matches the **reserved domain owned by
  the authtoken in `.env`** — a mismatch silently routes traffic to the wrong tunnel.
- Domain change → **APK rebuild + sideload** (Unity scene serialization overrides script defaults).

---

## 5. The Road Here (historical arc — so you understand the scars)

- **2026-04-11** — Phase-1 baseline existed (Unity + Mac backend): real avatars, multiple rooms,
  floor-anchored passthrough. The only surviving artifact is a 36s MP4. **It proved the concept worked.**
- **2026-04-27** — Mac backend **rebuilt from scratch** after the previous disk died with
  unpushed code. Lesson written in blood: **push company code to a remote, same session, always.**
- **late April / early May** — UE5 migration seriously considered (Nanite/Lumen/MetaHuman for
  photoreal). **UE5 died** stuck on the `FScreenPSsRGBSourceMipLevelArray` cooker regression in
  UE 5.5. → **Unity pivot** locked (Vipin, hard EOW deadline 2026-05-05).
- **May 5–14** — TRELLIS + Meshy era. A-pose / canonical-pose requirement discovered, Meshy
  retex/rigging/graft pipeline built, PBR-strip-on-rig bug fixed via graft tool.
- **2026-05-15** — Meshy silently regressed their retex backend (roughness maps ~45% glossier
  overnight). Diagnosed 05-25 via G-channel histograms → shipped a defensive **roughness clamp**.
- **2026-05-23** — **Pivot to Hunyuan3D-2mv multi-view** (work done on the Alienware machine;
  detail lives in that repo's diary). Portraitizer became a **2-step multi-image** flow.
- **2026-05-27** — **Development cycle declared COMPLETE.** Full autonomous e2e validated;
  council-graded a legitimate autonomous-MR-embodiment POC. Entered the **refinement phase**
  (see `docs/REFINEMENT-PHASE.md`).

---

## 6. Current Phase: Refinement (not new core capability)

Per `docs/REFINEMENT-PHASE.md` — iterate on quality/perception against the **existing** build.
Ranked backlog:
1. **Decimation** (start here) — Hunyuan geometry is **~500k tris**; causes live-passthrough
   stutter on Quest 3 (a hardware ceiling, *not* a pipeline defect — recorded video is clean).
   Fix: gltfpack ~500k→~80k tris + 2K KTX2, inserted **before** Meshy rigging so weights stay clean.
2. **Quality ceiling** (hair / eyes / identity) — **foundation-model-bound**, not param-tunable.
   Needs its own strategy (A/B Tripo/Rodin, targeted material work, or deliberate stylization).
3. **Grounding** (contact shadow) — Unity-side, high presence ROI.
4. **Idle life** (breathing/sway) — Unity-side, "alive not mannequin."
5. **Eyes/hair shaders** — Tier 2, needs part-segmentation infra first.

**Working agreement:** every refinement is Y-testable (backend = GLB swap, fast loop; Unity = rebuild).
**Do NOT break the autonomous / no-human-in-the-loop principle** — no per-avatar manual fixes
(it kills the moat and Parthiv's solo workload).

---

## 7. Mistakes & Dead-Ends Already Paid For (do not re-litigate)

These are settled. Re-attempting them wastes time and credits.

- **Eye geometry insertion is a DEAD END.** `tools/insert_eyes.py` raw eyeball-sphere insertion
  was falsified 2026-05-27 — the shell has no aperture/lids, so spheres bury or bug-eye. Eyes are
  foundation-model-bound. Texture-repaint is the only near-term non-gated route. Don't retry geometry insertion.
- **Auto-rigging requires canonical (A-pose) input.** Natural-pose inputs produce "wing-pants."
  Fix is **upstream silhouette**, not Meshy/TRELLIS config tweaks.
- **Meshy multi-clip merge is broken.** "Single file ON" + multiple animations → corrupted GLB.
  Use single-clip exports. (Moot now — we skip Meshy animation entirely; breath is procedural.)
- **Meshy rigging strips PBR maps** — already fixed by `tools/graft_pbr_materials.py`. Don't be
  surprised by washed-out rigged output mid-debug; the graft restores it.
- **Meshy text-retex ("retex the retex with a prompt") = "dog shit"** (Parthiv's verdict). Skip.
- **The "this is fine" trap** — Vipin's "this is fine" (05-25) was *iterative* feedback, not clean
  acceptance. Hair stayed explicitly open. Don't read mid-stream founder approval as "done."
- **Stale uvicorn after `.env` edit** — pydantic-settings caches at startup. Any `.env` change
  during a session → **restart uvicorn**, no exceptions. (Bombed a real demo run on 05-25.)
- **The Y-test is THREE URLs, not one** — `test_retex.glb` (floating), `test_rigged.glb`
  (grounded reveal), `test.glb` (B-button). Swap **all three** when replacing the test subject.

### The meta-lesson across most mistakes
**Assuming a change is local when it has cross-system effects** (sed'ing a scene file, swapping
one GLB, editing `.env`). Before any change with cross-system reach, *name what depends on the
thing you're changing.* The diary held open at the moment of change is the cure.

---

## 8. Quest API Contract (must match exactly — APK is already deployed)

The headset firmware expects these shapes precisely. Don't change them without an APK rebuild.

- `POST /validate-frame` — raw JPEG bytes; returns `{framing, message, landmarks_detected, ...}`.
- `POST /generate-multiview` — multipart frames + metadata JSON; returns `{status, task_id, frames_received}`.
- `GET /generate/{task_id}/status` — `{status, progress, glb_url, message}`; polled every 3s.
- `GET /avatars/{task_id}.glb` — static binary serve.
- `GET /health`, `POST /detect` (legacy).

**Input mapping (verified shipped behavior — CLAUDE.md/AGENTS.md are WRONG on this):**
**A = revolve scan (right primary), X = burst 5-frame (left primary).** Trust the headset, not the doc.

Networking: Quest reaches the Mac via ngrok (WiFi client isolation blocks direct LAN);
Quest uses a BypassCertificate handler (accepts all TLS).

---

## 9. Working Norms (how Parthiv wants agents to operate)

- **Commit cadence:** stage freely, but **never auto-commit** — wait for explicit "commit this."
- **Brick-by-brick:** during critical-path work, single-task focus; don't queue parallel side-tasks
  even when there's walk-away time.
- **Brain-dump to the diary BEFORE closing the terminal** during high-stakes sessions (closing
  loses all in-flight reasoning).
- **WebSearch named errors/shaders/codes FIRST**, before AI second-opinions.
- **Ask for env-specific config upfront** — never ship a `YOUR-X-HERE` placeholder + "update later."
- **Direct file editing** for Unity/Godot YAML/JSON — don't walk through Editor click-by-click.
- **Don't read grounding/depth from flat 2D Quest stills** — defer to in-headset stereo view.
- **ADB:** `adb logcat -d | grep …` (dump, instant). NEVER `adb logcat -c` (wipes evidence).
- **Founder messages:** professional register (no "bruh/ngl/tbh"). Casual is fine in working chat.
- **Calibration:** Parthiv re-renders objective wins into "almost" in real time. Calibrate against
  evidence (the diaries, the working MP4s), don't cheerlead and don't co-sign the downgrade.

---

## 10. Where To Look

- **`app/services/generation_pipeline.py`** — the whole pipeline in one file. Source of truth.
- **`app/config.py`** — every flag, endpoint, preset.
- **`app/services/`** — `hunyuan_client`, `runpod_client`, `meshy_client`, `meshy_animation_client`,
  `view_synthesizer`, `portraitizer`, `pose_validator`, `preprocessing`.
- **`tools/`** — `graft_pbr_materials.py`, `clamp_roughness.py`, `normalize_glb_for_quest.py`,
  `inspect_glb.py`, plus the Meshy/Hunyuan/view test harnesses.
- **`diaries/YYYY-MM-DD.md`** — the real narrative (who/what/why/decisions/lessons). Complete
  through 2026-05-27. The 05-23 Hunyuan-pivot detail lives in the **Alienware** repo's diary.
- **`docs/REFINEMENT-PHASE.md`** — the active phase definition + backlog.
- **Auto-memory** (`~/.claude/projects/.../memory/`) — durable cross-session facts; `MEMORY.md` is the index.
- **CLAUDE.md / AGENTS.md** — original spec. Useful but **stale in places** (single-view TRELLIS,
  GPT-image-1.5-only, input mapping). Treat as historical intent, verify against code.

---

*If you change the pipeline, the flags, or the contract — update this primer and note it in the
day's diary. The institutional-knowledge layer is the asset; keep it current.*
