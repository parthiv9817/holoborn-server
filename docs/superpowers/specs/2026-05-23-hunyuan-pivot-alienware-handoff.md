# Hunyuan3D-2mv Pivot — Alienware Handoff (Death Note v2)

**Date:** 2026-05-23
**Author session:** Parthiv + Claude (Opus 4.7 on Mac)
**Status:** Decision made (Hunyuan pivot). Alienware execution begins on Alienware-Claude's first turn.
**Target reader:** Future-Claude on Alienware (Windows 11 + PowerShell + possibly WSL2) picking up the work. Read this once, get all the context back, start executing.
**Supersedes:** `2026-05-21-multiview-trellis-design.md` (sections 6.3, 7, 11 of that spec were invalidated by hardware reality — see Section 1 below).

---

## 0. To future-Claude on the Alienware (READ FIRST)

You are not starting fresh. There was a multi-hour session on Parthiv's Mac on 2026-05-23 that produced this doc plus a ChatGPT council second-opinion. Everything you need to act is below.

**Before doing anything else:**
1. Read this whole file end-to-end. Every section is load-bearing.
2. Read `CLAUDE.md` at the root of `holoborn-server`. That's the Mac backend's project rules.
3. Read `diaries/2026-05-21.md` and `diaries/2026-05-22.md` (if exists) and `diaries/2026-05-23.md` (if exists). The diary chain gives you the immediate prior arc.
4. Read the prior spec `docs/superpowers/specs/2026-05-21-multiview-trellis-design.md` ONLY for sections 1 (Parthiv profile) and 2 (memory entries) — those are still valid. Sections 6.3, 7, 11 are SUPERSEDED by this doc.
5. The current branch on `holoborn-server` is `main`. The current branch on `holoborn-gpu` is `main`.

**Your literal first command** is in Section 9. Do not improvise something else.

**The single most important thing to understand:** the goal is **falsifiable empirical signal within 1 day** on whether Hunyuan3D-2mv geometry beats TRELLIS.2-4B geometry for hair + eyes. NOT a full production integration. NOT a research survey. ONE test, ONE answer, then we decide.

---

## 1. What changed since 2026-05-21 spec (read this if you read the prior spec)

The prior spec assumed the Alienware was a 24GB-VRAM machine and proposed running TRELLIS.2-4B locally. **Both assumptions were wrong.**

**Actual Alienware spec (verified 2026-05-23 via nvidia-smi + systeminfo):**
- NVIDIA GeForce RTX 4070 **Laptop GPU**, Ada Lovelace (sm_89), **8 GB VRAM**, 115W variant
- **32 GB DDR5 RAM**, dual-channel, 4800 MT/s
- Windows 11, CUDA 12.9 driver (576.83)
- gh CLI authenticated as `parthiv9817` in PowerShell

The 8GB VRAM rules out running TRELLIS.2-4B at production quality (1536_cascade needs ~20-24GB). The 32GB RAM unlocks aggressive CPU offloading patterns. Combined: this is a "viable local experimentation tier" machine per ChatGPT council, NOT a production rig.

**Production output continues to run on RunPod RTX 4090 24GB.** Alienware is for iteration only.

---

## 2. Who is Parthiv (compressed; full version in prior spec Section 1)

- 23 yo, AI integrations engineer at HoloBorn. Owns full stack: Mac backend, Unity Quest client, RunPod GPU handler, Meshy integration.
- Voice AI specialist; 370+ live Twilio calls in production. Don't teach him basics.
- Pre-Claude portfolio at github.com/parthivqw demonstrates he builds without AI assistance.
- **Casual / Gen Z register with you** ("bro", "brother", "ngl", "tbh", "lol"). MIRROR THAT.
- **Strictly professional register with Vipin** (founder). NO Gen Z slang in founder drafts.

---

## 3. Memory entries you must internalize (Mac-side backup in case yours not synced)

Mac path: `/Users/digispoc06/.claude/projects/-Users-digispoc06-Documents-holoborn-server/memory/`. The Alienware will have its own memory dir. These are the iron rules:

