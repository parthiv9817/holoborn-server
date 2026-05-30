# HoloBorn — Engineer's User Manual

> **Purpose.** This is the operational handbook for `holoborn-server` and the two serverless GPU
> repos it drives. If you're a new engineer picking this up, read this end-to-end once, then keep it
> open as a reference. It tells you what the system is, how every layer works, how to install/run/test
> it, how the GPU handlers are built and deployed, and how to dig yourself out of the known holes.
>
> **Companion docs (read these too):**
> - `docs/PROJECT-HOLOBORN-PRIMER.md` — the *narrative* onboarding (the "why", the people, the scars). This manual is the *operational* counterpart.
> - `docs/REFINEMENT-PHASE.md` — the current phase definition + ranked backlog.
> - `diaries/YYYY-MM-DD.md` — the day-by-day record. The territory; this manual is the map.
> - `mistakes/YYYY-MM-DD.md` — the failure log. Most of the Troubleshooting section below is distilled from it.
>
> **Golden rule:** when this doc and the code disagree, **the code wins** — then fix this doc.
> Last synced to the tree: **2026-05-30** (on `main`; the decimation feature lives on a branch — see §16).

---

## 1. What HoloBorn Is (60 seconds)

A **Meta Quest 3 mixed-reality app that grows a photoreal, rigged, breathing 3D hologram of a
person from a photo — fully autonomously, no human in the loop.** Press a button on the headset,
it captures you, ~5–8 minutes later a textured avatar of you materializes in the room through a
cinematic "spawn ritual," floor-anchored.

**This repo (`holoborn-server`) is the Mac FastAPI middleware** — the orchestrator between the
Quest headset and the cloud GPU/API services. It runs **no heavy ML itself** (MediaPipe pose
detection is the only on-Mac model); everything else is delegated to RunPod GPUs and SaaS APIs.

**North star (reframes everything):** HoloBorn is *not* a novelty avatar toy. The real product is
**digital legacy / immortality** — a conversational VR-you your descendants can talk to. The avatar
pipeline in this repo is **the BODY, and the body is essentially solved.** The unbuilt frontier is
the **MIND/voice layer**. Weigh decisions accordingly: the body is in a *refinement* phase.

---

## 2. The Three Repos (and where the work lives)

| Repo | Visibility | Role |
|---|---|---|
| **`parthiv9817/holoborn-server`** (this repo) | public | Mac FastAPI orchestrator. The brain. |
| **`parthiv9817/holoborn-quest-unity`** | public | The Quest 3 client (Unity 6, URP, OpenXR, glTFast). Renders the spawn ritual + hologram. |
| **`parthiv9817/holoborn-gpu`** | public | RunPod serverless **TRELLIS** handler (legacy single-view gen). Docker image `parthiv8421/holoborn-gpu`. |
| **`parthiv9817/holoborn-hunyuan-gpu`** | private | RunPod serverless **Hunyuan3D-2mv** handler (ACTIVE multi-view gen). |

(A fourth repo, `holoborn-quest-ue5`, is an abandoned UE5 client — see §15 history. Do not revive it.)

The GPU handler code is documented in full in **§10**.

---

## 3. Repo Map (`holoborn-server`, after the 2026-05-30 cleanup)

```
holoborn-server/
├── app/                          # the FastAPI application
│   ├── main.py                   # app factory, lifespan (loads MediaPipe + S3 client), route mount
│   ├── config.py                 # ALL settings/flags/endpoints/TRELLIS presets (pydantic-settings)
│   ├── routes/
│   │   ├── health.py             # GET /health
│   │   ├── detection.py          # POST /detect  (legacy face detection)
│   │   └── generation.py         # POST /validate-frame, /generate-multiview; GET /generate/{id}/status
│   ├── services/                 # one file per pipeline concern (see §9)
│   │   ├── frame_decoder.py      # JPEG bytes -> numpy BGR
│   │   ├── multipart_utils.py    # Unity multipart parsing (BOM/null strip, frame collection)
│   │   ├── preprocessing.py      # burst_average (numpy mean) + pick_sharpest (variance-of-Laplacian)
│   │   ├── pose_validator.py     # MediaPipe BlazePose framing check (knees+ankles visible)
│   │   ├── face_detector.py      # MediaPipe face detection (legacy /detect)
│   │   ├── portraitizer.py       # OpenAI gpt-image portrait edit (single + dual). Prompt V1->V4 history.
│   │   ├── view_synthesizer.py   # (Hunyuan path) 1 portrait -> 2x2 turnaround grid -> 4 view tiles
│   │   ├── runpod_client.py      # TRELLIS submit/poll + RunPod S3 download/delete
│   │   ├── hunyuan_client.py     # Hunyuan submit/poll (reuses runpod_client S3 + headers)
│   │   ├── meshy_client.py       # Meshy Retexture submit/poll/download + transient-retry engine
│   │   ├── meshy_animation_client.py  # Meshy Rigging + Animation submit/poll/extract
│   │   └── generation_pipeline.py     # *** THE ORCHESTRATOR: process_task() ties it all together ***
│   └── models/
│       ├── schemas.py            # detection schemas
│       └── generation_schemas.py # FramingResponse, MultiviewResponse, TaskStatusResponse, ...
├── tools/                        # standalone CLI utilities (run with .venv/bin/python)
│   ├── graft_pbr_materials.py    # re-graft PBR maps onto rigged GLB + roughness clamp (CRITICAL)
│   ├── clamp_roughness.py        # standalone roughness-floor clamp
│   ├── normalize_glb_for_quest.py# feet-at-origin + 1.7m normalize (Hunyuan->TRELLIS convention)
│   ├── inspect_glb.py            # GLB scene-graph / tri-count / material dump
│   ├── insert_eyes.py            # DEAD END (falsified 2026-05-27) — kept as a tombstone, do not use
│   ├── modify_material.py, clamp_*, gen_summoning_*  # one-off asset helpers
│   └── test_*.py                 # manual endpoint/Meshy/Hunyuan harnesses (NOT pytest)
├── tests/                        # see tests/README.md
│   ├── scripts/                  # runnable test scripts (burst-average, full pipeline, contracts...)
│   ├── inputs/                   # frozen committed fixtures (real Quest bursts, validate samples)
│   ├── outputs/                  # GITIGNORED — script outputs
│   └── captures/                 # GITIGNORED — on-device session captures
├── results/                      # GITIGNORED — live server runtime artifacts (avatars/originals/scans)
├── diaries/  mistakes/  drafts/  docs/   # institutional knowledge (see §17)
├── admin/                        # GITIGNORED — timesheets (team data, never push)
├── screenshots/  quest_outputs/  quest_screenshots/  # GITIGNORED — local media (organized by date)
├── CLAUDE.md / AGENTS.md         # original spec — STALE in places (see warning below)
├── requirements.txt
└── .env / .env.example
```

