# 2026-05-11 Evening Handoff — Reading list for the new Claude session

**Written 2026-05-11 ~16:30 by the session that lost the user's trust.**
**Purpose:** focused reading list for the new Claude session so it can pick up Unity Phase B cleanly without repeating today's mistakes.

---

## Read these IN THIS EXACT ORDER before doing anything

### Priority 1 — TODAY'S CONTEXT (must read first)

1. **`mistakes/2026-05-11.md`** — six anti-patterns the previous session exhibited. Read this BEFORE the diary so you know what NOT to do. The throughline: drift from agreed plan during execution + treating user frustration as their kryptonite when actually it was the session's sloppiness.

2. **`diaries/2026-05-11.md`** — full session brain-dump. What was built, what got drifted, exact code state, what's open. Required for cold-start orientation.

3. **`/Users/digispoc06/.claude/projects/-Users-digispoc06-Documents-holoborn-server/memory/feedback_no_timeline_pressure_framing.md`** — newest feedback memory from today. Read it. Live by it. Don't propose scope-cut subsets without explicit user authorization.

### Priority 2 — THE PLAN BEING BUILT

4. **`docs/superpowers/plans/2026-05-11-origin-story-ui.md`** — v2 origin story UI implementation plan. THIS IS THE SPEC. Don't propose downgrades to this. Mannequin + cyan floor circle + scan-line transition + biological awakening — all four, as written.

5. **`drafts/origin_story_ui_visualization_brief.md`** — the 7-frame visualization brief that produced the Gemini concept art the user is using as mental-model anchor. Frame 1-2 specifically: pale white mannequin + cyan floor circle UNDER it. Both visible.

6. **`drafts/glb_stage_transitions_round5_brief.md`** — Round 5 cross-AI brief for the council. Context for why we ended up at the Approach H design.

### Priority 3 — SATURDAY'S CONTEXT (still operative)

7. **`diaries/2026-05-09.md`** — Saturday's full brain-dump. End-to-end pipeline shipped on Quest, plastic GLB diagnosis, cube cloud aesthetic failure on device.

8. **`mistakes/2026-05-09.md`** — six instances of "predicting visual outcome → device disagreed → user was right." Today's mistakes are the next-day evolution of this anti-pattern.

9. **`docs/superpowers/handoff/2026-05-11-monday-handoff.md`** — what this session was supposed to do today.

### Priority 4 — REFERENCE / CODE STATE

10. **`CLAUDE.md`** — project overview, architecture, Quest contract, RunPod endpoint config.

11. **`/Users/digispoc06/.claude/projects/-Users-digispoc06-Documents-holoborn-server/memory/MEMORY.md`** — full memory index (auto-loaded but verify it).

12. **`app/services/meshy_client.py`** — new this session, retexture endpoint client. Don't touch unless something demonstrably broken.

13. **`app/services/generation_pipeline.py`** — modified this session, now chains TRELLIS → Meshy Retexture. Same caveat.

14. **`/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scripts/SpawnRitual/SpawnRitualStateMachine.cs`** — refactored to 3-stage origin story (Idle/ShellManifest/Revealed/Awakened/Failed). Tests at `Tests/EditMode/SpawnRitualStateMachineTests.cs` — 12 cases.

15. **`/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scripts/SpawnRitual/SpawnRitualController.cs`** — refactored events (OnShellManifestEnter / OnRevealedEnter / OnAwakenedEnter / OnFailedEnter).

16. **`/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scripts/SpawnRitual/AnatomicalMannequinController.cs`** — written this session, NOT YET WIRED in scene. Will likely need re-evaluation of approach (see plan).

17. **`/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scripts/AvatarSpawnPhaseDriver.cs`** — refactored to subscribe to OnRevealedEnter. Loads clean Meshy GLB via TestGlbLoader.

---

## What's already done (don't redo)

✅ Backend Meshy Retexture chain — production-ready, key swap is the only pending action
✅ Unity Phase A (state machine refactored, cube cloud deleted, tests green)
✅ Unity C# scaffolding for Phase B (AnatomicalMannequinController.cs)