- **`feedback_brick_by_brick.md`** — during critical-path execution, do NOT queue parallel side-tasks. Sequential focus.
- **`feedback_commit_cadence.md`** — NEVER auto-commit. Stage freely. Wait for Parthiv to say "commit this."
- **`feedback_websearch_before_ai_opinions.md`** — for named errors/library issues, WebSearch FIRST. ChatGPT/Gemini are backup, not substitute.
- **`feedback_env_config_upfront.md`** — never ship code with `YOUR-X-HERE` placeholder + "update later." Ask for actual values upfront.
- **`feedback_use_direct_file_editing.md`** — direct Read/Write/Edit on files. NOT click-by-click GUI walkthroughs.
- **`feedback_test_matrix_before_proposing.md`** — by the 3rd fix attempt, write a {settings, outcome} matrix. Don't repeat known-bad states.
- **`feedback_uvicorn_restart_on_env_change.md`** — pydantic-settings caches `.env` at startup. Restart uvicorn after any `.env` edit.
- **`feedback_no_timeline_pressure_framing.md`** — Vipin's "chill pill" stance is live. Don't propose scope cuts without authorization.
- **`feedback_terminal_brain_dump.md`** — during high-stakes sessions, brain-dump to `diaries/YYYY-MM-DD.md` BEFORE closing the terminal.
- **`user_founder_register.md`** — Vipin drafts use professional register.
- **`project_runpod_min_workers.md`** — RunPod min_workers=0 during dev; bump to 1 only ~30 min before live demos.
- **`project_canonical_pose_required.md`** — A-pose inputs auto-rig cleanly via Meshy; natural-pose produces wing-pants. Fix upstream silhouette, not downstream config.

---

## 4. What HoloBorn is (one paragraph)

Meta Quest 3 mixed-reality app that turns a single user photo into a 3D avatar hologram in the user's actual room. Quest captures via passthrough → Mac (FastAPI) does framing validation + portraitization (GPT Image 1.5/2) → sends to RunPod serverless GPU running **currently TRELLIS.2-4B** for image-to-3D → output goes through Meshy Retex → Meshy Rigging + Animation → final rigged animated GLB streams back to Quest → Unity + glTFast spawns it as hologram. Founder: **Vipin**. Sole technical employee: **Parthiv**.

---

## 5. The problem we're solving (the only thing that matters)

Quoting Vipin (Slack, 2026-05-20 17:37):
> "This is fine but we still havent cracked the texture level at hair etc"

He says "texture" but the actual cause is **geometry**, confirmed by direct GLB inspection in Babylon.js (white unlit clay render shows the same defects without any texture involved).

**Specific failures:**
- **Hair**: single helmet-cap mesh. No strand definition. No volumetric breakup. No fly-aways. Reads "wrong" as hologram.
- **Eyes**: sunken / underfit. Eyeball not distinct geometry from surrounding socket. Reads "dead-eyed."
- **Side profile**: collapses to a smooth averaged silhouette. The model is extrapolating unseen rear/side geometry from a single front portrait.

