# Hunyuan3D-2mv RunPod Deployment — Mac/holoborn-server Handoff (Death Note)

**Date:** 2026-05-23 (evening, after the Alienware session)
**Author session:** Parthiv + Claude (Opus 4.7) on the **Alienware** (Windows + WSL2 Ubuntu 24.04)
**Target reader:** Future-Claude on **Parthiv's Mac**, working in `holoborn-server`.
**Relates to:** `2026-05-23-hunyuan-pivot-alienware-handoff.md` (the pivot doc that sent work TO the Alienware). This is the REVERSE handoff — what came back.

---

## 0. Read this first

There was a ~7-hour session on the Alienware on 2026-05-23. It took the Hunyuan3D-2mv
pivot from "is the GPU even 8GB?" to a **live, validated RunPod serverless endpoint**.
The geometry stage (TRELLIS → Hunyuan) is now deployed and proven end-to-end. **Your job
on the Mac is the upstream + integration work** described in Section 4 — specifically a
**pipeline change in the portraitizer** (single image → multi-view) and wiring
holoborn-server to call the new endpoint.

Everything below is load-bearing. The single most important new fact:
**the new Hunyuan endpoint takes 4 images (front/left/back/right), not 1.**

---

## 1. What was built on the Alienware (the GPU side, DONE)

A new repo + RunPod serverless endpoint that replaces TRELLIS's geometry stage with
Hunyuan3D-2mv multi-view, while keeping the rest of the pipeline (Meshy, Quest) untouched.

- **New GPU repo:** `parthiv9817/holoborn-hunyuan-gpu` (private, GitHub) — mirrors the
  `holoborn-gpu` (TRELLIS) structure: `handler.py`, `run_inference.py`, `preprocess.py`,
  `Dockerfile`, `.github/workflows/docker.yml`.
- **Docker image:** `parthiv8421/holoborn-hunyuan-gpu:latest` (~15GB, weights baked in).
  Built by GitHub Actions CI/CD (push to main → build → Docker Hub), same pattern as TRELLIS.
- **The GPU pipeline:** for each of the 4 input views → **GFPGAN + RealESRGAN enhance**
  (same GAN stack as TRELLIS) → rembg → **Hunyuan3D-2mv multi-image** → geometry GLB.
  Texture is NOT generated on the GPU (geometry-only); **Meshy retexture stays downstream**,
  exactly as today.
- **Weights are baked into the image** (not on a network volume). The 2mv fp16 shape model
  (~5GB, DINOv2-giant encoder bundled in the safetensors) is downloaded at *build* time via
  `snapshot_download` and runs offline at runtime → zero cold-start weight download.

### The endpoint (LIVE, validated)
- **Endpoint ID:** `itd7oz9wexb1oo`  (name: `holoborn-hunyuan`)
- **Run URL:** `https://api.runpod.ai/v2/itd7oz9wexb1oo/run`
- **Status URL:** `https://api.runpod.ai/v2/itd7oz9wexb1oo/status/{job_id}`
- **GPU:** `ADA_24,ADA_32_PRO,ADA_48_PRO` (mirrors TRELLIS) · **min 0 / max 1** (dev)
- **Network volume:** `4tjtz8txf8` (the SAME `holoborn-weights` volume TRELLIS uses) — the
  output GLB is written to `outputs/<job_id>.glb` on it, so your existing
  `runpod_client.download_glb()` fetches it via S3 with **zero config change** (same bucket).
- **Cold start:** ~219s (15GB image pull, one-time per host) + ~115s processing.
  Warm worker: ~115s. (Bump min-workers to 1 ~30min before a demo to pre-pull.)

### Endpoint I/O contract
```jsonc
// REQUEST  POST /run
{ "input": {
    "front_b64": "<base64 PNG/JPEG>",   // required
    "left_b64":  "<...>",               // optional
    "back_b64":  "<...>",               // optional
    "right_b64": "<...>",               // optional
    // optional params (defaults are the validated optimum):
    "octree_resolution": 512,           // quality ceiling; higher = polygon bloat, not detail
    "num_inference_steps": 50,          // 60 = marginal bump, safe on 24GB
    "guidance_scale": 5.0,              // Tencent's mv default; do NOT raise (flow-matching artifacts)
    "num_chunks": 20000,                // memory knob, quality-neutral
    "seed": 12345,
    "skip_enhance": false,              // set true to bypass GFPGAN+ESRGAN
    "skip_preprocess": false
} }

// RESPONSE (job output when COMPLETED)
{ "glb_volume_path": "outputs/<job_id>.glb",  // fetch via existing S3 download_glb
  "glb_size_bytes": 10043108,
  "elapsed_seconds": 114.93 }
```

