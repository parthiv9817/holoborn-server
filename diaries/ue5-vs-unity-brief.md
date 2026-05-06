# HoloBorn — UE5 vs Unity Engine Comparison

**Date:** 2026-04-27
**Context:** Founder (Vipin) pushing for UE5 migration. Unity source code lost when Mac died. Quest build survives on headset. Decision needed: rebuild in Unity or migrate to UE5.
**Decision:** UE5 migration approved. This document captures the full reasoning.

---

## 0. Operating Constraints for This Debate

- **No fixed demo deadline.** Phase-1 end-to-end proof will be re-recorded on the **current Mac (this rebuilt backend repo, `holoborn-server`)** once Vipin tops up OpenAI credits. The UE5 rebuild runs in parallel — it does **not** block demo readiness because the Phase-1 proof keeps existing as the artifact.
- **Founder's UE5 preference is a given input, not a debate variable.** Vipin (Master's in AI, years of industry experience) is pushing UE5. Agents should argue the technical/strategic merit of UE5 vs Unity *assuming the founder push exists*. Do not spend tokens on whether Vipin is right to prefer UE5 — treat it as fixed context.
- **Backend lives in this repo (`holoborn-server`).** The Mac FastAPI middleware that the Quest client (Unity today, UE5 tomorrow) talks to is already rebuilt and tested here. Whatever engine the client is in, this backend is the integration target.

---

## 1. Why This Decision Exists Now

The old Mac died on ~April 25, 2026. The Unity project (`~/HoloBorn9817/`) was never pushed to Git. The compiled Quest build survives on the headset, but all C# source code is lost. We are rebuilding from zero regardless — the question is which engine to rebuild in.

**Key files lost:**
- `ScanController.cs` — main state machine (~900 lines)
- `CameraFeedDisplay.cs` — passthrough camera → HUD
- `TagAlongCanvas.cs` — HUD follows head
- `CanvasPositioner.cs` — thumbstick fine-tuning
- `AvatarSpawner.cs` — GLB loading + spawning
- `FrameSender.cs` — legacy frame sender
- Unity project settings, scene files, prefabs, build configs

**What the Unity build did (functionality to replicate):**
- Quest 3 passthrough camera access via Meta XR SDK
- Live camera feed displayed on a floating HUD canvas
- HUD follows head with smooth lerp (TagAlong behavior)
- A button: burst capture 5 frames from same position
- X button: validate frame → revolve around subject → capture 30 frames at 12° intervals
- AR scan guides: floor ring, 30 capture dots, direction arrow
- HTTP POST to Mac server (validate-frame, generate-multiview)
- Poll for GLB completion every 3 seconds
- Download GLB → load via glTFast → spawn at floor level facing user
- Placeholder avatar while generating
- BypassCertificate for ngrok HTTPS

---

## 2. The Founder's Position

