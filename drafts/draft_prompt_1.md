# draft_prompt_1.md — Portraitizer prompt iteration log

This file tracks every revision of the GPT Image portraitizer prompt used by `app/services/portraitizer.py`. Each version stays here so we can A/B compare, regress test, or revert. **Do not edit V1 — it's the baseline. Add new versions as V3, V4, etc.**

---

## Active version: **V3** (set 2026-05-07)

V3 lives in `app/services/portraitizer.py` as `PORTRAIT_PROMPT_V3`. The constant `PORTRAIT_PROMPT = PORTRAIT_PROMPT_V3` is what the live code calls. To revert: `PORTRAIT_PROMPT = PORTRAIT_PROMPT_V2` (or V1).

---

## V1 — original (Apr 27 → May 4, 2026)

```
Transform this photo into a clean professional portrait. Studio lighting with
soft diffused front light. Plain white background, no other objects or
environment visible. Preserve the person's exact face, facial hair, skin
tone, hairstyle, clothing, accessories, body pose, and proportions. Full
body visible from head to feet. Do not change, stylize, or idealize any
facial features. Photorealistic output, not illustrated or painted.
```

**Length:** 434 chars · **Status:** retired May 4, kept as baseline

### Empirical result on `frame_0.jpg` (May 4 manual ChatGPT test)

- ✅ Outfit preserved (checked shirt, jeans, white shoes, red lanyard)
- ✅ Pose preserved (hands at sides, full body)
- ✅ Background became clean white
- ❌ **Face structure subtly idealized** — slight model-like proportions
- ❌ Hair density / hairline drifted slightly
- ❌ Body proportions slightly elongated (more "model" than "real person")

The drift was acceptable for a baseline GLB but visibly less identity-preserving than ideal.

### Why V1 drifts (root cause analysis)

| V1 line | Problem | Source |
|---|---|---|
| "Transform this photo into a clean professional portrait" | Triggers "polish/idealize" mode in gpt-image-1.5 | OpenAI cookbook §5 — *"avoid studio polish or staging language"* |
| "Studio lighting with soft diffused front light" | "Studio" is a stylization signal — model defaults to retouched-headshot mode | OpenAI cookbook anti-pattern list |
| "Photorealistic output, not illustrated or painted" | Too generic — Charlie Hills: *"Define realism with rules, not vibes"* | charliehills.substack.com/p/how-to-prompt-gpt-image-15 |
| Preserve list as flowing prose | Models respect enumerated negative imperatives ("Do not change X, Y, Z") more than positive list ("preserve X, Y, Z") | OpenAI cookbook §5.2 (virtual try-on) |
| No anti-idealization clause | Without "no glamorization, no heavy retouching, real skin texture" the model auto-improves features | OpenAI cookbook §5.8 |
| No camera/lens spec | "35mm documentary feel" anchors realism; missing it leaves room for stylization | fal.ai/learn/tools/prompting-gpt-image-2 |
| No `input_fidelity="high"` API param | Separate model parameter required for identity-critical edits — was missing entirely | OpenAI cookbook §1.3 |

---

## V2 — buffed for identity preservation (set May 4, 2026)

```
This is a candid documentary photo of a real person, not a portrait session.
Make ONLY ONE change: replace the background with a plain seamless white
backdrop (RGB 245,245,245 to pure white).

Do not change the person's face, facial features, facial hair, eye shape,
nose, jaw, skin tone, skin texture, hairstyle, hair density, expression,
clothing (including the lanyard with badge), accessories, body shape, body
proportions, pose, hand position, or footwear in any way. Preserve their
exact likeness as it appears in the source image.

Match the lighting direction, color temperature, and exposure of the original
photo. Light the subject as if photographed with available indoor light —
not flash, not studio strobe, not retouched headshot lighting.

Keep the person's full body visible from head to feet, centered, eye-level
framing, 35mm documentary lens feel.

Style: honest unposed documentary photography. Real skin texture with visible
pores and natural skin imperfections. Real fabric texture with visible weave.
Natural shadow falloff. No glamorization. No heavy retouching. No idealization
of features. Not illustrated, not painted, not stylized.
```

**Length:** 1155 chars · **Status:** active

### Required API param (also new in V2)

```python
client.images.edit(
    ...,
    input_fidelity="high",   # ← OpenAI's identity-preservation param
)
```

### What V2 fixes (line-by-line vs V1)