**Validated 2026-05-23:** a real 4-view job ran COMPLETED in 114.93s compute, produced a
10MB valid GLB, written to the volume, fetched back via S3 (`magic=b'glTF'`). The full
round trip works.

---

## 2. The optimal geometry settings (already the defaults)

Don't "crank to max" — these ARE the max-*validated* settings; higher is worse:
- **octree_resolution = 512** is the ceiling. It's the marching-cubes grid; the latent has
  fixed info content, so >512 just oversamples a smooth field = more polygons, bigger GLB,
  no real detail (and we decimate for Quest anyway).
- **guidance_scale = 5.0** is the mv flow-matching default. The "7.5" seen online is for the
  OLDER DiT demo, not this model — raising it risks over-guidance artifacts.
- **num_inference_steps = 50** is near saturation. 60 is a safe marginal bump on 24GB.
- **The real quality lever is INPUT VIEW QUALITY, not Hunyuan params** (council Section 14:
  "input quality matters MORE than the reconstruction model"). See Section 3.

---

## 3. KEY FACT: Hunyuan downscales every view to 512×512

Verified from `hy3dgen/shapegen/preprocessors.py`:
- `MVImageProcessorV2` (config `size: 512`) runs `cv2.resize(image, (512, 512))` on EVERY
  view (`load_image`, line ~100), unconditionally.
- So feeding views larger than 512px gains **nothing** at the conditioning stage — they get
  downsampled to 512 before the model sees them. (Nuance: the DINOv2 encoder targets 518px
  and interpolates internally, but the processor hard-caps at 512 first.)

**Implication:** this is what makes the turnaround-grid idea (Section 5) viable, not a
quality compromise — ~512px grid tiles sit right at the model's input resolution.

---

## 4. THE PIPELINE CHANGE you need to make (Mac side)

Today the portraitizer produces **ONE front A-pose portrait** (single-image TRELLIS).
The new Hunyuan endpoint needs **4 views: front + left + back + right**. So the Mac flow
becomes:

```
Quest capture
  → portraitize → clean FRONT A-pose portrait        (existing portraitizer, prompt is FINE as-is)
  → view-gen    → left / back / right                (NEW step — see Section 5)
  → POST 4 images to itd7oz9wexb1oo/run              (NEW: multi-image input, not image_b64)
  → poll /status, get glb_volume_path
  → download_glb() via S3                            (EXISTING, unchanged — same volume/bucket)
  → Meshy retexture                                  (EXISTING, unchanged)
  → serve to Quest                                   (EXISTING)
```