> ⚠️ **`CLAUDE.md` / `AGENTS.md` are the original spec and are stale.** They describe a single-view
> TRELLIS / gpt-image-1.5-only pipeline and the **wrong Quest input mapping**. Treat them as
> historical intent. The code + this manual + the primer are authoritative.

---

## 4. Full System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ META QUEST 3  (Unity client, deployed APK — repo: holoborn-quest-unity)        │
│   X button = burst 5-frame capture (PRIMARY); dual body+face capture supported │
│   A button = revolve scan (30 frames)                                          │
│   B button = standalone GLB test  ·  Y button = on-device ritual trigger       │
└───────────────┬───────────────────────────────────────────────────────────────┘
                │  HTTPS via ngrok (WiFi client isolation blocks LAN; Quest accepts all certs)
                │  POST /generate-multiview  (multipart JPEGs + metadata) -> task_id (instant)
                │  GET  /generate/{task_id}/status  (polled every 3s)
                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ THIS SERVER — Mac FastAPI (CPU only). One asyncio background task per job.      │
│                                                                                 │
│  1. validate framing   MediaPipe BlazePose (knees+ankles visible > 0.5)         │
│  2. pick sharpest /    pick_sharpest (variance-of-Laplacian) OR burst_average   │
│     burst-average      frames saved to results/scans/{ts}_{task_id}/            │
│  3. PORTRAITIZE        OpenAI gpt-image. single (gpt-image-1.5) OR dual         │
│                        (gpt-image-2, body+face) -> clean studio A-pose portrait │
│  4. VIEW SYNTHESIS     (Hunyuan path only) gpt-image-2: 1 portrait -> 2x2 grid  │
│                        -> 4 view tiles (front/left/back/right)                  │
│  5. 3D GEN (GPU)  ───────────────────────────────────────────────►  RunPod     │
│        USE_HUNYUAN=true  -> Hunyuan3D-2mv  endpoint itd7oz9wexb1oo  (ACTIVE)     │
│        USE_HUNYUAN=false -> TRELLIS.2-4B   endpoint pz2c4wvo2rcdw9  (legacy)     │
│        GLB written to RunPod network volume; we download via S3 API + delete    │
│        -> staging file {task_id}_trellis.glb  (plastic-looking; Quest never sees)│
│  6. MESHY RETEXTURE ──────────────────────────────────────────────►  Meshy      │
│        meshy-6, enable_pbr, 4K base color, remove_lighting, regenerated UVs      │
│        (GLB + portrait staged at public ngrok URLs so Meshy can fetch them)      │
│        -> clean PBR GLB overwrites {task_id}.glb                                 │
│  7. MESHY RIGGING ────────────────────────────────────────────────►  Meshy      │
│        retex GLB -> rigged skeleton (height 1.7m).  ⚠ rigging STRIPS PBR maps    │
│  8. PBR GRAFT + CLAMP   tools/graft_pbr_materials.py re-bakes PBR onto rigged    │
│        mesh + clamps roughness (floor 200). Atomic overwrite -> {task_id}.glb    │
│        NO Meshy animation. Aliveness is procedural (Unity RiggedAvatarBreath).   │
│  9. SERVE              static GET /avatars/{task_id}.glb over ngrok              │
└───────────────┬───────────────────────────────────────────────────────────────┘
                │  Quest downloads GLB via glTFast -> spawn ritual -> floor-anchored hologram
                ▼
        breathing PBR-textured you, in the room
