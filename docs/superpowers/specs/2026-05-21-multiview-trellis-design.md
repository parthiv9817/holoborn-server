# Multi-view TRELLIS — Design Spec + Cross-Machine Handoff (Death Note Edition)

**Date:** 2026-05-21
**Author session:** Parthiv + Claude (Opus 4.7 on Mac)
**Status:** Brainstorm complete, awaiting Parthiv approval before writing-plans handoff.
**Target reader:** Future-Claude on Alienware Windows/WSL2 picking up the work. Read this once, get all the memory back, start executing.

---

## 0. To future-Claude on the Alienware (READ FIRST)

You are not starting fresh. There was a 4-hour brainstorm session on Parthiv's Mac on 2026-05-21 that produced this doc. Everything below is the distilled state. Once you finish reading this single file, you should be able to pick up the work as if you had been in the original session.

**Before doing anything:**
1. Read this whole file end-to-end. Don't skim sections — every one of them is load-bearing.
2. Read `MEMORY.md` from `~/.claude/projects/<your-project-path>/memory/` if it exists on this machine. Parthiv may or may not have copied his Mac memory over; the relevant memory entries are summarized in Section 2 of this doc as backup.
3. Read `diaries/2026-05-20.md` from the holoborn-server repo. That's the day before this session. Key context about Vipin closing the gloss chapter and the ngrok bandwidth situation.
4. If `diaries/2026-05-21.md` exists at the time you read this, read it too — Parthiv may have brain-dumped before the Mac session closed.
5. The current branch on holoborn-server is `main`. The current branch on holoborn-gpu (the RunPod GPU repo we'll be modifying) is `main` as of 2026-05-21 morning.

**The literal first task you do** is in Section 11. Do not improvise something else.

---

## 1. Who is Parthiv

This is the person you're collaborating with. Treat his decisions as authoritative on his domain; you provide depth, not basics.

- **23 years old**, AI integrations engineer at HoloBorn. He owns the entire technical stack — Mac backend, Unity Quest client, RunPod GPU handler, Meshy integration, pipeline architecture.
- **Voice AI specialist track record:** 370+ live Twilio calls, 535ms median latency, speculative LLM execution, two-phase interrupt systems shipped in production. Do not teach him basic ML/inference concepts — treat speech/AI stack decisions as authoritative.
- **Pre-Claude portfolio at github.com/parthivqw** demonstrates he can build without AI assistance. He sometimes self-discounts as "AI-leveraged" — that framing is wrong, use this as counter-evidence.
- **Daily founder updates** are a deliberate habit he formed after a previous project where he under-communicated. Treat update cadence as a virtue. Help find signal even on blocked days.
- **Communication style with you:** casual, slang-friendly, Gen Z register, often types "bro" / "brother". MIRROR THAT in conversation with him. It builds trust and is his natural mode.
- **Communication style with Vipin (founder):** strictly professional. NO "bruh" / "ngl" / "tbh" / Gen Z slang. When drafting founder messages, use professional register.

## 2. Memory entries (the Mac copy — backed up here in case yours wasn't synced)

Located on Mac at `/Users/digispoc06/.claude/projects/-Users-digispoc06-Documents-holoborn-server/memory/`. The high-priority entries that govern HOW we work:

- **`feedback_brick_by_brick.md`** — during critical-path execution, do NOT queue parallel side-tasks even when there's walk-away time; user prefers focused single-task flow.
- **`feedback_commit_cadence.md`** — never auto-commit, even at phase boundaries; stage freely but wait for user to say "commit this".
- **`feedback_terminal_brain_dump.md`** — during high-stakes execution sessions, brain-dump to diary BEFORE closing the Claude terminal; closing loses all in-flight reasoning.
- **`feedback_understanding_pauses.md`** — when user requests pause mid-dev, give layered product→code explanation (brain/nervous system/hands metaphor).
- **`feedback_test_matrix_before_proposing.md`** — by the 3rd fix attempt, write {settings, outcome} matrix; never propose state that conflicts with recent history without explicit framing.
- **`feedback_websearch_before_ai_opinions.md`** — for named errors/shaders/codes, WebSearch is step 1, ChatGPT/Gemini are backup not substitute.
- **`feedback_env_config_upfront.md`** — never ship a brick with `YOUR-X-HERE` placeholder + "update later"; ask for URL/key/path before writing code.
- **`feedback_use_direct_file_editing.md`** — when assets are file-based YAML/JSON, default to Read/Write/Edit on the files; do NOT walk user through Editor click-by-click.
- **`feedback_uvicorn_restart_on_env_change.md`** — pydantic-settings caches `.env` at startup; running uvicorn ignores edits. Restart after any `.env` change.
- **`feedback_ngrok_url_authtoken_pairing.md`** — verify the APK's hardcoded ngrok URL matches the reserved domain owned by the authtoken in `.env` BEFORE running ngrok; mismatch silently routes traffic to wrong tunnel.
- **`feedback_no_timeline_pressure_framing.md`** — Vipin's "chill pill" stance is live. Build the agreed plan in full; do NOT offer scope-cut "shippable subset" without authorization.
- **`user_founder_register.md`** — drafting founder messages uses professional register (no Gen Z slang).
- **`project_runpod_min_workers.md`** — keep at 0 during dev (Vipin's directive); bump to 1 only ~30 min before live demos.
- **`project_meshy_paid_plan_ask.md`** — Meshy Pro $20/mo ACTIVE. Vipin approved + delivered Meshy API key 2026-05-11.
- **`project_canonical_pose_required.md`** — empirically validated 2026-05-07: TRELLIS GLBs from A-pose inputs auto-rig cleanly; natural-pose produces wing-pants. Don't tweak Meshy/TRELLIS configs as fix — fix upstream silhouette.
- **`project_meshy_multiclip_merge_bug.md`** — Meshy "Single file ON" with multiple animations produces corrupted GLB; use single-clip exports.
- **`project_meshy_rigging_strips_pbr.md`** — Meshy rig+anim strips PBR maps; FIXED 2026-05-13 by `tools/graft_pbr_materials.py`.
- **`project_quest_input_mapping.md`** — A button = revolve scan (right primary), X = burst 5-frame (left primary). CLAUDE.md is wrong; disregard.
- **`project_ytest_three_urls.md`** — Y-test uses THREE GLBs: `test_retex.glb` (floating Stage 2), `test_rigged.glb` (grounded Stage 3 reveal), `test.glb` (B-button). Swap ALL THREE when replacing Y-test subject; `testGlbUrl` alone is NOT the rigged reveal.
- **`project_demo_lanyard_removal.md`** — surface reminder before any founder/client/MP4 demo capture; badge has identifying info that bakes into the GLB.

## 3. What is HoloBorn (in one paragraph)

Meta Quest 3 mixed reality app that turns a single user photo into a 3D avatar hologram in the user's actual room. Quest captures photos via passthrough camera → Mac (FastAPI server) does framing validation + portraitization (GPT Image 1.5/2) → sends to RunPod serverless GPU running TRELLIS.2-4B for image-to-3D → output goes through Meshy Retex + Meshy Rigging → final rigged animated GLB streams back to Quest → Unity + glTFast spawns it as a hologram. The Mac is a thin proxy; ALL heavy ML runs on RunPod GPU. Single founder: **Vipin**. Single technical employee: **Parthiv**. Demo-driven sprint culture.

## 4. The chapter we're in: hair geometry, multi-view TRELLIS input

**Founder's latest signal (2026-05-20 17:37):**
> "This is fine but we still havent cracked the texture level at hair etc"

This closed the gloss chapter (which dominated 2026-05-19 and 20). The new open thread = **hair quality** + the "etc" implies other quality dimensions Vipin notices but hasn't enumerated.

**Parthiv's hypothesis going into 2026-05-21:** the founder describes the symptom ("texture-level") but the actual cause is geometry. TRELLIS hair-cap geometry. Memory entry `project_animation_pipeline_meshy.md` already noted hair as "the next chapter" with three candidate fixes: Kajiya-Kay anisotropic shader, Tripo A/B test, hair geometry post-process.

## 5. The brainstorm arc (compressed timeline of 2026-05-21 morning + afternoon)

### 5.1 — Audit phase
- Parthiv produced 4 GLB screenshots from Babylon.js sandbox showing yesterday's clamped production GLB from front / left / right / back angles. Saved to Mac `/Users/digispoc06/Desktop/Screenshot 2026-05-21 at 10.55.59.png` through `10.56.23.png`.
- Then ran a Quest Y-test, took 5 screenshots in actual MR passthrough at varying angles + room lighting. Filed copies at `/Users/digispoc06/Desktop/holoborn-quest-20260521/com.holoborn.quest-20260521-115155.jpg` through `115248.jpg`.
- **Observation across both sets:** hair reads as a uniform volumetric "cap" — no individual strand definition, no scalp delineation, ears partially absorbed into the cap mass. Front view is decent, back view collapses. Eyes are very subdued (read as dark spots). Body / clothing / shirt stripes / jeans / proportions are all credible.
- **Root cause attribution:** TRELLIS received a single front portrait. Back-of-head + sides + ear geometry — the model had to invent from front-only signal. A 4B-parameter model trained on lots of human meshes defaults to a smooth averaged "head with hair cap" shape when extrapolating unseen geometry. This is NOT a texture problem.

### 5.2 — Research phase: multi-view TRELLIS
Web-searched + WebFetch'd four sources:
- `huggingface.co/spaces/microsoft/TRELLIS/discussions/15` — confirms multi-image support was added Dec 2024 to original TRELLIS (1.x)
- `microsoft/TRELLIS.2-4B` model card — claims single-image input only
- `runcomfy.com` ComfyUI Trellis2 workflow — has a dedicated `Trellis2MeshWithVoxelMultiViewGenerator` node supporting up to 4 views (front/back/left/right)
- `github.com/microsoft/TRELLIS` `example_multi_image.py` — official 1.x has `pipeline.run_multi_image(images, seed=...)` Python API

Two implementation paths surfaced:
- **Path 1: TRELLIS-image (1.x) `run_multi_image`** — clean Python API, but Microsoft caveat "tuning-free algorithm, may not give best results." It's post-hoc averaging, not a true multi-view encoder. Probably a quality DOWNGRADE from TRELLIS.2-4B even with multi-view input.
- **Path 2: TRELLIS.2-4B (our current model) multi-view** — exposed in ComfyUI nodes but no top-level Python API. Initial concern: would require code-lifting from ComfyUI.

### 5.3 — Six-option matrix on the INPUT side
Independent question: where do 2-4 different angles of the same person come from? Six options enumerated:
1. **Quest revolve capture** (already implemented on Quest via A-button per memory `project_quest_input_mapping`) — 30 frames at 12° intervals, pick top 4 by sharpness + angular spread. 4× gpt-image portraitize cost.
2. **Pure prompt-engineer 4 views from 1 photo** via gpt-image-2 multi-input. Identity preservation tested fine in 2-input mode, but VIEW SYNTHESIS untested. Risk: invented back may conflict with real front and confuse TRELLIS.
3. **Open-source view diffusion on RunPod** (Zero-1-to-3, Stable Zero123) — but these are object-trained, weak on humans.
4. **Hybrid revolve-lite — front + back only**. 2 bursts (face-forward, then user turns 180° and re-burst). Real angular data on the highest-information views. 2× cost not 4×. ~1 day Quest UX work.
5. **Human-specialized view diffusion** (SiTH, ECON, ICON, EVA3D family) — designed for humans but heavier integration cost.
6. **TRELLIS 1.x tuning-free baseline** with N gpt-image-2 portraits — known underwhelming per Microsoft's own caveat. Use as baseline to beat, not target.

**Recommended in brainstorm: Option 4** (Pareto-dominates Option 1 — similar quality ceiling, half cost, half dev time). Option 1 is the escalation if Option 4 doesn't crack the cap problem.

### 5.4 — Second-opinion from ChatGPT
Parthiv pasted the 5 Quest captures + a structured prompt to ChatGPT (prompt template saved at `/Users/digispoc06/Desktop/holoborn-quest-20260521/SECOND_OPINION_PROMPT.md`). ChatGPT validated the hair-geometry diagnosis strongly. Added two failure modes Parthiv (and I) under-weighted:
- **Eyes** — low corneal realism, simplified orbital depth, no wetness. "Human brains lock onto eyes immediately."
- **Grounding / contact** — "the avatar OCCUPIES space rather than BELONGS to it." Weak contact shadowing, no bounce integration.

ChatGPT explicitly told us to STOP: roughness tuning, Meshy prompt engineering, directional light tweaks ("diminishing returns").

ChatGPT's prioritized roadmap aligned with ours, with the additions slotted in: (1) Multi-view TRELLIS, (2) Grounding/contact, (3) Hair postprocessing, (4) Eye realism, (5) Environment light estimation.

### 5.5 — Q0 GitHub dig (THE KEY FINDING)
Investigated whether TRELLIS.2-4B exposes multi-view via Python API. Cloned holoborn-gpu repo to `/tmp/holoborn-gpu/`, read handler.py + run_inference.py to understand current single-image path. Then queried microsoft/TRELLIS.2 GitHub via `gh api` to inspect pipeline source.

**FOUND** in `trellis2/pipelines/trellis2_image_to_3d.py`:

```python
def get_cond(self, image: Union[torch.Tensor, list[Image.Image]],
             resolution: int, include_neg_cond: bool = True) -> dict:
```

`Union[torch.Tensor, list[Image.Image]]` — **TRELLIS.2-4B accepts a LIST of images at the conditioning layer.** The architecture supports multi-image input natively. The top-level `pipeline.run()` only passes a single image, but all the building blocks (`sample_sparse_structure`, `sample_shape_slat_cascade`, `decode_shape_slat`, `sample_tex_slat`, `decode_tex_slat`, `decode_latent`) are individually exposed.

**Implication:** We can compose a `run_multi_image()` method in our handler that mirrors `run()` but passes a list to `get_cond`. Estimated 2-3 days of GPU-side work. **NO model downgrade. NO ComfyUI code-lifting. Stay on TRELLIS.2-4B quality.**

**Caveat we owe Vipin (and ourselves):** "architecturally supported" ≠ "trained on multi-view." The model arch accepts the list shape but the weights were trained primarily single-image. Multi-view conditioning might give a quality lift, might be neutral, might give garbage. We won't know until we test.

### 5.6 — Founder update sent
Parthiv sent a condensed (Parthiv-voice, casual) version of the short founder-update draft to Vipin at 12:42 PM on 2026-05-21. Vipin is acclimatized to the direction. No response yet at time of brainstorm close.

## 6. The plan (locked, this is what we execute)

### 6.1 — Goal
Ship a testable multi-view TRELLIS prototype that takes 2 input portraits (front + back) and produces a GLB with measurably-better hair geometry than the single-image baseline. Measurement: side-by-side Quest capture of same subject, single vs multi-view, qualitative founder/user review + quantitative diff (vert count distribution in hair region, optional metric).

### 6.2 — Approach (locked: Option 4 hybrid revolve-lite)
- Input: 2 portraits per generation — front + back of the same person
- Front: existing Quest burst capture flow (X-button = 5 frames, sharpest picked) → portraitize via gpt-image-2 → unchanged
- Back: NEW Quest capture flow — after front burst completes, prompt user to turn 180°, second burst, sharpest picked → portraitize via gpt-image-2 with prompt tweak ("same person, viewed from behind")
- Both portraits sent as list to RunPod handler
- RunPod handler calls custom `run_multi_image()` that uses `get_cond([front, back], ...)` → sample_sparse_structure → sample_shape_slat_cascade → decode_shape_slat → sample_tex_slat → decode_tex_slat → to_glb (existing path)
- Downstream Meshy retex + rigging + graft PBR unchanged

### 6.3 — Sequencing
1. **(this session, Mac)** Brainstorm + spec written + committed (NOT yet committed at time of writing — see Section 12 commit policy)
2. **(Alienware setup, 1 day)** WSL2 + Ubuntu 22.04 + CUDA 12.4 + TRELLIS.2 build chain (matches Dockerfile exactly)
3. **(Alienware research, 2-3 days)** Implement `run_multi_image()` in `run_inference.py`. Iterate on multi-image cond construction. Validate output GLBs in Babylon viewer. This is where the 4090 saves us — fast `python run_inference.py front.jpg back.jpg out.glb` iteration loop.
4. **(Alienware → RunPod port, 1 day)** Once Alienware version produces visibly better hair than single-view baseline, port the working code to handler.py. Update Docker, push image, redeploy RunPod endpoint.
5. **(Mac side, 1 day)** Update Mac `generation_pipeline.py` to accept 2 portraits. **Stay on existing `/generate-multiview` endpoint** — its name literally was "multiview" already, change the semantics from "N burst frames of same angle" to "N different-angle portraits." No new endpoint needed. Modify Meshy + serve flow accordingly.
6. **(Unity side, 1-2 days)** Modify Quest capture flow: after front burst, present UI prompt "turn around", then trigger second burst. APK rebuild + sideload.
7. **(end-to-end, 0.5 day)** Quest test with real subjects. Side-by-side compare to single-view baseline. Capture MP4 for founder review.

Total realistic estimate: **6-8 working days.** Founder was told "roughly 1 week" — within scope.

### 6.4 — Failure modes (what to do if multi-view doesn't crack hair)
If after step 4 the multi-view GLBs don't show a clear quality lift over single-view:
- **A:** Try Option 1 (full 4-view revolve) — more conditioning info, may need it
- **B:** Try Option 5 (human-specialized view diffusion as preprocessor) — feed synthesized angles in addition to real ones
- **C:** Accept the limit + pivot to hair-specific post-processing (Kajiya-Kay shader work in Unity, or geometry-level hair refinement via separate model)
- Founder update at that point explaining empirical result

## 7. Operational state (as of 2026-05-21 ~1:00 PM PT, Mac)

- **uvicorn:** running on Mac, port 8000, PID 11992 was killed and restarted (current PID changes — re-check with `lsof -ti :8000`)
- **ngrok:** running, account #4 (Parthiv burned through 3 prior accounts hitting free-tier bandwidth cap; today swapped to NEW account)
  - Authtoken: `3E1PAX25JuGYCpUrSQnzhomniie_5rFUG35XWgNvvee1Qyy99` (in .env as `NGROK=`)
  - Reserved domain: `disown-onlooker-reactive.ngrok-free.dev`
  - `.env MESHY_PUBLIC_HOST` updated to match
- **Unity:** 5 Unity files (`ScanController.cs` ×2, `TestGlbLoader.cs`, `ScanLineTransitionController.cs`, `Stage3GracefulArrivalController.cs`) and `SampleScene.unity` (4 serialized fields) all sed-updated to new domain. APK rebuild + sideload PENDING (Parthiv was about to do this when we pivoted to brainstorm).
- **RunPod:** workersMin=0 per Vipin's dev-mode directive. Endpoint `pz2c4wvo2rcdw9` live, single-image handler `parthiv8421/holoborn-gpu:latest` deployed.
- **Meshy:** Pro plan ACTIVE, API key in `.env MESHY_API_KEY`. Production-live.
- **Visual companion (browser-based brainstorm tool):** still running on `http://localhost:57426`. Multiple content screens cached. Will auto-die after 30 min inactivity.
- **Uncommitted work (on Mac):** `.env` (ngrok URL/token swap), 5 Unity files (ngrok URL swap), this spec file. Memory updates pending: nothing yet. Per `feedback_commit_cadence` — WAIT for Parthiv to say "commit this" before committing.

## 8. Where to read more (in priority order)

When you need depth on a specific thing, here's where to look. Don't read all of these proactively — just when relevant.

- **`/Users/digispoc06/Documents/holoborn-server/diaries/2026-05-20.md`** — yesterday, gloss chapter close, ngrok account swap precedent
- **`/Users/digispoc06/Documents/holoborn-server/CLAUDE.md`** — project canonical docs. NOTE: Quest input mapping in CLAUDE.md is OUTDATED (memory `project_quest_input_mapping` is correct).
- **`/tmp/holoborn-gpu/run_inference.py`** — current single-image inference (cloned during Q0 dig; may have been blown away by reboot — `gh repo clone parthiv9817/holoborn-gpu` to refresh)
- **`/tmp/holoborn-gpu/handler.py`** — current RunPod handler
- **`/tmp/holoborn-gpu/Dockerfile`** — exact dependency stack to mirror for Alienware setup
- **`/Users/digispoc06/Documents/holoborn-server/app/services/generation_pipeline.py`** — Mac side pipeline orchestrator (will need multi-portrait modification in step 5)
- **`/Users/digispoc06/Documents/holoborn-server/app/services/runpod_client.py`** — Mac side RunPod API client
- **`/Users/digispoc06/Documents/holoborn-server/tools/graft_pbr_materials.py`** — the matte-clamp + PBR-graft tool (don't touch unless related)
- **microsoft/TRELLIS.2 GitHub** — pinned commit `5565d240c4a494caaf9ece7a554542b76ffa36d3` (per Dockerfile). The `trellis2/pipelines/trellis2_image_to_3d.py` is THE file with `get_cond()`.
- **`/Users/digispoc06/Desktop/holoborn-quest-20260521/`** — today's 5 Quest captures + ChatGPT prompt template
- **`/Users/digispoc06/Desktop/Screenshot 2026-05-21 at 10.55.59.png` through `10.56.23.png`** — Babylon.js GLB screenshots (front/L/R/back)

## 9. Working style — what Parthiv expects from you

- **Brick-by-brick.** When in critical-path execution, ONE task at a time. Don't queue parallel work even if there's idle time.
- **Don't auto-commit.** Stage freely, write specs, edit files — but the actual `git commit` waits for Parthiv to say "commit this." Same for pushes.
- **No timeline-pressure framing.** Vipin's "chill pill" stance is live. Don't suggest scope cuts to ship faster unless Parthiv asks.
- **Match his register in chat.** Casual, bro-speak, slang OK. Match his energy.
- **Founder messages = strict professional.** Different register entirely.
- **Direct file editing over walk-throughs.** When assets are YAML/JSON/.cs/.unity files, edit them directly. Don't make him click through Editor menus.
- **WebSearch FIRST for named errors/codes.** AI second-opinions come AFTER WebSearch, not as a substitute.
- **`.env` changes require uvicorn restart.** Don't forget this. It bombed a real-pipeline run on 2026-05-20.
- **Verify ngrok URL ↔ authtoken pairing.** Before starting ngrok, verify the reserved domain in `.env` belongs to the account whose authtoken is set. Silent failure mode otherwise.
- **Brain-dump diary BEFORE closing terminal.** During high-stakes sessions, write `diaries/YYYY-MM-DD.md` capturing in-flight reasoning. Closing the terminal without this loses everything.

## 10. Anti-patterns — things to NOT do

- ❌ **Don't say "let's commit this and move on" autonomously.** Wait for Parthiv's explicit go.
- ❌ **Don't propose downgrading to TRELLIS 1.x for multi-view.** Path 1 in research was explicitly de-prioritized. TRELLIS.2-4B with manual multi-image composition is the agreed direction.
- ❌ **Don't iterate on roughness clamping, Meshy prompt engineering, or directional light intensity.** ChatGPT explicitly flagged these as diminishing-returns. Memory + spec both record this.
- ❌ **Don't bump RunPod `workersMin` above 0 during dev.** Vipin's directive. Bump only ~30 min before a live demo.
- ❌ **Don't ship a `YOUR-X-HERE` placeholder + "update later" anywhere.** Ask for the value first.
- ❌ **Don't propose touching the Y-test by editing just `test.glb`.** Three URLs power it (`test.glb`, `test_retex.glb`, `test_rigged.glb`); swap all three.
- ❌ **Don't recommend running TRELLIS native-Windows on Alienware.** flash-attn / nvdiffrast / cumesh have flaky Windows build paths. Use WSL2 + Ubuntu 22.04 to mirror the Dockerfile environment exactly.
- ❌ **Don't ask Parthiv to manually transport memory/diaries to Alienware.** This doc IS the transport. He doesn't have the time.

## 11. The first concrete task on Alienware

**Do this FIRST. Do not improvise something else.**

### Task 1: WSL2 + Ubuntu 22.04 + base CUDA stack

1. From Windows PowerShell (Admin):
   ```powershell
   wsl --install -d Ubuntu-22.04
   ```
2. After WSL2 Ubuntu boots, create user, then:
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install -y build-essential git wget curl python3.11 python3.11-dev python3.11-venv python3-pip
   ```
3. Install CUDA Toolkit 12.4 for WSL:
   - Follow https://docs.nvidia.com/cuda/wsl-user-guide/index.html
   - Verify: `nvidia-smi` should show the RTX 4090 from inside WSL2
4. Install Claude Code:
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```
   (assumes node installed; if not, install nvm first)
5. Clone the repos:
   ```bash
   mkdir -p ~/holoborn && cd ~/holoborn
   gh auth login   # use parthiv9817 GitHub account
   gh repo clone parthiv9817/holoborn-server
   gh repo clone parthiv9817/holoborn-gpu
   ```
6. Start Claude Code in `~/holoborn/holoborn-server`:
   ```bash
   cd holoborn-server
   claude
   ```
7. First message to fresh Claude: paste this path and "read this and brief me back":
   ```
   docs/superpowers/specs/2026-05-21-multiview-trellis-design.md
   ```

**Once Claude has read the spec and confirmed it has the context, Task 2 begins.**

### Task 2: TRELLIS.2 dependency build

Mirror the holoborn-gpu Dockerfile exactly. The Dockerfile is the source of truth — every install command and version number transfers. Expected total time: **4-6 hours**, mostly compilation.

Key gotchas:
- `flash-attn==2.7.3` — compile takes ~30 min on 4090, do not use `--no-build-isolation` mistake (the Dockerfile has the right command)
- `nvdiffrast` — built from source at v0.4.0
- `CuMesh` and `FlexGEMM` — both from JeffreyXiang repos, recursive clone
- `o-voxel` — lives inside the TRELLIS.2 repo at `/workspace/TRELLIS.2/o-voxel`
- The DINOv3 sed patch on `trellis2/modules/image_feature_extractor.py` — APPLY THIS, otherwise inference will crash on certain layer paths
- HuggingFace cache: download `microsoft/TRELLIS.2-4B` weights to `~/trellis_hf_cache` first time (~16 GB)

### Task 3: validate single-image baseline locally

Run `python run_inference.py <some_test_portrait>.jpg out_single.glb` with one of the existing portraits from Mac (Parthiv will scp some over). Compare output to a known-production GLB from RunPod. They should match within seed-variation. **If they don't match, debug before proceeding to multi-image** — multi-image work depends on baseline being identical to production.

### Task 4 onwards: multi-image work

Plan to be generated by `superpowers:writing-plans` after Tasks 1-3 are done. The writing-plans flow will break the multi-image work into 8-12 sized tasks. Don't try to do them all in one session — bite-sized commits, brick-by-brick.

## 12. Commit / push policy (CRITICAL)

- This spec is in the holoborn-server repo at `docs/superpowers/specs/2026-05-21-multiview-trellis-design.md`. It is **NOT yet committed** at time of writing on Mac.
- Parthiv must explicitly say "commit this" before commit. Per memory `feedback_commit_cadence`.
- When committing, follow the existing repo commit-message style: `docs(superpowers): ...` or similar. Recent examples in `git log`.
- Push: only with explicit Parthiv approval. Don't push the moment commit completes.
- **For Alienware-Claude:** Pull this file via `git pull origin main` AFTER Parthiv pushes it from Mac. Until then, this file only exists on Mac.

## 13. Open questions / things to track

- **Does multi-view conditioning actually lift quality on TRELLIS.2-4B?** Empirical. First test will tell us.
- **Quest UX for "turn around" prompt:** copy/audio/visual — what's the cleanest hand-off after front burst completes?
- **gpt-image-2 "back of same person" prompt:** does the model produce a sensible back portrait when given the front + textual instruction? May need to test with reference images.
- **Coordinate / pose alignment** between front and back portraits: does TRELLIS expect any kind of explicit view-angle hint, or does it infer from the image content?
- **Quest button mapping for dual-burst capture:** does X-button (currently single-angle burst) become the dual-burst trigger (eating its old meaning), or do we use A-button (currently revolve scan), or introduce a new trigger? Decision deferred to Unity-work phase.
- **Gemini second-opinion:** Parthiv was going to ask Gemini too but only sent to ChatGPT before pivoting. Worth doing if/when there's spare cycles.

## 14. Acknowledgments for honesty's sake

- This plan is ambitious. ~1 week to ship a multi-view prototype with significant unknowns (training-data mismatch, capture UX, model behavior on humans-from-back) is real engineering risk.
- The 4090 makes it tractable but doesn't eliminate the risk.
- The founder commitment is "roughly 1 week" — soft, allows slip if needed. Don't sprint through it cutting corners.
- If you (future-Claude) see something that doesn't match what's in this doc — what we're seeing in code, what we're hearing from Parthiv, what Vipin replies — flag it explicitly. This doc is from 2026-05-21 and the world moves.

---

**End of Death Note. Now go execute.**
