# Project HoloBorn — Technical Brief & Second-Opinion Request

**Author:** Parthiv (associate AI engineer, working solo on this project)
**Date:** 2026-05-06
**Audience:** ChatGPT / Gemini — please review and offer alternative perspectives
**Goal:** Stress-test architectural decisions and surface ideas I may have missed before EOW demo

---

## TL;DR

HoloBorn is a Meta Quest 3 mixed-reality app that turns a single passthrough-camera capture of a real person into a photorealistic 3D avatar that materializes as a hologram in their physical room within ~3-5 minutes. End-to-end pipeline shipping today (2026-05-06): Quest → Mac FastAPI → RunPod serverless GPU (TRELLIS.2-4B) → S3 → Mac → Quest. Full-PBR avatar rendering verified working tonight on Quest 3 in MR passthrough.

**Two features to ship before EOW (2026-05-08 to 10):**
1. Avatar animation (Meshy Rigging API, replacing the current static mesh)
2. UI polish to "premium VR product" standard per founder ask

I'd appreciate alternative architectural ideas, premium-VR-UX patterns I might have missed, and any sharp critiques of the choices below.

---

## 1. What HoloBorn does

User experience flow:
1. User wears Quest 3 in MR passthrough mode
2. Points headset at a real person standing in the room
3. Presses **A button** → 30-frame revolve scan as user walks around subject in a circle (validation gate first via MediaPipe BlazePose — knees + ankles must be visible) **OR** **X button** → 5-frame burst capture from same position (~200ms window)
4. App uploads frames to local Mac backend
5. Mac backend averages burst frames (numpy mean), portraitizes via GPT Image 1.5 (currently blocked on billing — falling back to raw burst), submits to RunPod TRELLIS.2-4B endpoint
6. ~3-5 min later, GLB lands on RunPod S3 → Mac downloads → serves to Quest
7. Quest downloads GLB via glTFast, spawns it 1.5-2m in front of user, scaled to ~1.7m, feet on floor, facing user
8. Hologram of the captured person appears in the user's actual room

**Demo deliverable:** 60-90 second MP4 of the full flow, captured EOW.

---

## 2. Current architecture (verified working as of 2026-05-06 EOD)

```
┌─────────────────────────┐
│ Quest 3 (Unity 6.4.5f1) │  Meta XR Core SDK 201.0.0, MR Utility Kit, glTFast 6.18, URP, Vulkan
│ ScanController.cs       │  A=revolve, X=burst, B=GLB-load test (this session's brick)
│ TestGlbLoader.cs        │  glTFast LoadGltfBinary + InstantiateMainSceneAsync + URP shader fix
│ TagAlongCanvas.cs       │  Lerp HUD canvas to head + offset (-0.3, -0.1, 1.0)
│ BypassCertificate.cs    │  ngrok TLS cert handler (dev only)
└────────────┬────────────┘
             │ HTTPS over ngrok (free tier, perm domain)
             │ - POST /validate-frame  (raw JPEG, BlazePose check)
             │ - POST /generate-multiview (multipart 5 or 30 JPEGs + JSON metadata)
             │ - GET  /generate/{task_id}/status
             │ - GET  /avatars/{task_id}.glb
             ▼
┌─────────────────────────┐
│ Mac (FastAPI on Intel)  │  Python 3.11, pydantic-settings, MediaPipe (CPU only)
│ - face_detector.py      │  MediaPipe Face Detection
│ - pose_validator.py     │  BlazePose (knees + ankles >0.5 visibility)
│ - preprocessing.py      │  Burst-averaging (numpy mean, ~4.95 MAE @ 5 frames)
│ - portraitizer.py       │  GPT Image 1.5 (currently 400 billing_hard_limit — bypass active)
│ - runpod_client.py      │  Submit job + poll + S3 GLB fetch via boto3
└────────────┬────────────┘
             │ POST /v2/{endpoint_id}/run  (RunPod serverless API)
             │ Auth: Bearer token
             │ Input: { "image_b64": "<base64 JPEG>" }
             ▼
┌────────────────────────────────────────┐
│ RunPod Serverless (RTX 4090)           │  Endpoint: pz2c4wvo2rcdw9
│ Docker: parthiv8421/holoborn-gpu:latest│  Network volume: holoborn-weights
│ ~3 min cold start, ~3 min compute      │
│                                        │
│ handler.py → run_inference.py:         │
│  1. preprocess_raw (CLAHE+WB+upscale)  │
│  2. GFPGAN + RealESRGAN x2 (face+bg)   │
│  3. RMBG (BiRefNet) cutout             │
│  4. TRELLIS.2-4B 1536_cascade          │
│     SAMPLER_PARAMS (hardcoded today):  │
│       - sparse_struct: steps=12,       │
│         guidance=8.0                   │
│       - shape_slat: steps=12,          │
│         guidance=8.0  ← high           │
│       - tex_slat: steps=12,            │
│         guidance=1.0  ← low            │
│  5. decode latents → to_glb            │
│     (decim=50k, texture=4096px)        │
│  6. Write to /runpod-volume/outputs/   │
│     <job_id>.glb                       │
└────────────────┬───────────────────────┘
                 │ S3 fetch (boto3, RunPod's S3 API)
                 │ Bucket: holoborn-weights
                 ▼
              Mac serves /avatars/{task_id}.glb statically → Quest downloads via glTFast
```