```

### Graceful degradation ladder (the pipeline never hard-stops at a cosmetic step)
- No `MESHY_PUBLIC_HOST` → serve raw TRELLIS/Hunyuan **plastic** as final.
- Meshy retex fails (after transient retries) → serve plastic.
- Meshy rigging fails → serve the **retex** GLB (no skeleton; breath won't resolve, rest of ritual fires).
- Only **RunPod / download / timeout** failures mark the task `failed`.

---

## 5. The Pipeline, Function by Function

Authoritative source: **`app/services/generation_pipeline.py::process_task`**. Read it — it's the whole
system in one ~340-line file. The route (`generation.py::generate_multiview`) hands it a `task_id`,
the body JPEG (and optional face JPEG for dual mode), a `scan_dir`, and a mutable `task_record` dict.
`process_task` mutates `task_record["status"]` as it advances; `/generate/{id}/status` reads it.

Status machine (what `/generate/{task_id}/status` reports):
```
processing → portraitizing → generating → retexturing → rigging → complete
                                                                  ↘ failed
```
Quest polls every 3s and drives the spawn-ritual stages off these transitions
(`status="rigging"` triggers the Stage-2 reveal — the retex avatar *is* the Stage-2 form).

**Single vs dual capture** (decided in the route, `generate_multiview`):
- `body_*` **and** `face_*` multipart fields present → **dual mode** → `portraitize_dual` (gpt-image-2, both refs).
- Otherwise legacy `frame_*` fields → **single mode** → `burst_average` → `portraitize` (gpt-image-1.5).

**Naming quirk to know:** even on the Hunyuan path, the staging file is named `{task_id}_trellis.glb`
and `task_record["pipeline_mode"]` is set to `"hunyuan"`/`"trellis"` accordingly. Don't be confused by
the "trellis" in the staging filename — it's just the intermediate-GLB name.

---

## 6. Setup & Install

**Prerequisites**
- macOS (this was built on an **Intel** Mac — i7, x86_64. If you grab tools, get the x86_64/Intel build, not arm64).
- Python 3.11+ (the repo's `.venv` is the canonical interpreter).
- `ngrok` (a paid/reserved domain is strongly recommended — see §12).
- `node`/`npm` only if you touch decimation (`npm i -g gltfpack`; there is **no** Homebrew formula).
- Accounts/keys: **OpenAI**, **RunPod** (+ its S3 creds), **Meshy** (Pro plan).

**Install**
```bash
cd holoborn-server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then fill in the keys (see §11)
```
On boot the app auto-creates `results/{avatars,originals,scans,quest_test_uploads}` and validates the
RunPod S3 bucket via `head_bucket` (fails fast if creds are wrong).

---

## 7. Running the Server

```bash
# ALWAYS launch with explicit PYTHONPATH = repo root. Do NOT rely on the ambient cwd —
# a relaunch from the wrong directory gives "ModuleNotFoundError: No module named 'app'"
# and the tunnel 502s (mistakes/2026-05-29.md).
cd /Users/digispoc06/Documents/holoborn-server
PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