**Concrete code changes in holoborn-server:**
1. **`runpod_client.submit_job()`** currently sends `{"input": {"image_b64": ...}}` (single).
   Add a Hunyuan variant that sends the 4-image contract (Section 1) to the new endpoint.
   Keep the TRELLIS one intact (don't break the live pipeline).
2. **Add the view-gen step** (Section 5) — synthesize left/back/right from the front portrait.
3. **The FRONT portraitizer prompt does NOT need changing** — `PORTRAIT_PROMPT_V3/V4` already
   produce the clean front A-pose Hunyuan wants. It's the *view-gen* prompts that are new.
4. New endpoint config: point the Hunyuan path at `itd7oz9wexb1oo` (the TRELLIS endpoint
   `pz2c4wvo2rcdw9` stays for fallback/A-B).

---

## 5. View-gen: the two approaches (and what to TEST on the Mac)

gpt-image-2 **cannot** produce 4 different-angle images in one call natively (`n` only gives
*variations of the same prompt*, not different angles). Two real options:

### Approach A — separate calls (PROVEN on Alienware today)
4 calls: portraitize front, then 3 gpt-image-2 `images.edit` calls (left/back/right) using
the front as the reference. Validated — produces consistent identity/wardrobe, and the 180°
back view worked. Downside: 4 calls (~$0.57) and a *pose-drift* risk (in testing, arms were
out ~30-40° in front but dropped to the sides in the profiles — inconsistent pose across
views slightly caps reconstruction quality).

The view-gen prompt structure (from the Alienware's `gen_views.py`, follows OpenAI's
official gpt-image prompting guide — labeled segments, "change only the camera angle",
restate the preserve-list every call):
```
SUBJECT: one specific real person, A-pose, seamless near-white studio backdrop.
CHANGE (camera angle only): re-photograph from {LEFT profile 90° / REAR 180° / RIGHT profile 90°}.
  ...explicit per-view directive (what the camera sees, face visible or not)...
  "Rotate the viewpoint around the person — do not redesign or replace the person."
KEEP EXACTLY THE SAME (do not redesign the character):
  identity / wardrobe / A-pose / framing / lighting / near-white bg  (full list, every call)
OUTPUT: photorealistic documentary, no stylization, no watermark.
```
Use `gpt-image-2` (NOT `input_fidelity` — that param doesn't apply to gpt-image-2; it's
high-fidelity by default per OpenAI's guide).

### Approach B — turnaround GRID (CHEAPER + more consistent; NEEDS isolated testing — Parthiv's call to test on Mac)
ONE gpt-image-2 call → one image that's a 2×2 grid (front/left/back/right tiles of the same
person) → split into 4 programmatically. **1 call (~$0.19) instead of 4, and views are more
consistent because generated jointly.** Resolution is fine because Hunyuan downscales to 512
anyway (Section 3) — each ~512px tile is enough.

**The verification this needs (do it isolated, on the Mac, with rich inputs):**
1. Does gpt-image-2 reliably produce a **cleanly separable** 2×2 grid (consistent cell
   boundaries, no bleed)?
2. Does it **nail each angle** distinctly (true left/back/right, not 4 near-fronts)?
3. Is **identity/pose consistent** across the 4 tiles (better than separate calls?)?
4. Does the resulting **Hunyuan geometry** match or beat the separate-calls geometry?
Only if all four hold do we switch to the grid. Otherwise stay on separate calls.

---

## 6. What's validated vs NOT

**Validated (Alienware):**
- Hunyuan-2mv multi-view geometry on real human, on the 8GB card and on RunPod 24GB.
- Full GPU pipeline: GAN-enhance 4 views → Hunyuan → GLB.
- RunPod endpoint end-to-end: 4 imgs → GLB on volume → S3 fetch (valid glTF).
- CI/CD: push → build → Docker Hub.

**NOT yet done (your work):**
- Mac-side view-gen integration (the new step).
- The turnaround-grid approach (Section 5B) — untested.
- The actual **hair/eye geometry verdict** — inspect the white-clay geometry of a difficult
  subject (medium-long hair, visible eyes) vs the TRELLIS baseline. That's the original
  reason for the whole pivot and it's still open.
- Whether the synthesized-view pose-drift hurts enough to warrant real multi-angle photos.

---

## 7. Gotchas learned the hard way (so you don't repeat them)

- **CI build OOM:** baking weights by *loading the model* OOM-kills the ~16GB Actions runner.
  We bake via `snapshot_download` (downloads files, ~zero RAM) instead. Don't `from_pretrained`
  at build time.
- **CI disk:** the CUDA image needs a `jlumbroso/free-disk-space` step or it hits `Errno 28`.
- **GitHub release flakiness:** the GAN-weight `wget`s need retry flags (`--tries`,
  `--retry-on-http-error=429,500,502,503,504`) — CI IPs get rate-limited.
- **gpt-image-2:** no `input_fidelity`; `n` ≠ different angles; one call = one image.

---

## 8. Repos / artifacts
- GPU repo: `parthiv9817/holoborn-hunyuan-gpu` (private)
- Image: `parthiv8421/holoborn-hunyuan-gpu:latest`
- Endpoint: `itd7oz9wexb1oo` · Volume: `4tjtz8txf8` (shared with TRELLIS)
- The Alienware working dir (if Parthiv references it): `~/holoborn-hunyuan-gpu` in WSL —
  contains `gen_views.py` (the view-gen prompts) + `test_endpoint.py` (the 4-image test).

## 9. The single sentence
**Wire holoborn-server to: portraitize the front, synthesize 3 more views (test the grid
approach first), POST all 4 to `itd7oz9wexb1oo`, fetch the GLB via the existing S3 path,
hand it to Meshy — then finally judge the hair/eye geometry vs TRELLIS.**