Vipin (Master's in AI) has been pushing for UE5 since early in the project. His reasoning (inferred from conversation history):

1. **UE5's rendering reputation** — Nanite, Lumen, MetaHuman-quality avatars. UE5 demo reels show photorealistic humans.
2. **Future-proofing** — if HoloBorn expands beyond Quest 3 to higher-powered devices (Apple Vision Pro, PCVR), UE5's advanced rendering features become available.
3. **Industry perception** — UE5 is seen as the "serious" engine for photorealistic applications.

**Vipin's earlier suggestions (from project history):**
- Suggested using UE5 for GLB generation on the backend (rejected: UE5 isn't a library, headless invocation costs ~1-2 min cold start, uses same algorithms available in Python)
- Suggested using LHM splats in UE5 for reconstruction (rejected: Quest uses mobile renderer regardless of engine, splats don't rig)

---

## 3. The Rendering Reality on Quest 3

### 3.1 What Quest 3 Actually Runs

Quest 3 has a Snapdragon XR2 Gen 2 — a **mobile chip**. Both Unity and UE5 use the **same class of mobile forward renderer** on Quest.

| Feature | Unity URP on Quest | UE5 Mobile on Quest |
|---------|-------------------|---------------------|
| Nanite (auto-LOD geometry) | Not available | Not available on Quest |
| Lumen (real-time GI) | Not available | Not supported in Mobile Forward |
| Ray tracing | Not available | Not available |
| Screen-space reflections | Not available | Not available |
| Forward rendering | Yes | Yes |
| Basic PBR materials | Yes | Yes (slightly better) |
| Subsurface scattering approx | Limited | Better approximation |
| Mobile post-processing | Basic | Slightly better tone mapping + AO |

**Source:** Meta's own documentation states Nanite is not available on Quest. Lumen is not supported in Mobile Forward with HDR Disabled (which is what Quest uses). Meta warns that UE5 apps may experience performance regression compared to UE4 due to rendering pipeline changes.

### 3.2 What Each Term Means (Non-Game-Dev Context)

**Nanite:** Automatic geometry streaming. A 10-million triangle model gets rendered by streaming only the visible triangles per pixel. No manual LOD creation needed. Film-quality assets at real-time speeds. **Requires desktop GPU — completely disabled on Quest.**

**Lumen:** Real-time global illumination. Light bounces realistically — a red wall tints nearby objects pink, sunlight fills rooms naturally. Traditional engines use pre-baked static lightmaps. Lumen is dynamic. **Requires desktop GPU — not available on Quest mobile renderer.**

**Ray Tracing:** Simulates individual light rays bouncing through a scene. Reflections, refractions, shadows all computed physically. How Pixar renders movies, but in real-time at reduced quality. **Requires RTX GPU — not available on Quest.**

**Mobile Forward Renderer:** The simplest, cheapest rendering approach. One light pass per object, no bouncing light, minimal dynamic shadows. Both engines use this on Quest because the XR2 is fundamentally a phone chip. **This is the ceiling for both engines on Quest 3.**

### 3.3 The Honest Implication

On Quest 3 standalone, both engines are driving the same Toyota. UE5 is a Ferrari — but only on PC/console hardware where Nanite, Lumen, and ray tracing are available. The avatar will look essentially the same on Quest regardless of engine choice.

---

## 4. Where UE5 Actually Wins (Even on Quest)

Despite the mobile renderer limitation, UE5 has a few real advantages:

### 4.1 Better Mobile PBR Materials
UE5's default material system has a more physically accurate skin response even on the mobile renderer. Subsurface scattering approximation works on mobile — gives skin a softer, more natural look instead of the "plasticy" appearance Vipin complained about. Unity URP's mobile shader is more basic.

### 4.2 Better Post-Processing Stack
Even on mobile, UE5 offers slightly better tone mapping and ambient occlusion approximation than Unity URP. Small differences, but visible in avatar close-ups.

### 4.3 Blueprint Visual Scripting
Faster prototyping for a solo developer. Logic can be wired visually without writing C++. Not a rendering advantage, but a productivity one.

### 4.4 MetaHuman Integration (Future)
If HoloBorn ever generates MetaHuman-compatible rigs instead of raw GLBs, UE5 is the native ecosystem. Not relevant today, but relevant for the roadmap.

---

## 5. Where UE5 Loses (Practical Concerns)

### 5.1 Runtime GLB Loading — THE CRITICAL RISK

HoloBorn's entire product depends on loading arbitrary GLBs at runtime (received from RunPod). This is the #1 technical risk of the UE5 migration.

| Engine | Runtime GLB Solution | Maturity |
|--------|---------------------|----------|
| Unity | glTFast | Battle-tested, 3 lines of code, handles 25-35MB avatars reliably |
| UE5 | glTFRuntime plugin (Roberto De Ioris) | Third-party, must verify Quest 3 compatibility |

**glTFRuntime** is the UE5 equivalent. It supports runtime loading of glTF/GLB files. **Must verify:**
- Does it work on Quest 3 (Android/ARM)?
- Does it handle 25-35MB GLBs without OOM?
- Does it preserve PBR materials on mobile renderer?
- Is it actively maintained?

**If glTFRuntime doesn't work on Quest 3, the UE5 migration is dead.** This is the single go/no-go check before committing.

### 5.2 Build Times
UE5 Quest builds take 2-3x longer than equivalent Unity builds. For a solo dev iterating rapidly, this compounds. A 5-minute Unity build becomes a 10-15 minute UE5 build.

### 5.3 C++ vs C#
Unity uses C# — managed memory, no segfaults, faster development cycle. UE5 uses C++ (with Blueprint as a visual alternative). C++ is harder, slower to write, and more crash-prone. Blueprints help but won't cover everything — custom HTTP handling, GLB loading callbacks, and camera access may require C++.

### 5.4 APK Size
UE5 Quest apps are typically 2-3x larger than equivalent Unity apps. Not a dealbreaker, but worth noting for distribution.

### 5.5 Learning Curve
Parthiv has 14 months of Unity experience and zero UE5 experience. He learned Unity in ~1 week for HoloBorn's needs. UE5 learning curve is likely 1-2 weeks for equivalent proficiency, but with more friction on Quest-specific setup (Meta OpenXR plugin, passthrough configuration, permissions).

### 5.6 Meta SDK Support
Meta's Quest development SDK (Meta XR SDK) has strong Unity support with extensive documentation and samples. UE5 support exists but is historically second-priority. Passthrough camera access, spatial anchors, and MR features may have fewer UE5 examples.

---

## 6. The "Code Is Lost" Factor

This is the strongest argument FOR migration. Analysis:

| Scenario | Effort | Risk |
|----------|--------|------|
| Rebuild in Unity | ~1 week (familiar territory) | Low — known platform, known patterns |
| Rebuild in UE5 | ~2-3 weeks (learning + building) | Medium — unknown platform, glTFRuntime dependency |
| Rebuild in Unity now, migrate to UE5 later | ~1 week now + ~3 weeks later = ~4 weeks total | Low now, high later (two rebuilds) |
| Rebuild in UE5 now | ~2-3 weeks total | Medium (one rebuild, learn once) |

**The math favors UE5 IF:**
1. glTFRuntime works on Quest 3 (must verify)
2. The roadmap includes Vision Pro or PCVR (where UE5 advantages materialize)
3. Vipin's push for UE5 means organizational alignment (fighting the founder wastes energy)

**The math favors Unity IF:**
1. glTFRuntime doesn't work on Quest 3
2. Speed to demo is the #1 priority (investor deadline, etc.)
3. HoloBorn stays Quest-only for the foreseeable future

---

## 7. Future Platform Analysis

### 7.1 Apple Vision Pro
- M2 chip — closer to laptop GPU than phone chip
- Apple Metal API supports advanced rendering
- UE5 can leverage more features: better materials, more complex shaders
- **UE5 advantage: REAL and significant on Vision Pro**

### 7.2 PCVR (Quest Air Link / Steam VR)
- Desktop GPU (RTX 3070+) available
- Nanite, Lumen, ray tracing all available
- **UE5 advantage: MASSIVE on PCVR**

### 7.3 Quest 4 / Future Standalone
- Unknown hardware, likely improved but still mobile-class
- May support limited Nanite/Lumen in future UE5 versions
- **UE5 advantage: SPECULATIVE**

### 7.4 AR Glasses (Meta Orion, etc.)
- Even more constrained than Quest 3
- Mobile forward renderer regardless of engine
- **UE5 advantage: NONE**

---

## 8. The Avatar Quality Question

**Does the engine affect avatar quality?**

The avatar quality problem is NOT the renderer. It's the input pipeline:
1. Quest 3 passthrough camera is 4MP with poor low-light performance
2. TRELLIS.2's DINOv3 backbone sees faces as ~11 patches (hard ceiling on face detail)
3. No identity preservation in the current pipeline

Switching engines does NOT fix any of these. The same GLB rendered in UE5 mobile will look essentially the same as in Unity URP. The "plasticy skin" complaint could be partially addressed by UE5's better subsurface scattering approximation, but it's a material tweak, not a fundamental quality improvement.

**What actually improves avatar quality:**
- Better input (burst averaging, portraitizer) ← already solved
- Better face enhancement (GFPGAN + ESRGAN) ← already on GPU
- Controlled lighting at capture time ← operational, not engine-related
- Future: identity-preserving face models (PuLID/InstantID) ← research, not engine-related

---

## 9. Vipin's Push — Why He's Not Wrong

Vipin isn't wrong to push UE5. He's thinking strategically:
- HoloBorn as a multi-platform product (Quest + Vision Pro + PCVR) needs UE5
- UE5's brand perception matters for fundraising ("built on Unreal Engine" sounds more serious than "built on Unity" to investors)
- The rendering advantages become real on higher-powered devices
- If migrating later is inevitable, migrating now (when code is already lost) is cheaper

**Where Vipin IS wrong:**
- Thinking UE5 will make Quest 3 avatars look dramatically better (it won't — same mobile renderer)
- Suggesting UE5 for backend GLB generation (UE5 isn't a library)
- Implying the engine is the quality bottleneck (it's the input pipeline and TRELLIS, not the renderer)

---

## 10. Decision Matrix

| Factor | Unity | UE5 | Weight |
|--------|-------|-----|--------|
| Quest 3 visual quality | 3 | 3.5 | HIGH — minimal difference |
| Vision Pro readiness | 2 | 4 | MEDIUM — future roadmap |
| PCVR readiness | 2 | 5 | LOW — not current target |
| Runtime GLB loading | 5 | 3 (unverified) | CRITICAL — product depends on it |
| Development speed | 5 | 3 | HIGH — solo dev, time pressure |
| Build times | 4 | 2 | MEDIUM — daily friction |
| Meta SDK support | 5 | 3 | MEDIUM — passthrough, MR features |
| Founder alignment | 2 | 5 | HIGH — fighting founder wastes energy |
| Learning curve | 5 | 2 | MEDIUM — 1-2 weeks to learn |
| Code is already lost | 3 | 4 | HIGH — rebuilding anyway |
| Investor perception | 3 | 4 | MEDIUM — "Unreal Engine" signals seriousness |
| Skin/material quality | 3 | 4 | LOW — material tweak, not engine limitation |
| APK size | 4 | 2 | LOW — not a dealbreaker |
| Community / tutorials | 5 | 4 | LOW — both have extensive resources |

---

## 11. Final Verdict

**Migrate to UE5.** Three reasons:

1. **The code is already lost.** Rebuilding effort is similar either way. The incremental cost of learning UE5 (~1-2 extra weeks) is a one-time investment vs. paying the migration cost later.

2. **Founder alignment.** Vipin wants UE5. Fighting this burns political capital on a decision where UE5 is defensible. Save the pushback for decisions that actually matter (like not using UE5 for backend GLB generation).

3. **Platform roadmap.** If HoloBorn targets Vision Pro within 6-12 months, UE5 is the right long-term choice. The rendering advantages that are locked on Quest become real on Vision Pro's M2 chip.

**Conditions / Blockers:**

- **MUST verify glTFRuntime works on Quest 3** before committing. If it doesn't, fall back to Unity. This is a 1-day spike, not a leap of faith.
- **Build backend first** (engine-agnostic). Backend works with any frontend — Quest Unity build today, UE5 build tomorrow.
- **Don't rebuild backend AND learn UE5 simultaneously.** Sequential, not parallel.

---

## 12. Migration Checklist

### Before starting UE5:
- [ ] Verify glTFRuntime plugin works on Quest 3
- [ ] Verify Meta XR SDK / OpenXR passthrough camera access in UE5
- [ ] Verify HTTP client capabilities in UE5 (FHttpModule or Blueprints)
- [ ] Mac backend fully working and tested with existing Quest Unity build

### UE5 features to implement (matching Unity build):
- [ ] Passthrough camera access (Meta OpenXR)
- [ ] Camera feed displayed on floating HUD
- [ ] HUD tag-along (follows head with lerp)
- [ ] A button burst capture (5 frames)
- [ ] X button single frame + revolve capture (30 frames at 12°)
- [ ] AR scan guides (floor ring, dots, arrow)
- [ ] HTTP POST multipart to Mac server
- [ ] JSON parsing for server responses
- [ ] GLB download and runtime loading via glTFRuntime
- [ ] Avatar spawning at floor level, facing user
- [ ] Placeholder avatar during generation
- [ ] HTTPS certificate bypass for ngrok

---

*This document captures the full UE5 vs Unity debate.
Reference it when the question comes up again — and it will.*
