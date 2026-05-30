# HoloBorn — Mac Backend (`holoborn-server`)

The Mac FastAPI orchestrator for **HoloBorn**: a Meta Quest 3 mixed-reality app that grows a
photoreal, rigged, breathing 3D hologram of a person from a photo — **fully autonomously, no human
in the loop.** Press a button on the headset, it captures you, and ~5–8 minutes later a textured
avatar of you materializes in the room through a cinematic spawn ritual, floor-anchored.

This repo is the **middleware** between the Quest headset and the cloud GPU/API services. It runs no
heavy ML itself (MediaPipe pose detection only); everything else is delegated.

> **North star:** HoloBorn is not a novelty avatar toy — the real product is **digital legacy**
> (a conversational VR-you). The avatar pipeline here is *the body*, and the body is essentially
> solved. The mind/voice layer is the next frontier.

## Pipeline

```
Quest 3 ──POST /generate-multiview──► THIS SERVER (Mac, FastAPI, CPU)
                                        1. validate framing   (MediaPipe BlazePose)
                                        2. pick sharpest / burst-average
                                        3. portraitize         (OpenAI gpt-image → studio A-pose)
                                        4. view synthesis      (Hunyuan path: 1→4 turnaround views)
                                        5. 3D gen (GPU)        (RunPod: Hunyuan3D-2mv | TRELLIS)
                                        6. Meshy retexture     (clean 4K PBR, de-lit)
                                        7. Meshy rigging       (skeleton)
                                        8. PBR graft + clamp   (restore maps rigging strips)
                                        9. serve GLB ──────────► Quest (glTFast → hologram)
```
Graceful degradation: rigging fails → serve retex; retex fails → serve raw "plastic"; only
RunPod/download/timeout failures mark a task `failed`.

## The repos

| Repo | Role |
|---|---|
| **holoborn-server** (this) | Mac FastAPI orchestrator |
| [holoborn-quest-unity](https://github.com/parthiv9817/holoborn-quest-unity) | Quest 3 client (Unity 6, URP, OpenXR, glTFast) |
| [holoborn-gpu](https://github.com/parthiv9817/holoborn-gpu) | RunPod serverless **TRELLIS** handler (legacy single-view gen) |
| holoborn-hunyuan-gpu | RunPod serverless **Hunyuan3D-2mv** handler (active multi-view gen, private) |

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in OpenAI / RunPod (+S3) / Meshy keys
PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
ngrok http 8000               # expose to the Quest (use the reserved domain)
```
> `.env` is cached at startup — **restart uvicorn after any `.env` edit.** Launch with explicit
> `PYTHONPATH=.` so module resolution doesn't depend on the cwd.

## The gen-path switch

`USE_HUNYUAN=true` (production) routes 3D generation through **Hunyuan3D-2mv** (RunPod
`itd7oz9wexb1oo`); `false` uses **TRELLIS** (`pz2c4wvo2rcdw9`). Everything downstream (Meshy
retex/rig/graft) is model-agnostic. **grep this flag before assuming which model runs.**

## Documentation

- **[`docs/USER-MANUAL.md`](docs/USER-MANUAL.md)** — full operational handbook: every layer, both GPU
  handlers, setup/run/test, config reference, ops footguns, troubleshooting. **Start here.**
- **[`docs/PROJECT-HOLOBORN-PRIMER.md`](docs/PROJECT-HOLOBORN-PRIMER.md)** — narrative onboarding (the why, the people, the scars).
- **[`docs/REFINEMENT-PHASE.md`](docs/REFINEMENT-PHASE.md)** — current phase + ranked backlog.
- `diaries/` — day-by-day record. `mistakes/` — the failure log. The institutional-knowledge layer is the asset.

## Status

Development cycle declared **complete 2026-05-27** (full autonomous e2e validated, council-graded a
legitimate autonomous-MR-embodiment POC). Now in a **refinement phase** — iterate quality on the
existing build, don't break the no-human-in-the-loop principle.