# In another terminal, expose it (use the reserved domain that matches the APK + .env authtoken):
ngrok http 8000   # or: ngrok http --domain=<reserved-domain> 8000
```

> 🔁 **pydantic-settings caches `.env` at startup.** Any `.env` edit during a session is invisible
> until you **restart uvicorn**. A live demo bombed on 2026-05-20 because of exactly this. Restart, always.

Quick smoke test:
```bash
curl -s localhost:8000/health
# {"status":"alive","frames_processed":0,"uptime_seconds":...}
```

---

## 8. The Quest API Contract (must match exactly — the APK is already deployed)

Changing any shape requires an APK rebuild + sideload. Don't.

| Endpoint | Method | Request | Response |
|---|---|---|---|
| `/health` | GET | — | `{status, frames_processed, uptime_seconds}` |
| `/validate-frame` | POST | raw JPEG bytes (`image/jpeg`) | `{framing:"good"|"bad", message, landmarks_detected, subject_center_x, subject_center_z, processing_time_ms}` |
| `/generate-multiview` | POST | multipart: `frame_0..N` **or** `body_*`+`face_*` files + `metadata` JSON string | `{status:"processing", task_id, frames_received, message}` |
| `/generate/{task_id}/status` | GET | — | `{status, progress:0-100, glb_url:"/avatars/{id}.glb", message}` |
| `/avatars/{task_id}.glb` | GET | — | static GLB binary |
| `/detect` | POST | raw JPEG or multipart `file` | `{detected, face_count, faces[], frame_number, processing_time_ms}` (legacy) |

**Quest specifics the server already handles:** Unity adds a BOM + null bytes to the `metadata`
string — `multipart_utils.clean_unity_str` strips them. Frames arrive as `starlette.UploadFile`
(not `fastapi.UploadFile`). `metadata` is a JSON array like `[{"index":0,"angle":0.0}, ...]`.

**Input mapping (verified shipped behavior — `CLAUDE.md` is WRONG):**
**A = revolve scan, X = burst 5-frame, B = standalone GLB test, Y = on-device ritual trigger.**

---

## 9. Layer-by-Layer Reference (server services)

Every file is small and single-purpose (the repo enforces a ~200-line ceiling). Quality bar:
type hints throughout, dated WHY-comments, explicit custom exceptions, graceful fallbacks.

### `frame_decoder.py`
`decode_jpeg(bytes) -> np.ndarray` (BGR). Raises `ValueError` on undecodable input. **Remember:
OpenCV is BGR end-to-end** — a spurious RGB↔BGR swap once produced blue output (mistakes/2026-05-05).

### `multipart_utils.py`
- `clean_unity_str` — strips BOM (`﻿`) + null bytes Unity appends.
- `parse_metadata` — JSON-array parse of the cleaned metadata.
- `collect_frames(form, prefix)` — pulls `{prefix}{int}` uploads in index order. Called 3×:
  `body_`, `face_`, and the legacy `frame_` default.

### `preprocessing.py`
- `pick_sharpest(frames)` — variance-of-Laplacian on a 480px grayscale downscale; returns the
  full-res sharpest JPEG. Used in **dual** mode for both bursts.
- `burst_average(frames)` — pixel-wise numpy mean (noise reduction; no alignment — the headset
  barely moves in 200ms). Used in **single** mode. Raises if frame shapes mismatch.

### `pose_validator.py`
MediaPipe BlazePose, `static_image_mode`, complexity 1. Framing is **"good"** only when **both knees
AND both ankles** have visibility > 0.5 (i.e. full body in frame). Returns hip-center x/z too.
Loaded once at app start; skipped entirely when `QUEST_TEST_MODE=true`.

### `portraitizer.py` — the keystone preprocessing step
Turns a dark Quest capture into a clean studio **A-pose** portrait on a light-grey backdrop.
- `portraitize(bytes)` — single input, `gpt-image-1.5`, `input_fidelity="high"`, 1024×1536. Uses
  **`PORTRAIT_PROMPT_V3`** (A-pose, per-limb image-space pose prose, banned-stylization vocab).
- `portraitize_dual(body, face)` — two refs, `gpt-image-2`, **`PORTRAIT_PROMPT_V4`** (face anchors
  identity, body anchors clothing/proportions). gpt-image-2 does **not** accept `input_fidelity`.
- **Prompt history (V1→V4) is preserved in the file** as constants — read it before touching prompts.
  Hard-won lessons baked in: never enumerate specific clothing items (a hardcoded "lanyard" once got
  hallucinated onto everyone — mistakes/2026-05-14); describe the *transformation*, not the output;
  always include explicit negation of unseen items.
- Insight: the portraitizer's load-bearing job is **lighting transformation**, not noise cleanup.

### `view_synthesizer.py` — (Hunyuan path only)
`synthesize_views_grid(front_portrait) -> {front,left,back,right}` PNGs. One `gpt-image-2` call
produces a **1024×1024 2×2 turnaround grid** (locked layout: TL=front, TR=left, BL=back, BR=right),
then `split_grid` crops it into four 512×512 tiles. 512 matches Hunyuan's internal MVImageProcessor
downscale exactly — no wasted detail. The grid prompt restates the "keep identical" list every call
to fight drift.

### `runpod_client.py` — TRELLIS submit/poll + the S3 layer (shared)
- `submit_job(image_b64, **extra) -> job_id` — POST `{"input":{"image_b64":...}}` to `/run`.
- `poll_until_complete(job_id)` — polls `/status/{id}` until `COMPLETED`; raises `RunpodJobError`
  on FAILED/CANCELLED/TIMED_OUT, `TimeoutError` past `RUNPOD_POLL_TIMEOUT_S`.
- `get_s3_client()` — `@lru_cache` boto3 client. **This is RunPod's S3-compatible volume API, NOT
  AWS S3:** explicit creds, `signature_version='s3v4'`, no env-var pickup. Bucket = the **network
  volume UUID**, not its display name.
- `download_glb(volume_path, local)` — S3 download + **`b'glTF'` magic-byte verify** (deletes the
  file and raises `GlbDownloadError` if it's not a real GLB).
- `delete_remote_glb(volume_path)` — frees the volume after download (skipped if
  `RUNPOD_S3_KEEP_AFTER_DOWNLOAD=true`).

### `hunyuan_client.py` — Hunyuan submit/poll
Mirrors `runpod_client` for the multi-view endpoint. **Reuses** `runpod_client._runpod_headers` and
the S3 download/delete (same API key, same volume — only the `/run` and `/status` URLs differ).
`submit_job(views)` base64-encodes each present view into `{front_b64, left_b64, back_b64, right_b64}`
(only `front` is required).

### `meshy_client.py` — Retexture + the transient-retry engine
- `submit_retexture(...)` / `poll_until_complete` / `extract_glb_url` / `download_retexture_glb`
  (also magic-byte verified). Production call uses `ai_model="meshy-6"`, `enable_pbr=True`,
  `enable_original_uv=False` (Meshy regenerates a proper UV unwrap), `remove_lighting=True`,
  `hd_texture=True` (4K base color), `target_formats=["glb"]`.
- **`run_with_transient_retry(submit, poll, ...)`** — retries the *whole* submit+poll cycle when Meshy
  returns `service_unavailable` ("temporarily unavailable, please retry"), a capacity blip that
  self-heals in ~90s. Non-transient errors (bad URL, bad input) propagate immediately — retrying
  them would fail identically. Defaults: `MESHY_MAX_ATTEMPTS=3`, `MESHY_RETRY_BACKOFF_S=12`.
- **Dummy mode:** empty `MESHY_API_KEY` → falls back to a dummy key that returns mock responses
  (`is_dummy_mode()` is true). Lets you exercise the flow without spending credits.
- `model_urls.glb` is **top-level** in Meshy's GET response — an early bug read it nested and
  silently fell back to plastic (diaries/2026-05-11).

### `meshy_animation_client.py` — Rigging (+ Animation, unused)
- `submit_rigging(model_url, height_meters=1.7)` / `poll_rigging_until_complete` /
  `extract_rigged_glb_url` (reads `result.rigged_character_glb_url`). 300s submit timeout (Meshy
  fetches the model_url upfront; a rate-limited ngrok tunnel can make that slow).
- Animation endpoints exist (`submit_animation`, `extract_*animation*`) but are **not used** —
  aliveness is procedural Unity-side. (Also: Meshy multi-clip merge is broken — single-clip only.)
- Constraints: humanoid-only, **300k face cap**, +Z forward, A/T-pose, **3-day URL expiry**
  (mirror immediately), rig = 5 credits, animation = 3 credits, ~$0.16/avatar on Pro.

### `generation_pipeline.py::process_task` — the orchestrator
Ties §5 steps together with the §4 degradation ladder. Also honors the test bypasses:
`TEST_DRY_RUN` (mark complete after saving frames, zero downstream cost), `TEST_PORTRAIT_OVERRIDE`
(feed a cached portrait, skip OpenAI), `TEST_PORTRAIT_DELAY_S` (cinematic sleep so the spawn vortex
gets its window when OpenAI is bypassed). The PBR graft (`tools/graft_pbr_materials.py`) is imported
lazily by adding the repo root to `sys.path` on first use.

---

## 10. The Serverless GPU Handlers (RunPod)

The GPU does the heavy 3D generation. There are **two** RunPod serverless endpoints, both following
the canonical RunPod pattern: the model is loaded **once at module import** (resident across jobs)
and `runpod.serverless.start({"handler": handler})` drives the worker loop. No FastAPI, no HTTP proxy
inside the container.

### 10.1 TRELLIS — `holoborn-gpu` (endpoint `pz2c4wvo2rcdw9`, legacy)

**Files:** `handler.py`, `run_inference.py`, `preprocess.py`, `Dockerfile`, `.github/workflows/docker.yml`.

**Input** (`{"input": {...}}`):
```
image_b64 | image_url            (one required)
seed=42, decimation=50000, texture_size=4096, pipeline_type="1536_cascade",
skip_enhance=false, skip_preprocess=false,
sparse_struct_guidance=8.0, sparse_struct_steps=12,
shape_slat_guidance=8.0,   shape_slat_steps=12,
tex_slat_guidance=1.0,     tex_slat_steps=12
```
**Output:** `{glb_volume_path:"outputs/<job_id>.glb", glb_size_bytes, elapsed_seconds}` — GLB written
to `/runpod-volume/outputs/<job_id>.glb`, fetched by the Mac via the RunPod S3 API.

**Pipeline (`run_inference.py`):**
1. **`preprocess.py`** on the raw BGR: CLAHE on L-channel (shadow lift) → gray-world white balance
   (kill tungsten cast) → conditional Lanczos upscale to long-edge ≥ 1500 (gives GFPGAN enough face
   pixels). (A post-rembg square auto-crop exists but is opt-in — TRELLIS already crops internally.)
2. **Enhance:** GFPGAN v1.3 (face restore) + RealESRGAN x2 (`RealESRGAN_x2plus`). Falls back to
   ESRGAN-only if no face is detected. Loaded/freed **per request** (2+ GB VRAM; TRELLIS needs headroom).
3. **Rembg:** TRELLIS's built-in BiRefNet (`pipeline.rembg_model`) → RGBA cutout, model moved on/off GPU.
4. **TRELLIS.2-4B `1536_cascade`:** three samplers (sparse-structure, shape-SLAT, tex-SLAT) with
   tunable steps/guidance; decode latents → `o_voxel.postprocess.to_glb` with `decimation_target`,
   `texture_size`, remesh on. Sampler `guidance_rescale`/`rescale_t` are hardcoded per stage.

The Mac sends `TRELLIS_PRESETS` (in `app/config.py`) as input overrides: `fast` (matches handler
defaults, 50k decimation), `demo_premium`, and `demo_max` (the locked production tune:
`shape_slat=4.0, ss_guidance=7.0, tex_slat=3.5, steps=22, decimation=200000`).

**Dockerfile highlights** (`nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04`, Python 3.11 via deadsnakes):
PyTorch 2.6 + cu124; TRELLIS deps; GFPGAN/ESRGAN chain (`--no-deps` to avoid a torch downgrade) +
the `basicsr` `functional_tensor` sed-patch (torchvision ≥0.16 removed that module); **flash-attn**,
**nvdiffrast**, **CuMesh**, **FlexGEMM** all built from source; TRELLIS.2 pinned to commit
`5565d240...` with a DINOv3-layer patch; `o-voxel` built from the TRELLIS repo. Enhancement weights
are **pre-baked** into the image (zero network on cold start). The **16 GB HF model cache lives on the
network volume** (`HF_HOME=/runpod-volume/trellis_hf_cache`, `HF_HUB_OFFLINE=1`).

### 10.2 Hunyuan3D-2mv — `holoborn-hunyuan-gpu` (endpoint `itd7oz9wexb1oo`, **ACTIVE**)

**Files:** same four. Multi-image; **geometry only** — texture is intentionally NOT generated on the
GPU (Meshy does texturing downstream), so the heavy texture CUDA extensions
(`custom_rasterizer`/`differentiable_renderer`) are **not** built → a much lighter image than TRELLIS.

**Input** (`{"input": {...}}`):
```
front_b64                         (required)
left_b64, back_b64, right_b64     (optional)
seed=12345, num_inference_steps=50, octree_resolution=512,
num_chunks=20000, guidance_scale=5.0, skip_enhance=false, skip_preprocess=false
```
> The handler defaults (octree 512, steps 50, chunks 20000) are the validated optimum. Do **not**
> raise `octree_resolution` for "more detail" — it just bloats polygon count. `guidance_scale=5.0` is
> the mv flow-matching default; don't raise it.

**Output:** identical shape to TRELLIS (same volume, same S3 fetch).

**Pipeline (`run_inference.py`):** for **each** of the 4 views — preprocess (same CLAHE/WB/upscale) →
GFPGAN+RealESRGAN → rembg (skipped if the image already has a real alpha channel). Then
**`Hunyuan3DDiTFlowMatchingPipeline`** (`tencent/Hunyuan3D-2mv`, subfolder `hunyuan3d-dit-v2-mv`,
fp16) with `image={view:img}` multi-image input → trimesh GLB. Enhancer is loaded then freed before
Hunyuan loads. The image encoder is **DINOv2-Giant @ 518×518** (512 is the octree number, not the
encoder res).

**Dockerfile highlights** (same CUDA base, Python 3.10): clones `Tencent-Hunyuan/Hunyuan3D-2`, installs
geometry deps only; same GFPGAN/ESRGAN chain + sed-patch; **bakes the Hunyuan-2mv fp16 shape
safetensors into the image** via `snapshot_download` (downloads, not loads — loading the 5 GB pipeline
would OOM the ~16 GB CI runner), then goes fully offline (`HF_HUB_OFFLINE=1`). **Self-contained: no
network volume needed for weights** — cold start is just the image pull.

### 10.3 Building & deploying a GPU image
CI is `.github/workflows/docker.yml`: **push to `main` → GitHub Actions builds and pushes to Docker
Hub** (`docker/build-push-action`, gha cache). TRELLIS tags `parthiv8421/holoborn-gpu:v4` + `:latest`.
Then in the RunPod console, point the serverless endpoint at the new image tag. The TRELLIS CI build
runs ~45 min (flash-attn/nvdiffrast/CuMesh compile from source).

**Local dev runs** (both repos support bare CLI):
```bash
# TRELLIS
python run_inference.py input.jpg out.glb --seed 42 --decimation 200000
# Hunyuan (multi-view)
python run_inference.py --front f.png --left l.png --back b.png --right r.png -o out.glb
python run_inference.py --front f.png --skip-enhance --cpu-offload    # 8GB-safe geometry-only
```

---

## 11. Configuration Reference (`app/config.py` + `.env`)

Fill `.env` from `.env.example`. Never commit `.env` (it's gitignored). Key settings:

| Var | Default | What it does |
|---|---|---|
| `OPENAI_API_KEY` | — | OpenAI key for the portraitizer + view synthesizer. |
| `GPT_IMAGE_MODEL` | `gpt-image-1.5` | single-input portrait model. |
| `GPT_IMAGE_MODEL_DUAL` | `gpt-image-2` | dual-input (body+face) portrait + view-grid model. |
| `RUNPOD_API_KEY` | — | RunPod bearer token (shared by TRELLIS + Hunyuan). |
| `USE_HUNYUAN` | `false` (code) | **THE gen-path switch.** `true` → Hunyuan `itd7oz9wexb1oo`; `false` → TRELLIS `pz2c4wvo2rcdw9`. **grep this before assuming which model runs.** Production `.env` sets it `true`. |
| `RUNPOD_ENDPOINT_ID` / `GPU_SERVER_URL` | TRELLIS | TRELLIS endpoint. |
| `RUNPOD_HUNYUAN_ENDPOINT_ID` / `GPU_HUNYUAN_SERVER_URL` | Hunyuan | Hunyuan endpoint. |
| `RUNPOD_S3_*` (access/secret/endpoint/bucket/region) | — | RunPod **volume** S3 creds. Bucket = volume **UUID**. |
| `RUNPOD_POLL_TIMEOUT_S` | `600` | raise to ~1500 in dev to survive cold starts. |
| `MESHY_API_KEY` | — | empty → **dummy mode** (mock responses). |
| `MESHY_PUBLIC_HOST` | — | the **ngrok host** that serves staged GLBs/portraits back to Meshy. Empty → skip retex, serve plastic. Read from `.env`, never hardcode. |
| `MESHY_MAX_ATTEMPTS` / `MESHY_RETRY_BACKOFF_S` | `3` / `12` | transient-retry tuning. |
| `QUEST_TEST_MODE` | `true` | skip MediaPipe BlazePose on `/validate-frame` (returns "good"). Does **not** affect the real pipeline anymore. |
| `TEST_DRY_RUN` | `false` | accept upload, save frames, mark complete — **zero** downstream cost. Verify Quest wire format without burning credits. |
| `TEST_PORTRAIT_OVERRIDE` | "" | path to a cached portrait → skip OpenAI. |
| `TEST_PORTRAIT_DELAY_S` | `0` | cinematic sleep before RunPod submit (gives the vortex its window when OpenAI is bypassed). |

`TRELLIS_PRESETS` (`fast`/`demo_premium`/`demo_max`) also live in `config.py`.

---

## 12. Operations & Footguns

### ngrok — the recurring footgun
- Free-tier domains **churn** whenever an account hits its 1 GB/mo bandwidth cap. Each full e2e
  pulls ~70 MB (burst upload + portrait + ~22 MB retex to Meshy + ~44 MB rigged GLB to Quest), so a
  free account dies in ~14 e2e runs. The domain has rotated through **9+** names.
- **NEVER hardcode an ngrok domain.** Always read `MESHY_PUBLIC_HOST` from `.env`.
- Before `ngrok http 8000`: verify the **APK's hardcoded URL** matches the **reserved domain owned by
  the authtoken in `.env`** — a mismatch silently routes traffic to the wrong tunnel.
- A domain change → **APK rebuild + sideload** (Unity serializes the URL into the scene).
- Decision (2026-05-29): **stay on ngrok through dev**; revisit a permanent tunnel (~$10 domain or
  Tailscale Funnel) only at deployment, with founder greenlight.

### RunPod
- Keep `min_workers=0` during dev (cost). **Bump min AND max to 1 together** ~30 min before a live
  demo (a `workersMax=0` trap will silently keep you cold), then fire **one throwaway warmup job** to
  flush the HF cache / eat the cold start. TRELLIS cold ≈ 9 min / warm ≈ 91 s; Hunyuan cold ≈ 16 min
  (throttled pool) / warm ≈ 148 s.
- Before cancelling a "stuck" queued job, check **`executionTime`** in the status payload — if it's
  > 0 the worker has it; let it run (a cancelled-too-early job cost a real e2e on 2026-05-14).

### Meshy
- Pro plan is **active** (~$0.16/avatar). Mirror result URLs immediately (3-day expiry).
- Roughness clamp floor is **200** (Meshy's retex backend regressed ~45% glossier on 2026-05-15;
  `graft_pbr_materials.py` clamps the metalRough G-channel to defend against it).

---

## 13. Testing

See `tests/README.md` for the full layout. The short version:

```bash
source .venv/bin/activate