| V2 change | Why |
|---|---|
| Reframes opening to "candid documentary photo of a real person, not a portrait session" | Kills the "polish" mode at the source — model treats input as documentary, not as a styling task |
| "Make ONLY ONE change: replace the background" | Reframes the entire task as background-substitution, not portrait-creation. Per OpenAI's "change only X + keep everything else the same" canonical pattern |
| Background spec is precise (RGB 245,245,245 to white) | Removes interpretation — "plain white" was vague |
| 17-token negative-imperative preserve list | Direct "Do not change X, Y, Z" form. Includes specifics like "lanyard with badge" so accessories don't drop |
| "Match lighting / color temp / exposure of original" | Locks lighting to source, prevents the "headshot lighting" trigger |
| Negative anchors on lighting: "not flash, not studio strobe, not retouched headshot lighting" | Explicit bans prevent default behavior |
| "35mm documentary lens feel" | fal.ai pattern — anchors realism via camera language instead of vague "photorealistic" |
| Final paragraph: "real skin texture with visible pores and natural skin imperfections" | Anti-idealization grounding per OpenAI §5.8 + Charlie Hills |
| "No glamorization. No heavy retouching. No idealization of features" | Explicit triple-ban on the V1 failure mode |

### Empirical result for V2

**Skipped to V3** — V2 was never API-tested (OpenAI billing remained blocked through May 7). V3 superseded V2 on 2026-05-07 once the auto-rigging hypothesis was prioritized over pure identity preservation.

V2 stays in `portraitizer.py` as a fallback option (preserves the pose of the input — useful if input is already in canonical pose).

---

## V3 — A-pose conditioning for downstream auto-rigging (set 2026-05-07)

```
Generate a new full-body documentary photograph of the person from this image,
standing in a clean A-pose for 3D scanning.

Identity: same face, same eye shape and colour, same skin tone, same facial
hair, same hairstyle and density, same age, neutral relaxed expression.
Real skin texture with visible pores and natural asymmetry. Same body
proportions and limb lengths.

Clothing: same shirt with the same pattern and same colours, same jeans
with the same colour and fit, same lanyard around the neck with the same
badge attached, same footwear. Preserve fabric weave and texture; do not
flatten patterns into solid colour.

Pose, limb by limb:
- Body and head facing the camera directly.
- Both arms extended approximately 30 to 40 degrees away from the torso,
reaching toward the LEFT and RIGHT edges of the image. Arms NOT touching
the ribs or hips. Palms facing the thighs, fingers relaxed and slightly
curled.
- Both feet placed shoulder-width apart on the floor, NOT touching each
other, toes pointing forward toward the camera.
- Both legs straight but not locked, knees facing forward.
- Shoulders level, spine straight, weight even on both feet.
- Full body visible from the top of the head to the toes of both feet.

Background: plain seamless light-grey backdrop, RGB approximately
240,240,240. Subject centred horizontally and vertically. Slight headroom
above the head, slight floor visible below the feet.

Lighting: soft diffuse front key light, gentle fill from both sides, even
illumination across the body. No harsh shadows, no rim glow, no halo, no
coloured gels. Match the natural skin tone of the input photo; do not warm
or cool the colour temperature.

Style: shot on Hasselblad X2D with a 50mm lens, eye-level, f/8. Honest
documentary photograph, photorealistic. Real fabric texture, real skin
texture, natural shadow falloff. No retouching, no jaw sharpening, no eye
enlargement, no skin smoothing, no idealization. Not illustrated, not
painted, not stylised, not anime, not cartoon.

Do not add accessories, text, logos, or watermarks that are not present
in the input image.
```

**Length:** ~2200 chars · **Status:** ACTIVE (locked 2026-05-07)

### What V3 changes (vs V2)

| V3 change | Why |
|---|---|
| Reframes from "edit this photo" to **"Generate a new full-body documentary photograph"** | Empirical finding (north-47.com): generation-frame outperforms edit-frame for major pose changes. Edit-frame biases toward preserving input pose. |
| **Pose, limb by limb** explicit specification | Per-limb physical-state prose beats pose-name. "Both arms extended approximately 30 to 40 degrees away from the torso" works; "stand in A-pose" fails. (Threads/Nano Banana community finding.) |
| **Image-space directions** ("LEFT and RIGHT edges of the image") | Body-relative directions ("his right") fail because the model can't reliably resolve viewpoint. Image-space is unambiguous. |
| Drops V2's "Make ONLY ONE change: replace background" | V3 makes multiple changes (pose + lighting + background). Locking to "one change" prevents the pose change. |
| **Anti-stylization vocabulary expanded** to ban "anime, cartoon" explicitly | Charlie Hills + community finding: stylization triggers leak even with "photorealistic" anchor. |
| Camera spec upgraded: **Hasselblad X2D 50mm f/8** | Specific camera anchors realism better than generic "35mm." |
| Pose specifies **A-pose** (not T-pose) | Industry preference: A-pose has natural arm-torso separation; T-pose creates unnatural armpit topology that deforms badly during animation. |
| **For 3D scanning** framing in opening | Subtly tells the model the output's downstream purpose, biasing toward TRELLIS-friendly silhouette (clean limb separation, front-facing). |