**Empirically verified today:**
- Network: 32MB GLB downloads from `https://unphilologic-unalphabetized-terrance.ngrok-free.dev/avatars/test.glb` in ~5s
- glTFast parse: passes magic-bytes check, full mesh + textures imported
- URP shader stripping issue: SOLVED via Resources/ folder placeholder Materials referencing `Shader Graphs/glTF-pbrMetallicRoughness` and `Shader Graphs/glTF-pbrSpecularGlossiness` (canonical Unity glTFast docs approach — Unity bundles all `Resources/*` assets + their shader deps regardless of static analysis)
- Scale + floor-align: combined-renderer-bounds based scaling to fixed 1.7m, offset by `bounds.min.y` for feet-on-floor
- HUD repositioning: TagAlongCanvas with `offset = (-0.3, -0.1, 1.0)` — left-of-view, doesn't block avatar
- Avatar render: full PBR (skin tones, blue checkered shirt, jeans, lanyard with ID card visible) standing in user's office in passthrough — same quality bar as the legacy build's reference shot

---

## 3. Stack details

| Layer | Tech | Version |
|---|---|---|
| Quest app engine | Unity URP | 6000.4.5f1 (Unity 6.4 LTS) |
| XR | Meta XR Core SDK | 201.0.0 |
| Passthrough | Meta MR Utility Kit | 201.0.0 |
| GLB loader | `com.unity.cloud.gltfast` | 6.18.0 |
| Scripting backend | IL2CPP | (Vulkan, ARM64) |
| Mac backend | FastAPI | latest |
| Pose validation | MediaPipe BlazePose | 0.10.x |
| Face detection | MediaPipe | 0.10.x |
| Portraitizer | OpenAI GPT Image 1.5 | (blocked on billing) |
| 3D generation | Microsoft TRELLIS.2-4B | (HuggingFace `microsoft/TRELLIS.2-4B`) |
| Face restoration | GFPGAN v1.3 | |
| Upscaling | RealESRGAN x2plus | |
| Background removal | RMBG / BiRefNet | |
| GPU host | RunPod serverless | RTX 4090 |
| Storage | RunPod S3-compatible | |
| Tunnel (dev) | ngrok free tier | (perm domain) |

**Three GitHub repos**: `parthiv9817/holoborn-server` (Mac), `parthiv9817/holoborn-quest-unity` (Quest app), `parthiv9817/holoborn-gpu` (RunPod Docker handler). All public.

---

## 4. What's shipping pre-EOW (the two open features)

