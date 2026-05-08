# Founder update — 2026-05-06

**To:** Vipin
**Subject:** HoloBorn EOD update — full PBR avatar shipped end-to-end on Quest, EOW plan locked

---

Hi Vipin,

**Today's headline:** the full pipeline is working end-to-end on Quest 3 in MR. Quest captures the photo, my Mac backend forwards it to RunPod, the GPU returns a TRELLIS GLB, and the avatar materializes in the user's room with full PBR rendering — skin tones, clothing, accessories, the lanyard with the company ID card all visible. Same quality bar as the previous build's reference shot. Screenshot attached.

The hardest brick of the project — getting glTFast PBR shaders to survive Unity's URP build pipeline on Quest — is now solved cleanly using Unity's officially documented approach (Resources/ folder placeholder Materials), not a hack. Code committed and pushed to both `holoborn-quest-unity` and `holoborn-server` GitHub repos.

---

**Your three asks — locked into the EOW plan:**

1. **Animation (avatar feeling alive, not standing like a duck):** Meshy Rigging API integration for the idle skeleton + procedural breathing/sway/head-look-at-user layered on top in Unity. The procedural layer ships even if Meshy has issues with any specific generated mesh — guaranteed alive feel as a parachute. Slated for Thursday.

2. **Premium VR UI:** Stress-tested the polish plan against ChatGPT and Gemini before locking it. Both converged on the same priority order: spawn moment → idle motion → audio/haptics → lighting → mesh → UI typography. Final stack: holographic 3D-print spawn reveal (feet-up materialization with emissive edge), spatial audio cues, controller haptics on key moments, blob shadow under feet for grounding, gaze-reactive avatar that occasionally looks at the user. Aesthetic direction: Apple Vision Pro / Iron Man hologram lab — clean, minimal, precise. Slated for Friday.

3. **Metrics visibility for the GLB load:** Solving this with a world-anchored progress visualization rather than a 2D loading bar. During the 3-5 min generation wait, a wireframe placeholder appears at the spawn location in the user's actual room and fills in progressively — capture → upload → queued → generating (X%) → rigging → materializing. Tells the user "the magic is happening over there" and anchors attention to physical space. Reads as a premium product feature, not a wait screen.

---

**Timeline:**

- Thu (May 7): animation pipeline (Meshy + procedural) + multi-seed TRELLIS quality lottery
- Fri (May 8): spawn ritual + spatial audio/haptics + progress visualization + lighting integration
- Sat-Sun: demo capture, retakes until clean, MP4 to you Sunday evening

---

**One blocker that needs your help:** OpenAI billing has been hard-limited since Monday (May 4) — every image generation call returns `400 billing_hard_limit_reached`. I've raised this with Tapasya three times over the past three days, no response. The portraitizer step (GPT Image 1.5 → studio-lit input → TRELLIS) is empirically load-bearing for material quality on the avatar — without it, geometry is fine but textures come out muddier than they could. The current demo path uses the raw-burst → RunPod fallback (working, but visibly less crisp). Could you raise the billing limit on the OpenAI dashboard, or transfer ownership of the request to whoever can move it today? Happy to take dashboard access directly if that's faster.

---

Will send the demo MP4 Sunday. Animation working in MR by Thursday EOD as the next milestone.

Thanks,
Parthiv