---

## What's open

❌ **Mannequin prefab + material** — user deleted previous attempt because the cyan emission was too aggressive (Tron lightcycle instead of subtle rim). Stock URP/Lit emission applies uniformly to translucent surfaces — won't give edge-only rim. **Probably need to build a Shader Graph with Fresnel node** for proper rim effect. This is the FIRST decision the new session needs to make.

❌ **Cyan floor circle prefab** (GroundShadow_Prefab) — Quad + transparent emissive cyan material, saved as prefab. Should be the visually dominant cyan element per Gemini's concept art.

❌ **Wire AnatomicalMannequinController in scene** — attach to SpawnRitualController GameObject, wire Inspector refs (Mannequin Prefab, Head Transform → CenterEyeAnchor, Grounding Shadow Prefab).

❌ **Stage 1→2 scan-line transition** (Phase C of v2 plan) — vertical scan + emissive boundary quad, custom shader graph for clip-plane effect.

❌ **Stage 2→3 biological awakening** (Phase E of v2 plan) — breath + gaze acquisition + idle animation start.

❌ **Failure mode HUD messages** (Phase G of v2 plan).

❌ **Quest device verification + demo capture** (Phases H + I).

---

## Behavioral protocol for the new Claude

1. **No timeline pressure framing.** Vipin values product over deadline. Don't propose "shippable subsets" without authorization.

2. **No unauthorized downgrades.** v2 plan is the spec. If user asks "where's X," confirm X is in the plan + we'll build it in order. Don't propose dropping X.

3. **Engineer-level Unity instructions.** User has shipped the entire pipeline. They know Unity. No "press F to frame" basics. Trust them to handle Quad creation, material setup, prefab dragging.

4. **Brick = coherent artifact with verifiable end state.** Not atomic clicks. Not multi-feature mega-steps. One artifact, one verification.

5. **Pause to confirm mental model before each major brick.** Especially for visual work: "what's the dominant element you see when this state activates?" That's the priority order for implementation.

6. **Trust user's eye on device.** When something looks wrong on Quest, it's wrong. Don't argue from spec. Saturday's mistake #3 still applies.

7. **Don't pattern-match user frustration as kryptonite.** Sometimes it's earned by the session's sloppiness, not the user's fatigue. Take the L when warranted.

---

## First message recommendation (for new Claude to send user)

> "I've read today's diary + mistakes + the v2 plan + Gemini's visualization brief. Backend is production-ready awaiting Vipin's Meshy key. Unity Phase A is complete (state machine refactored, cube code deleted, tests green). What's open: build the Mannequin and floor-circle prefabs, wire them in scene, then Phase C (scan-line) and beyond.
>
> Before we build the mannequin material — heads up that stock URP/Lit emission gives a uniform glow, not edge-only rim. To get the 'subtle cyan rim on silhouette edges' look from Gemini's concept art, we'd need to make a Shader Graph with a Fresnel node + Emission output. Want me to walk you through that, or would you rather try stock URP/Lit at low emission intensity first as a quick-test?
>
> Whichever you pick, I'll give it as one brick with a verifiable end state. No micro-instructions."

That's the right opener. Honest about what works (backend, state machine), honest about the open technical decision (stock vs shader graph for rim), gives the user a clean choice.

---

## One last note

The user said *"you've made this too complex by iterating variables from previous Unity versions don't know where the components are but confidently saying yo it's there."* That's true and important — without eyes on their Unity Editor, the previous session was guessing at UI element locations. The new session should:

- Ask which Unity version they're on (visible in the title bar — was 6.4 in screenshots today)
- For genuinely version-specific Unity UI questions, ask the user to send a screenshot rather than guessing
- For technical decisions (shader graph, material setup), give the technical answer without prescribing exact UI clicks

Walk forward. Brick by brick — but real bricks, not click-by-click. The user shipped a pipeline. Trust them.
