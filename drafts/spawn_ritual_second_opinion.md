# HoloBorn Spawn Ritual — Second-Opinion Brief

**Author:** Parthiv (associate AI engineer, working solo)
**Date:** 2026-05-08
**Audience:** ChatGPT and Gemini — please review and stress-test this design
**Goal:** Catch blind spots, surface alternatives, reality-check perf assumptions before I commit ~11 hours of implementation against a 2-day demo deadline

---

## TL;DR what I'm asking you

Stress-test the design below for a Quest 3 mixed-reality "avatar spawn ritual + world-anchored generation progress visualization." I have 2 days (today Fri 2026-05-08 + Saturday) before Sunday demo capture for a founder review. Roughly 11 hours of implementation budget. I cannot pivot to a fundamentally different visual approach mid-week and still ship.

I want your honest reads on:
- Whether the cube-assembly aesthetic is on-trend or already cliche in 2026
- Quest 3 / Unity URP perf gotchas with this approach
- The 3 phase beats I'm least confident in (P1 capture, P4 "thinking", P5 "rehearsing")
- Color choice (cyan default — alternatives I should consider?)
- What I'm probably missing entirely

Specific question list at the bottom.

---

## What HoloBorn is (project context refresher)

HoloBorn is a Meta Quest 3 mixed-reality app for hologram avatar generation. User presses a button on Quest, captures themselves via passthrough cameras, server processes the photo through a multi-stage pipeline, returns a rigged 3D avatar that spawns as a hologram in the user's room.

Pipeline: Quest captures → Mac server → OpenAI portraitizer (~30-60s) → RunPod TRELLIS GPU (~3-5 min) → Meshy auto-rig (~30-60s) → Meshy animation bake (~30-60s) → Quest spawns rigged GLB. Total: 7-10 minutes.

Validated end-to-end on 2026-05-07: a fully rigged Indian gentleman in cyan-lit MR passthrough, idling in the developer's office. ~28-second screen recording captured. Auto-rigging brick is dead. Today's work is the *premium UI layer* on top of the working pipeline.

Founder ask, verbatim: "Go wild. Make it feel like a premium product VR app, not a tech demo."

Constraint: solo dev, EOW deadline, all heavy lifting (TRELLIS, Meshy, OpenAI) is server-side and out of scope for this spec.

---

## Why we're not just building a 2D progress bar

A 2D progress bar fails in this context for two reasons:

1. **The user is in a room.** They have a 360° volumetric workspace. A flat HUD element trapped on glass at fixed depth feels like 2D thinking ported to VR — same trap that mobile-first products fail when they ship to spatial computing.
2. **They will literally stand and stare for 7-10 minutes.** Static placeholders or flat percentage bars over that duration feel like the system is broken. We need active visual content the user wants to watch.

The Gemini suggestion from yesterday's review ("a top-notch progress status bar") is the right intuition wrapped in 2D framing. The VR-native version is **the avatar building itself in the spot where it'll spawn, in front of the user, while they watch.**

---

## The proposed design (cube-cloud assembly)

### Aesthetic references for visual vocabulary

Watch in this order, fastest to slowest payoff:
1. **Westworld host construction scenes** (HBO S1) — primary reference, literal "person being built in front of you"
2. **Avengers: Endgame Iron Man Bleeding Edge nanotech** — particle/cube assembly snap-to-position
3. **Apple Vision Pro launch video** — "premium VR UI" baseline (clean, depth-layered, controlled motion)
4. **Iron Man 2/3 Jarvis hologram lab** — translucent geometric panels, layered holograms, cyan/orange accents
5. **Detroit: Become Human Kamski reveals** — minimal cyan/white from particle systems
6. **Ra.One / Transformers Galvatron build** — programmable-matter cube assembly

Shared language: room-anchored, depth-layered, controlled motion, monochrome accent (planning cyan), spatial audio coming FROM the holograms.

### Six-phase storyboard

```
PHASE 1 — Capture (instant, ~0.5s)
  • Particle burst from user's location (cyan, ~50 particles, 0.5s)
  • Cyan floor circle pulses at 1.5m forward (small marker, NOT a humanoid wireframe)
  • Soft "lock" sound + haptic pulse on left controller

PHASE 2 — Portraitizer (~30-60s)
  • Cubes start raining down from above into a slow vortex above the floor circle
  • ~50-100 cubes, orbiting slowly, cyan-tinted
  • Cube arrival rate: 5-10/sec
  • Soft thrumming spatial audio loop, floor circle pulses synced to thrum

PHASE 3 — RunPod TRELLIS (~3-5 min, the long one)
  • Vortex compresses; cubes start finding humanoid-silhouette positions
  • Arrival rate increases to 20-30/sec
  • Cubes "snap and stay" along the silhouette surface (sampled from final mesh verts)
  • RunPod % directly maps to silhouette completeness (0% empty → 100% full silhouette of ~300 cubes)
  • Color drifts cooler as % climbs

PHASE 4 — Meshy rigging (~30-60s)
  • Cube cloud is humanoid-shaped at this point
  • Bone-glyphs fade in INSIDE the cloud (skeletal preview through gaps)
  • Cloud pulses in waves — "thinking"
  • Soft chime per bone (~14 chimes total)

PHASE 5 — Meshy animating (~30-60s)
  • Cubes "wake up" — subtle motion mimicking the upcoming idle animation
  • Cloud rehearses faintly; builds anticipation

PHASE 6 — Spawn ritual (the 2.5s climax)
  • Cubes flow inward, snap to actual mesh vertex positions (vertex displacement shader)
  • PBR avatar mesh fades in underneath as cubes land (alpha 0→1 over 1.5s)
  • Settled cubes dissolve into emissive sparkles → vanish
  • Avatar's eyes briefly glow cyan (0.5s pulse), settle
  • Idle animation begins
  • Spatial whoosh + soft chime + haptic pulse
```