### Feature A: Avatar animation (replacing static mesh)

**Founder ask:** *"The 3D guy should feel like it's living, not standing like a duck."*

**Constraint:** TRELLIS.2 outputs static textured PBR meshes only — no skeleton, no skin weights, no animations (CVPR'25 paper + HF model card both confirm).

**Chosen approach:** **Meshy Rigging API** (`POST /openapi/v1/rigging`):
- Input: textured humanoid GLB (.glb) — exact match for TRELLIS output
- Output: rigged GLB or FBX with included walking + running animations
- ~17s processing per task
- 5 credits per task (~$0.10 ballpark)
- 300k face limit (TRELLIS GLBs typically 50-150k)
- No T-pose required (auto pose estimation)

**Pipeline placement:** between RunPod completion and Quest serve. Mac backend POSTs the static GLB to Meshy → polls → downloads rigged GLB → serves to Quest at `/avatars/{task_id}.glb` (replacing the static one).

**Quest side**: extend the spawn helper to grab the `Animator` component after `gltf.InstantiateMainSceneAsync`, call `Play("idle")`, set `clip.wrapMode = WrapMode.Loop`. glTFast doesn't auto-play animations at runtime and doesn't enable Loop Time by default — both addressable in code.

**Ripcord fallback** if Meshy integration eats time pre-demo: procedural root-transform animation in `Update()` — Y-bob at 0.3Hz (breathing rate) + ±2° sway + 0.99-1.01 scale pulse. ~30 lines, sells "alive" without rigging. Won't do head turns / pose changes, but better than mannequin pose.

**Alternatives considered + rejected:**
- **Tripo AI**: comparable but API docs less explicit, pricing opaque
- **Reallusion AccuRIG 2**: free + great quality but desktop-only, no API → can't automate in our pipeline
- **DeepMotion**: heavy/expensive, optimized for novel mocap not rigging
- **Ready Player Me**: their own avatar style, doesn't accept TRELLIS output
- **Mixamo (Adobe)**: free + huge animation library but no public API, manual web flow only

### Feature B: UI polish — "premium VR product" feel

**Founder ask:** *"Go wild — I want the UI to feel like a premium product VR app, not a tech demo."*

**Hard constraint:** HDR + Quest passthrough = passthrough renders black (Meta SDK limitation, multi-source confirmed). Default Quest passthrough setup uses Underlay mode where this conflict applies. So UI polish lives in geometry/lighting/materials/motion/audio/haptics, NOT in bloom or tone-mapping.

**Tier 1 — Demo-impact-per-effort priorities (~3 hours total):**

1. **Spawn-moment effect.** Avatar materializing with: particle dust/sparks (Unity built-in particle system) emerging from spawn point over 1-2s, dissolve shader (vertex displacement + alpha-cutoff over 1.5s), brief emissive glow plane under feet. Single biggest "wow" moment in demo.
2. **Haptic feedback.** `OVRInput.SetControllerVibration(amplitude, frequency, controller)` — one-line. Triggers on button presses, validation success/fail, spawn complete. Without haptics: passive feel. With: alive-and-responsive feel.
3. **Spatial audio cues.** Unity 3D AudioSource at world points — subtle shimmer at avatar spawn, soft chime on validate-success. Quest renders directionally — listener hears the avatar appear FROM where it appears.

**Tier 2 — HUD typography + composition:**

4. Replace default Liberation Sans TMP font with clean modern sans-serif (Inter or SF Pro from Google Fonts → TMP)
5. Glassmorphism HUD background — translucent blur material (Asset Store URP-blur shader, free) replacing solid black canvas
6. Animated text transitions on status state changes — fade out / swap / fade in (DOTween, free)
7. Type hierarchy: 36pt/600 headline + 18pt/400 body + 14pt/400 caption + ONE accent color (cyan or coral)

**Tier 3 — Avatar-side polish:**

8. Soft contact shadow under avatar feet → "weight" in the room
9. Subtle rim light catching silhouette → depth cue
10. Reflection probe baked at scene origin → PBR fabric/skin samples real-room reflections

**Skipped for v2 (post-demo):** hand-tracking pinch interactions, custom skin SSS shader, hair-card LOD shader, smooth controller laser pointer, circular progress ring loading state, avatar ambient sounds.

---

## 5. TRELLIS parameter tuning — current vs research-backed quality config

This is the third potential lever I'd appreciate sanity-checking on.

**Current state**: Local backend sends only `image_b64`. GPU handler uses hardcoded defaults:
- `decimation_target = 50,000`
- `texture_size = 4096`
- `pipeline_type = "1536_cascade"`
- `seed = 42`
- All sampler `steps = 12`
- `sparse_structure guidance = 8.0`, `shape_slat guidance = 8.0`, `tex_slat guidance = 1.0`

**Research finding** (fal.ai parameter guide + GitHub issue #92): our current sampler params are tuned for **hard-surface objects** (furniture, vehicles), not organic humans. Recommended for human avatars:
- `shape_slat guidance: 8.0 → 4.0-5.0` (high values cause over-confident geometry artifacts on faces)
- `sparse_struct guidance: 8.0 → 6.5-7.0` (more interpretive freedom for organic poses)
- `tex_slat guidance: 1.0 → 2.5-3.5` (sharper texture detail — skin, fabric, hair)
- `steps: 12 → 16-20` (diminishing returns past ~25)
- `decimation_target: 50K → 200-400K` (smoother mesh, fewer faceted artifacts)
- `texture_size: 4096` (already max)
- `pipeline_type: "1536_cascade"` (already top)
- **Multi-seed lottery: run 3-5 seeds, pick best output by visual inspection** — TRELLIS has high variance per seed, this is the single biggest "free quality" win

**Required code change**: GPU handler currently doesn't accept sampler_params overrides — uses hardcoded `SAMPLER_PARAMS` constant. Trivial patch in `holoborn-gpu/handler.py` and `run_inference.py` to plumb these from input dict. ~30 min.

**Don't-care constraints:** GLB size and processing time are irrelevant — output is written to RunPod S3, fetched by Mac, served to Quest. No mobile-bundle-size concern. Optimizing purely for visual quality.

---

## 6. EOW execution plan (today is Wed 2026-05-06)

| Day | Block | Deliverables |
|---|---|---|
| **Thu 2026-05-07 AM** | Animation pipeline | GPU handler patches + Meshy API integration in Mac backend + rigged GLB end-to-end test |
| **Thu 2026-05-07 PM** | Animation playback | Animator wiring in Unity (loop, blend), procedural fallback wired |
| **Fri 2026-05-08 AM** | UI Tier 1+2 | Spawn-moment effect, haptics, spatial audio, font swap, glassmorphism HUD |
| **Fri 2026-05-08 PM** | Avatar polish + TRELLIS retune | Tier 3 (shadow/rim/reflection probe), multi-seed lottery test with new sampler params |
| **Sat-Sun 2026-05-09/10** | Demo capture + bug fixes | MP4 recording, retake until clean, send to founder Sun PM |

**Cuts if time runs out**: procedural breathing instead of Meshy rig (saves half day), keep current font (saves 30min), skip glassmorphism (saves 30min). Floor-shape demo even with cuts is meaningfully above today's baseline.

---

## 7. Constraints & current blockers

- **Solo dev** (no teammates on this project — not vibe-coding, just one person handling Quest C# + Mac Python + RunPod Docker + research + memory + ops).
- **Intel i7-1068NG7 Mac (x86_64)** for development — Unity IL2CPP cold builds are 30-90 min on this hardware. Build cycle cost shapes iteration discipline.
- **EOW deadline**: 2026-05-08 to 10. Founder set this hard, no slip.
- **OpenAI billing hard-limited since 2026-05-04** — `400 billing_hard_limit_reached` on any image generation call. Blocks the GPT Image 1.5 portraitizer step. Ticket pending with TL Tapasya for ~3 days, no response. Today's escalation path: parallel ping to founder. Demo Plan B is raw-burst → RunPod (proven working today, just slightly muddier materials than portraitizer-input would give).
- **No production-quality TLS** — ngrok free tier with `BypassCertificate` handler in Unity for cert validation. Dev only; needs proper deployment story for ship.
- **No animation rig pre-Meshy** — current avatar is static. Full duck-mode without Feature A.

---

## 8. Tooling firepower

- **Claude Code** (Anthropic) on the Max plan — Opus 4.7 with 1M-token context, agentic file editing, web search, gh CLI integration, parallel tool calls, plus a curated memory system spanning 14 project memories + 8 daily diaries + 5 mistakes files. Primary thinking partner for architecture, debugging, and pipeline design.
- `gh` CLI for GitHub interaction
- VS Code as editor
- Unity Editor 6000.4.5f1 with Meta XR + URP
- adb + ngrok for device debugging
- boto3 for RunPod S3 fetch
- Already: 4hr deep diagnosis loop today on a URP shader stripping bug ended with the canonical Unity-documented fix (Resources/ folder Material placeholders) — *not* a hack, the official approach per [Unity glTFast Project Setup docs](https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.0/manual/ProjectSetup.html).

---

## 9. Specific asks for ChatGPT / Gemini

I'd value your perspective on any of these:

1. **Animation choice** — is Meshy Rigging API actually the best fit, or would you push toward Tripo AI / DeepMotion / a different approach for this specific use case (passthrough MR, full-body humans, ~3-5min existing pipeline budget)? Anything I'm missing about Meshy's quality bar or rate limits in production?

2. **TRELLIS parameter tuning for human avatars** — am I reading the fal.ai guidance correctly that our current `shape_slat guidance = 8.0` is over-aggressive for organics? Any specific param combinations you've seen empirically work better for full-body human portraits at this fidelity bar?

3. **Premium VR UX patterns I haven't listed** — the Tier 1/2/3 polish list I have feels solid but possibly missing things. What VR/MR products do you consider best-in-class for "premium product feel" right now (2026), and what specific patterns/effects/interaction details from those would you recommend stealing for a 60-90 sec demo?

4. **Spawn-moment effect** — particle dust + dissolve + emissive glow is my plan for the avatar materialization. Any compelling alternative aesthetics that read more "premium" — holographic scan-line effect, voxel-build, photon-shower, etc.? Reference titles welcome.

5. **Architectural critique** — anything about the Quest → Mac → RunPod → S3 → Mac → Quest pipeline that strikes you as fragile, over-engineered, under-engineered, or where you'd suggest a different boundary? Particularly interested in: should the Mac middleware exist at all in production, or should Quest talk directly to RunPod with the portraitizer step embedded in the Docker image?

6. **OpenAI portraitizer alternative paths** — given the hard-limit billing block, are there equivalent-quality alternatives I should evaluate? (Stability AI image edit, Adobe Firefly API, Flux Schnell, etc.) Specifically need: input photo → studio-portrait transformation preserving identity, full-body framing, white background, photorealistic. The empirically-confirmed value of this step is ~the difference between "good geometry" and "good geometry AND good materials."

7. **Anything I'm conspicuously NOT asking** — what would you focus on that I've completely missed?

---

## 10. What I'm NOT asking for

- Feature scope expansion beyond animation + UI (focused on EOW shipment, not v2 roadmap)
- Tutorials on glTFast or Unity URP basics — I've been deep in those for 3 weeks
- Pipeline rewrites unless there's a genuine architectural bug
- "You should use Unreal" — already burned a week proving UE5 + Quest 3 + Intel Mac was a dead end (engine regression in cooker stage, parked permanently)

Direct critique > diplomatic phrasing. Specific > general. Code snippets > prose where applicable.

Thanks.

— Parthiv