# Offline burst-average sanity (no network, no GPU)
python tests/scripts/test_burst_average.py

# RunPod end-to-end with a fixture input (~5-9 min cold, ~$0.55)
python tests/scripts/test_runpod_manual.py [path/to/portrait.png]
```
- `tests/inputs/` — **frozen, committed** fixtures (real Quest bursts, validate samples). Promote a
  good runtime sample with `cp -r results/... tests/inputs/<name>/ && git add`.
- `tests/outputs/` + `tests/captures/` — **gitignored** scratch.
- `results/` is owned by the **live server** — don't put test artifacts there.
- Unity side has 24 EditMode NUnit tests (cube/vortex/silhouette) + a 33-test spawn state machine.
- `tools/test_*.py` are **manual** harnesses (Meshy retex, Meshy rigging, Hunyuan endpoint, view grid)
  — run them directly, they are not collected by pytest.

> Hit the **real endpoint** before claiming a phase is done — import + schema validation passing is
> not "done" (mistakes/2026-05-08). And **test fallbacks by inducing failure** — a fallback once
> never fired because it caught `TimeoutError` but the real error was `httpx.ReadTimeout`
> (mistakes/2026-05-14). Catch the parent `httpx.HTTPError`.

---

## 14. Tools Reference (`tools/`, run with `.venv/bin/python`)

| Tool | What it does |
|---|---|
| **`graft_pbr_materials.py`** | **Critical.** Re-grafts the retex GLB's full PBR stack (baseColor/metalRough/normal/emissive) onto the rigged GLB (Meshy rigging strips them), and clamps the metalRough **G-channel to a floor (default 200)** + zeroes metallic. Pure-stdlib GLB binary surgery. Used inside the pipeline and standalone. |
| `clamp_roughness.py` | Standalone version of just the roughness clamp. |
| `normalize_glb_for_quest.py` | Rewrites positions to feet-at-origin + 1.7m tall (Hunyuan outputs a normalized cube; TRELLIS/Unity expect feet-at-origin meters). Use when dropping a raw Hunyuan GLB into a Y-test slot. |
| `inspect_glb.py` | Scene-graph / tri-count / material / `extensionsUsed` dump. **Always check `extensionsUsed` after decimation.** |
| `insert_eyes.py` | **DEAD END — do not use.** Raw eyeball-sphere insertion was falsified 2026-05-27 (the fused shell has no eye aperture/lids → buries or bug-eyes). Eyes are foundation-model-bound. |
| `test_hunyuan_endpoint.py`, `test_meshy_retex.py`, `test_meshy_rigging.py`, `test_view_grid.py` | manual integration harnesses. |
| `gen_summoning_sigil.py`, `gen_summoning_audio.py`, `modify_material.py`, `prepare_animated_test_glb.py` | one-off asset/experiment helpers. |

---

## 15. How We Got Here (the scars — abridged; full arc in the primer + diaries)

- **2026-04-11** — A Phase-1 Unity baseline already worked (36s MP4 proof: avatars anchored in two rooms).
- **2026-04-27** — Mac backend **rebuilt from scratch** after the prior disk died with unpushed code.
  Lesson in blood: **push company code to a remote every session.**
- **late Apr – 2026-05-04** — UE5 migration attempted for photoreal (Nanite/MetaHuman). **Died** on an
  unfixable UE 5.5.4 cooker regression (`FScreenPSsRGBSourceMipLevelArray` missing for
  `VULKAN_ES31_ANDROID`) across 10+ builds; zero documented Intel-Mac+UE5+Quest successes globally.
- **2026-05-05** — **Unity pivot** locked (Vipin, hard EOW deadline). APK forensics → stack rebuilt.
- **2026-05-06 → 14** — TRELLIS + Meshy era: PBR-on-Quest (Resources/ placeholder fix), A-pose
  canonical-pose requirement, Meshy retex/rig/graft pipeline, **first full real-backend e2e (05-14)**.
- **2026-05-15 (diagnosed 05-25)** — Meshy silently regressed retex (~45% glossier) → shipped the
  defensive **roughness clamp**.
- **2026-05-23** — **Pivot to Hunyuan3D-2mv multi-view** (hair is a *geometry* problem, not texture;
  Hunyuan's multi-image input fixes unseen-angle geometry). New endpoint, 2-step portraitizer.
- **2026-05-27** — **Development cycle declared COMPLETE.** Full autonomous e2e validated;
  council-graded a legitimate autonomous-MR-embodiment POC. Entered the **refinement phase**.

---

## 16. Current State & Roadmap (as of 2026-05-30)

**Branch state.** `main` is the production line. **Decimation lives on
`feat/decimation-pre-rigging`, NOT merged.** That branch adds `app/services/decimation.py`
(`decimate_glb()`, graceful-fail-returns-False) + config (`decimate_before_rigging` default **OFF**,
`decimation_ratio=0.18`, `gltfpack_bin`), inserted in `process_task` **between retex download and
rigging submit**.

**The decimation recipe (Quest-validated 2026-05-29):**
```
gltfpack -i {retex}.glb -o {out}.glb -si 0.18 -noq
# ~452k -> ~81k tris (-82%). Kills the live-passthrough walk-around stutter.
```
> 🔑 **`-noq` is mandatory** for glTFast 6.18 — default quantization injects `KHR_mesh_quantization` +
> `KHR_texture_transform`, which glTFast 6.18 mis-applies → scrambled UVs. Always verify the output's
> `extensionsUsed` is clean (`tools/inspect_glb.py`). Decimation goes **pre-rigging** so skin weights
> stay clean (Meshy does not re-mesh the tri count back up). `gltfpack` installs via `npm i -g
> gltfpack` (no Homebrew formula).

**The one gate before merge:** a single full RunPod e2e of the decimation path (was blocked on ~$1
RunPod credits). After it passes: flip the flag ON, **re-measure the Unity `riggedBoundsToFeetOffset`**
(0.20 was measured on the 471k rig), merge to `main`.

**Refinement backlog (ranked, from `docs/REFINEMENT-PHASE.md`):**
1. **Decimation** — basically done (see above); just the e2e gate + merge remain.
2. **Quality ceiling (hair / eyes / identity)** — **foundation-model-bound**, not param-tunable.
   Needs its own strategy (A/B Tripo/Rodin, targeted material work, or deliberate stylization). Eye
   *geometry* insertion is a confirmed dead-end; texture-repaint is the only near-term route.
3. **Grounding (contact shadow)** — Unity-side, high presence ROI.
4. **Idle life (breath/sway)** — Unity-side, "alive not mannequin."
5. **Eyes/hair shaders** — Tier 2, needs part-segmentation infra first.

**Known open risks (from the 2026-05-26 premortem):** never tested on a real external user; no
falsifiable "good enough" bar; bus factor of one; the moat is rented glue (Meshy/RunPod). Texture
size is still ~33 MB (two 4K maps; KTX2 needs KtxUnity + an APK rebuild). ngrok churn is a chronic
dev bottleneck. The **"soul phase"** (persona → voice clone → conversational mind) is the next
mountain and is unbuilt.

**Working agreement for refinement:** iterate on the existing build; every change is **Y-testable**
(backend = GLB swap into `test.glb`/`test_retex.glb`/`test_rigged.glb` — **all three**; Unity =
rebuild). **Do NOT break the autonomous / no-human-in-the-loop principle** — no per-avatar manual
fixes (it kills the moat and the solo workload).

---

## 17. Where To Look / Conventions

- **Pipeline truth:** `app/services/generation_pipeline.py`. **Flags/endpoints/presets:** `app/config.py`.
- **Narrative onboarding:** `docs/PROJECT-HOLOBORN-PRIMER.md`. **Current phase:** `docs/REFINEMENT-PHASE.md`.
- **The real story:** `diaries/YYYY-MM-DD.md` (complete through 2026-05-27; the 05-23 Hunyuan-pivot
  detail lives in the separate Alienware repo). **The failure log:** `mistakes/YYYY-MM-DD.md`.
- **Research depth:** `drafts/` (cross-AI second opinions, war plans) + `docs/superpowers/specs/`.
- **GPU repos:** `holoborn-gpu` (TRELLIS) and `holoborn-hunyuan-gpu` (Hunyuan) on GitHub (`parthiv9817`).

**Working norms** (full list in the primer §9): never auto-commit — wait for explicit approval;
brick-by-brick single-task focus on the critical path; WebSearch named errors/codes *first*, before
AI second opinions; ask for env-specific config upfront (no `YOUR-X-HERE` placeholders); edit
file-based assets (Unity YAML) directly rather than clicking through the Editor; `adb logcat -d |
grep` (never `-c`); founder messages in a professional register.

---

*If you change the pipeline, the flags, the GPU contract, or the API shapes — update this manual and
note it in the day's diary. The institutional-knowledge layer is the asset; keep it current.*