### Empirical result for V3 (2026-05-07)

**Tested with ChatGPT web UI** (OpenAI billing still blocked, used web UI as workaround). Two inputs:
1. `tests/inputs/burst_5frames_quest_20260504/frame_0.jpg` — Quest single frame (dim ambient)
2. `results/originals/validate_20260506_074228_732813_bad.jpg` — face-occluded validate frame (bad input)

**Pose:** ✅ Both outputs achieved A-pose with arms 30-40° out, feet apart, body topology separable. Hypothesis target hit.

**Identity:** ⚠️ ~50% drift on the face for input 1, ~0% (impossible to assess) for input 2. Drift is concentrated in the face — features visible but eyes narrowed, jaw more angular, hair texture shifted. Body identity (proportions, build) preserved well.

**Clothing:** ✅ ~85% preserved — shirt pattern, lanyard, jeans, footwear all carried through. Slight badge-text simplification.

**Downstream rigging quality:** ✅ ✅ ✅ The whole point. Portrait A → RunPod → 28.3 MB GLB → Meshy auto-marker placement worked first try (all 14 skeleton markers correctly placed) → idle/walk animation played cleanly with NO wing-pants deformation. Architectural hypothesis empirically validated.

**Important caveat on identity drift:** the input frames had degraded face data (dim lighting on input 1, face occluded on input 2). Garbage-in-garbage-out is part of the failure. Future test on burst-averaged or deliberately well-lit input expected to reduce face drift significantly.

### V3 sources

- [north-47.com — selfie-to-studio Nano Banana pipeline](https://www.north-47.com/from-selfie-to-studio-shot-with-ai-to-standardized-corporate-employee-photos/) — generation-frame > edit-frame, image-space directions, affirmative > negative constraints
- [Threads — Nano Banana Pro pose-change prompt](https://www.threads.com/@prompts_.gpt/post/DWV2jShkcNe/) — per-limb physical-state prose pattern
- [binaryverseai — Drift Shield + one-change rule](https://binaryverseai.com/gpt-image-1-5-guide-consistency-api-pricing-tips/) — what NOT to write
- [OpenAI Cookbook — gpt-image-1.5 prompting guide](https://developers.openai.com/cookbook/examples/multimodal/image-gen-1.5-prompting_guide) — Virtual Try-On exemplar adapted for pose change
- Community-research synthesis (parallel agent run 2026-05-07) — identity-preservation ceiling realistic at 85-95%, clothing 60-75%, pose 50-70%, all-three-in-one-shot ~30-50%

---

## Sources used to design V2

- **OpenAI Cookbook (canonical):** https://developers.openai.com/cookbook/examples/multimodal/image-gen-1.5-prompting_guide
- **OpenAI Cookbook (general image models):** https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide
- **fal.ai gpt-image-2 production guide:** https://fal.ai/learn/tools/prompting-gpt-image-2
- **Charlie Hills indie blog:** https://charliehills.substack.com/p/how-to-prompt-gpt-image-15
- **OpenAI Help — prompt engineering best practices:** https://help.openai.com/en/articles/6654000-best-practices-for-prompt-engineering-with-the-openai-api
- **DALL-E 3 character consistency:** https://medium.com/ai-art-creators/character-consistency-in-dall-e-3-4777a100f74a

---

## Notes for V3+ (when V2 has empirical data)

- If V2 still drifts on **hairline shape** or **eyebrow density** specifically → add even more granular preserve tokens (e.g. "preserve exact hairline shape, hair part position, eyebrow shape and density, eye spacing, ear shape")
- If V2 still **stylizes the face** → try removing "candid documentary" reframe entirely and use only the negative-imperative preserve list — minimal-language version
- If V2 changes the **clothing colors** → add explicit color tokens: "navy blue checked shirt, dark indigo jeans, white sneakers, red lanyard"
- If portraits look too **flat** (lacking depth) → add "natural facial shadow falloff, depth from indoor side-light, no flash flatness"
- Consider testing a **multi-image input** version where image 1 = subject, image 2 = an example "good" reference background → may stabilize the white-backdrop result further

## Inputs always to test against

When evaluating future prompt versions, run on these specific frames so results are comparable:

1. `results/quest_test_uploads/multiview_20260504_070012_572dbcad/frame_0.jpg` — Quest passthrough single frame, real office scene, person standing
2. (Future: averaged 5-frame from same burst — generated by `burst_average()`, has noise reduction over single frame)

Save outputs as: `results/quest_test_uploads/portrait_v<N>_<timestamp>.png` for diffability.
