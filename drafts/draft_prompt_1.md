# draft_prompt_1.md — Portraitizer prompt iteration log

This file tracks every revision of the GPT Image portraitizer prompt used by `app/services/portraitizer.py`. Each version stays here so we can A/B compare, regress test, or revert. **Do not edit V1 — it's the baseline. Add new versions as V3, V4, etc.**

---

## Active version: **V2** (set 2026-05-04)

V2 lives in `app/services/portraitizer.py` as `PORTRAIT_PROMPT_V2`. The constant `PORTRAIT_PROMPT = PORTRAIT_PROMPT_V2` is what the live code calls. To revert, change one line: `PORTRAIT_PROMPT = PORTRAIT_PROMPT_V1`.

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

**TBD** — will test once OpenAI billing limit is lifted.

Test plan when unblocked:
1. Same input frame: `frame_0.jpg` from `results/quest_test_uploads/multiview_20260504_070012_572dbcad/`
2. Same model: `gpt-image-2-2026-04-21` (latest accessible)
3. Compare V2 output side-by-side with V1 output (the May 4 manual ChatGPT test) and the source frame
4. Score: identity preservation, outfit fidelity, body proportions, drift on hairline/skin

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