### Implementation order (foundations first, ~11hrs total)

1. Cube primitive + pool spawning system (~1.5hr)
2. Cube target-position lerp behavior (~1hr)
3. Vortex behavior (~30min)
4. Silhouette-sampling behavior (~1.5hr)
5. Snap-to-mesh + dissolve shader (~3hr)
6. Phase orchestrator state machine (~1.5hr)
7. Audio + haptics layer (~1hr)
8. Polish pass: color drift, bone glyphs, eye glow, particle dissolve (~1hr)

Steps 1-4 can be tested in Editor without Quest cycle. Step 5 onwards needs Quest test cycles (~5-10min per build cycle).

### Quest 3 perf budget

| Element | Count | Tris | Notes |
|---|---|---|---|
| Cubes (peak) | 300 | 12 each = 3,600 total | Low-poly, single material |
| Avatar mesh (final) | 1 | ~30,000 (Meshy decimation, validated 2026-05-07) | Already perf-validated |
| Floor circle | 1 | ~32 | Quad with circular alpha |
| Particle bursts | ≤50 | n/a | GPU-driven, Unity built-in |

Frame target: stays >72 fps in Quest Profiler during all 6 phases. Hard floor: never below 60 fps even at Phase 6 climax.

Fallback ladder: 300 → 200 → 150 → 100 cubes. Below 100, switch to Unity VFX Graph (loses per-cube control of snap-to-mesh — last resort).

---

## What I'm explicitly NOT asking for feedback on

(So please don't waste your context window on these — the 2026-05-06 cross-AI review already settled them):

- Glassmorphism HUD background — DROPPED, stays dropped
- Font swap / typography hierarchy — DROPPED, stays dropped
- Animated text fade transitions — DROPPED, replaced by world-anchored cube cloud
- Whether to use Meshy auto-rigging at all — LOCKED, validated 2026-05-07
- Whether to do procedural idle on top of Meshy clip — LOCKED in plan, separate from this spec
- Whether the founder cares more about presence vs cosmetics — already validated, presence wins

---

## Specific blind-spot questions (10 total)

I want your sharpest take on each. Don't be diplomatic — if you think something's wrong, say it.

1. **Cube-assembly aesthetic — on-trend or cliche?** Is this visual language overused in 2025-2026 era VR/MR demos? Are there specific products (Meta avatars, Spatial.io, RPM, etc.) that already shipped this exact effect? Risk of looking derivative.

2. **Phase 4-5 are my weakest beats.** "Cube cloud thinks" + "cube cloud rehearses idle" feel underspecified to me. Better treatments? Or should one of these phases be cut entirely (e.g., go straight from P3 silhouette-complete to P6 snap-spawn, skip rigging and animation visuals)?

3. **Quest 3 perf — 300 GameObject cubes vs Unity VFX Graph.** Concrete reasons to start with one over the other for our use case (need per-cube target-position control for snap-to-mesh)? URP-specific gotchas?

4. **Color choice — cyan default.** Cyan matches Apple Vision Pro / Detroit / Iron Man references but might feel default. Alternatives: warm orange (Halo Forerunner), white-only no color (Apple/clinical), green (Matrix/digital). What would you pick for HoloBorn specifically?

5. **Where do cubes come from?** Currently "rain from above." Alternatives: emerge from floor, materialize at random points around user, flow from where user stood at capture, flow from a fixed beacon point in the room. Affects spatial storytelling. Best fit for HoloBorn's avatar-from-photo metaphor?

6. **Capture moment particle burst — appropriate or noisy?** P1 burst from user might fight with downstream cube assembly. Should it be a single bright "lock" flash instead? Or no visual at all (just audio + haptic)?

7. **Phase 5 "cube wake" — whole-cloud motion or per-cube offsets?** If cubes rehearse animation, are they doing whole-cloud bob, or per-cube position noise? Whole-cloud might read "cloud is bouncing," per-cube might read "noise." Open.

8. **Eye-glow at spawn — natural or cheesy?** Eye-glow is gold-standard "alien arriving" beat (every robot intro since the 80s) but might read cheesy in 2026. Alternative beats: brief breath-in animation, slight head turn toward user, hand unclench. Your take?

9. **Spatial audio mix — P2 thrum looping for 3-5 minutes during TRELLIS.** Does that grate or feel ambient? Audio fade-in/out per phase, or continuous? Should the thrum vary in intensity with TRELLIS progress %?

10. **Anything we're missing entirely?** Open prompt for blind spots. Gaze, lighting integration with passthrough, room-scanning UX, social/observer perspective, accessibility, anything else.

---

## What I want back from you

Not a thumbs-up. Concrete, specific, prioritized:

- **Top 3 risks** in this design ordered by severity
- **Top 3 alternatives** to specific design decisions, with why they might be better
- **Concrete cuts** I could make if I'm running out of time on Sunday morning
- **Anything you'd kill outright** and replace with something fundamentally different

I trust your pushback more than your validation. If the whole design is on the wrong track, tell me — better to find out today than Sunday morning.