**Already solved (don't re-litigate):**
- Texture quality (Meshy v6 Retexture with `remove_lighting=true + enable_pbr=true`).
- Rigging + animation (Meshy Rigging + Animation APIs).
- Quest-side rendering (IBL via studio HDRI, glTFast Shader Graphs, ACES tonemap — ~85% Meshy WebUI fidelity, agent-confirmed hardware ceiling).
- Pipeline end-to-end reliability.

---

## 6. The decision: Hunyuan3D-2mv pivot

**Locked in** by Parthiv on 2026-05-23 after a ChatGPT council second-opinion that recommended this with a substantive justification. Verbatim Parthiv: *"so brother decidede i am pivoiting to hunyuan."*

**Council's core argument** (the part you need to internalize):

> TRELLIS multi-image is *architecturally* supported (`get_cond` accepts `list[Image]`) but the released weights were trained on single-image inputs only. The model treats multiple portraits as "more conditioning tokens" rather than "multi-view geometric constraints." Different problems.
>
> Hunyuan3D-2mv was **natively trained** on front/back/left multi-view inputs. Architectural bias directly targets silhouette consistency, depth continuity, volumetric reconstruction — which is exactly the failure mode behind helmet hair and dead eyes.
>
> Multi-view supervision improves orbital depth, curvature continuity, specular geometry separation. Helmet hair happens when the model lacks rear/head-volume priors; multi-view training gives those.

**The architecture this lands on:**

```
Hunyuan3D-2mv          ← geometry prior engine (replaces TRELLIS)
    ↓ GLB
Meshy v6 Retexture     ← material / PBR normalization (unchanged)
    ↓ GLB
Meshy Rigging+Anim     ← (unchanged)
    ↓ GLB
Quest + glTFast        ← (unchanged)
```

Meshy already proved itself as a geometry-preserving PBR cleanup pass on TRELLIS output. There's no reason it won't work on Hunyuan output the same way. We're replacing ONE stage, keeping the rest.

---

## 7. Falsifiable test protocol (from ChatGPT council — execute this verbatim)

**Subject selection:** ONE difficult subject. Medium-long hair. Visible bangs/flyaways. Strong eye visibility. Side-profile asymmetry. Parthiv will provide the source photo(s); ask him for it. Likely Y-test subject or a fresh capture.

**Generate three GLBs from the same source(s):**

| Model | Inputs | Notes |
|---|---|---|
| TRELLIS current (production) | 1 image | Use RunPod existing pipeline as baseline. Don't re-run; use the most recent existing production GLB if available. |
| Hunyuan3D-2mv | 3 images (front, back, left) | The actual test. Run locally on Alienware OR on a fresh RunPod pod if local OOMs. |

(Council originally proposed a 3rd test — TRELLIS multi-image — but we're skipping it. Council's own analysis predicted "modest improvement" and Parthiv has decided the pivot. Don't waste a day proving the weak option.)

**Inspect each GLB at:**
- Pure white clay render (Babylon.js sandbox, unlit material, no texture)
- Wireframe pass (topology preservation)

**Judge ONLY on these metrics — NOT overall prettiness:**

| Metric | Success Condition |
|---|---|
| Hair silhouette | No smooth helmet cap. Visible mass breakup. |
| Hair depth | Volumetric layering visible in side view. |
| Eye geometry | Distinct orbital protrusion. Eyeball separable from socket. |
| Side profile | Preserved facial curvature. Doesn't collapse to averaged head shape. |
| Temporal stability | Two re-runs produce broadly similar geometry (not random). |

**The kill condition:** If Hunyuan does NOT materially improve silhouette breakup, orbital depth, or hair volume within ~1 day of work, **abandon the pivot** and report back. This is non-negotiable. Don't fall into "let me tweak one more parameter" doom-loop.

---

## 8. Implementation path (3 options, ranked by cost)

**Path A (DEFAULT — try first): Tencent's official Gradio demo, locally.**
- Clone `https://github.com/Tencent-Hunyuan/Hunyuan3D-2`
- Follow their multi-view (mv) inference instructions
- Run on Alienware (Python venv, Windows native or WSL2 — see Section 9 for the call)
- Expected outcome: works in ~2-4 hours of setup if you don't hit dep hell; OOMs at peak texture stage on 8GB without offloading
- **If it works, you can iterate locally without burning RunPod credits.**

**Path B (fallback if A OOMs hard): ComfyUI-Hunyuan3DWrapper.**
- Community wrapper that handles low-VRAM offloading at the loader level
- Has documented `--lowvram --force-fp16` flags that ACTUALLY work for Hunyuan inference (verified via trellis2.app blog as community pattern for low-VRAM 3D inference)
- More setup overhead (ComfyUI install + custom nodes) but better low-VRAM ergonomics
- Expected outcome: works on 8GB at FP16 with sequential CPU offload

**Path C (last resort): Run on a fresh RunPod pod, not serverless.**
- Spin up an on-demand RunPod RTX 4090 instance (NOT the serverless endpoint — a raw pod for SSH)
- Run Hunyuan-2mv there with full VRAM available
- Costs ~$0.50/hr; ~2-3 hours of work = ~$2 total
- Use this if both A and B fail or if Parthiv decides local iteration is too slow
- **Requires Parthiv to top up RunPod credit first** (currently ~$9; needs ~$50-100 — ask him before going this route)

**Don't combine paths. Pick A. If A fails at install, pivot to B. If B fails, pivot to C. One brick at a time.**

---

## 9. Your literal first action on Alienware (do NOT improvise)

Before any setup, do exactly these steps in order:

### Step 0: Verify environment state (parallel where possible)

Run these in PowerShell and report results to Parthiv before proceeding:

```powershell
nvidia-smi
python --version
git --version
gh auth status
wsl --status
docker --version
```

Expected: nvidia-smi shows 8188 MiB. Python 3.10+ ideally. gh authenticated as parthiv9817. WSL2 may or may not be installed. Docker may or may not be installed.

### Step 1: Clone both repos to the Alienware

```powershell
mkdir C:\Users\Dell\dev\holoborn
cd C:\Users\Dell\dev\holoborn
gh repo clone parthiv9817/holoborn-server
gh repo clone parthiv9817/holoborn-gpu
```

### Step 2: Re-read this doc + CLAUDE.md + latest diary from the cloned repo

```powershell
cd C:\Users\Dell\dev\holoborn\holoborn-server
# Open this doc again from the cloned location to be sure of any updates:
# docs\superpowers\specs\2026-05-23-hunyuan-pivot-alienware-handoff.md
```

### Step 3: Confirm with Parthiv before installing anything

Before you start downloading 16GB of Hunyuan weights or installing Python deps, **explicitly confirm** with Parthiv that he wants Path A (local Python install). The reason: a 16GB+ download is non-trivial and he should know it's happening. Per `feedback_env_config_upfront.md` — no surprises.

Say something like: *"On Alienware, environment looks like [X, Y, Z]. Ready to start Path A (clone Tencent Hunyuan3D-2 repo, set up Python env, download weights — ~16GB, ~30min on broadband). Greenlight?"*

Wait for greenlight. Then proceed.

### Step 4 onward: follow Tencent's official Hunyuan3D-2 setup, with multi-view variant.

The model card is at `https://huggingface.co/tencent/Hunyuan3D-2mv`. The repo is at `https://github.com/Tencent-Hunyuan/Hunyuan3D-2`. WebFetch both as your first authoritative source — community blog posts come second.

---

## 10. License risk — Hunyuan3D-2 Tencent Community License

**This is the strategic risk Parthiv should know before deploying to production:**

The Tencent Hunyuan Community License has these constraints (council-cited; verify against the actual LICENSE file when you can):

- **Commercial use is permitted** below thresholds (1M MAU).
- **Excludes EU / UK / South Korea** as territories.
- **Requires separate licensing above 1M MAU.**

HoloBorn is pre-revenue. Currently under all thresholds. But if there's intent to scale into EU app stores or globally, **legal review needed before production dependence**.

**Action item for you:** When you're at the point where Hunyuan is performing well and Parthiv asks "should we ship this," BEFORE saying yes, surface this license risk to him explicitly. Don't let it surprise anyone.

---

## 11. Operational state at handoff (2026-05-23, ~late morning Mac time)

- **Production pipeline:** unchanged. TRELLIS + Meshy still live on RunPod + Mac backend.
- **RunPod credit balance:** ~$9. Tight. Don't burn it on Hunyuan exploration; use Alienware locally first.
- **RunPod min_workers:** 0 (dev mode, per Vipin's directive).
- **Mac uvicorn:** not running this session. ngrok not running. Restart only if Parthiv asks.
- **Current ngrok URL** (if Parthiv asks you to restart): `grinning-flyable-golf.ngrok-free.dev` per memory `project_ngrok_perm_url.md`. Verify it pairs with the authtoken in `.env` BEFORE running ngrok (per `feedback_ngrok_url_authtoken_pairing.md`).
- **Meshy Pro:** ACTIVE, API key in `.env`, Vipin approved 2026-05-11.
- **Most recent diary:** read `diaries/2026-05-21.md` for the brainstorm context. Today's (2026-05-23) diary should be written by Parthiv or you before the Alienware session closes (per `feedback_terminal_brain_dump.md`).

---

## 12. How to update Vipin (this is delicate — there's a live tension)

**Current Vipin state (2026-05-23 ~04:00 AM Slack):**
> "i dont appreciate this, you are here to resolve issue not tell me this n that"
> "you should have got this done"
> "Please check you Alienware machine properly am sure its not an 8gb machine"
> "you have till today to resolve everything"
> "not like i have not given you anything you have asked for"
> "please dont come with issue! get things done"

**Parthiv's verified counter-data:**
- 8GB is confirmed (nvidia-smi authoritative; 8188 MiB).
- Vipin's "till today" deadline is operative.

**Rules for any Vipin update you draft:**

1. **Do NOT send anything until there is empirical data.** Yesterday's mistake was "calling dead-end before verifying community workarounds." Don't repeat the symmetric mistake of "calling good news before testing."
2. **Professional register only** (per `user_founder_register.md`). No "bruh" / "ngl" / "tbh" / "lol."
3. **Lead with what was done, not what's blocked.** Vipin's literal instruction: *"please dont come with issue! get things done."*
4. **Concrete data, falsifiable claims.** "Generated test GLB with Hunyuan-2mv at [config]; geometry comparison vs TRELLIS shows [specific defect improved/not improved]." Not "looks promising."
5. **Don't propose scope cuts** (per `feedback_no_timeline_pressure_framing.md`). If something can't ship today, say so plainly with reason; don't pre-emptively offer "a shippable subset."
6. **Don't ask Vipin for things mid-update** unless explicitly needed. If RunPod credit top-up is needed, raise it AFTER showing the empirical result, not before.

**Recommended cadence:** ONE update at end of Alienware day with: (a) what was tested, (b) what the GLB inspection showed, (c) what the next step is. Not running commentary.

---

## 13. Anti-patterns (what NOT to do)

These are the failure modes Parthiv has explicitly called out across the project. Avoid these:

- **Don't auto-commit.** Even after a clean test cycle. Wait for explicit "commit this."
- **Don't click-by-click in any GUI.** If it's a file (YAML, JSON, .toml, .env), use Read/Write/Edit directly. Don't walk Parthiv through ComfyUI's node graph mouse-by-mouse.
- **Don't surface "this is broken" without first WebSearching the exact error string.** Especially for Hunyuan/PyTorch/CUDA dep errors — community has hit them all already.
- **Don't propose a fix that contradicts a recent test outcome without explicit framing.** If something OOMed at FP32 and you're proposing FP16, say "previous attempt OOMed at FP32 — trying FP16 next" not just "let's try FP16."
- **Don't draft Vipin messages with slang.** Strict professional register.
- **Don't queue parallel side-tasks.** One brick at a time. Even if there's a 30-min wait on a model download, don't start exploring some tangent. Wait, observe, continue.
- **Don't propose "let me also rebuild X" or "while I'm here, let me refactor Y."** Scope discipline. The goal is ONE thing: empirical signal on Hunyuan geometry quality.
- **Don't burn RunPod credits without asking.** Local-first.

---

## 14. Other multi-view 3D models the council surfaced (DON'T explore unless Hunyuan fails)

For situational awareness only. Do NOT explore these unless Hunyuan-2mv fails the kill condition in Section 7 and Parthiv explicitly asks for next options.

**Worth a 1-day spike IF Hunyuan fails:**
- InstantMesh
- Wonder3D
- Era3D
- MV-Adapter + Hunyuan combo (uses MV-Adapter to synthesize side/rear views, feeds to Hunyuan)

**Probably NOT worth time:**
- CRM (different problem class)
- SF3D (geometry quality not stronger than Hunyuan)
- TRELLIS mesh ensembles (hacky)

**Hidden variable the council flagged:**
> "Your multi-view INPUT quality may matter MORE than the reconstruction model. Garbage synthetic side/rear views will poison geometry."

So the strongest pipeline may eventually become: single portrait → MV-Adapter for view synthesis → Hunyuan-2mv → Meshy. Don't go there yet. First test Hunyuan-2mv with REAL multi-view inputs from Parthiv (3 photos).

---

## 15. Communication channels + reference data

- **Slack** is where Vipin lives. Parthiv sends updates there.
- **GitHub repos** (both public):
  - `parthiv9817/holoborn-server` (Mac FastAPI backend — current dir)
  - `parthiv9817/holoborn-gpu` (RunPod GPU handler — Docker pipeline)
  - `parthiv9817/holoborn-quest-unity` (Unity Quest client)
- **Docker Hub:** `parthiv8421/holoborn-gpu:latest` (the production RunPod image; can pull for reference)
- **Hunyuan3D-2 official:** `Tencent-Hunyuan/Hunyuan3D-2` on GitHub, `tencent/Hunyuan3D-2mv` on HuggingFace
- **RunPod endpoint** (production, unchanged): `pz2c4wvo2rcdw9` — async URL `https://api.runpod.ai/v2/pz2c4wvo2rcdw9/run`
- **Mac path to this doc** (if Parthiv references it): `/Users/digispoc06/Documents/holoborn-server/docs/superpowers/specs/2026-05-23-hunyuan-pivot-alienware-handoff.md`

---

## 16. Open questions for next session (raise these with Parthiv if relevant)

- **Source photos for the test:** does Parthiv want to use existing Y-test source images, or shoot a fresh 3-photo set (front/back/left) specifically for this? Ask before downloading models.
- **RunPod credit top-up:** if Path C becomes necessary, Parthiv needs Vipin's approval. Don't surprise-ask in the middle of work; surface it as a question once it's clearly needed.
- **WSL2 install on Alienware:** if Path A or B requires WSL2 and it's not installed, that's a 30-min setup + reboot. Confirm with Parthiv before doing it.
- **License review timing:** when Hunyuan is performing well and Vipin is about to greenlight production, the EU/MAU constraint needs to be surfaced. Track this.

---

## 17. The single sentence to remember

**Get one Hunyuan3D-2mv GLB out of the Alienware (or a RunPod fallback pod) in under 1 day, inspect it for hair + eye geometry vs the existing TRELLIS production GLB, and report back with a binary verdict.** Everything else is in service of that.
