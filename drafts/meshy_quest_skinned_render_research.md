# Meshy -> Quest URP Skinned-Mesh Rendering — Research

Date: 2026-05-07
Authoring context: HoloBorn EOW demo, Unity 6000.4.5f1, URP, glTFast 6.18.0, Quest 3, IL2CPP/ARM64.
Stack under test: TRELLIS-2-4B static GLB -> Meshy auto-rig + animation library bake -> 1 mesh, 1 skin, 26 nodes, 193k tris, 96k verts, 4 baked AnimationClips.

---

## TL;DR

1. **The single highest-confidence root cause of the wet/oily/sparkly artifacts is bad / non-MikkTSpace / non-normalized tangent data interacting with skinning math.** Every signal points here:
   - The artifact only appears on the *animated* (skinned) variant — static rigged passes clean. Skinning is the only path that mutates tangents per-frame.
   - `Mesh.RecalculateTangents()` post-spawn helped *partially*, which is the textbook fingerprint of a tangent-basis mismatch (Unity forum thread "RecalculateTangents breaks existing normal map" describes this exact failure mode — the recalculated tangents disagree with the convention the normal map was baked in, so lighting goes wrong but in a different way).
   - Babylon shows the same artifacts plus inverted-normal headlessness on the same file. Babylon is a stricter glTF-spec viewer than Meshy's own preview, which is the textbook fingerprint of a GLB exporter that ships visually-OK content via lenient defaults.
2. **Highest-leverage fix to try first:** stop calling `RecalculateTangents` ourselves, add the `GLTFAST_SAFE` scripting define so glTFast renormalizes bone weights at runtime, and import the GLB through Blender's glTF Import (which forces MikkTSpace tangent recomputation on the unindexed mesh) -> re-export -> re-test on Quest. If that resolves the sheen, the bug is Meshy not exporting MikkTSpace-correct TANGENT attributes on the skinned mesh.
3. **193k tris is ~3-6x over budget for a single Quest 3 animated humanoid.** Meta's documented per-frame budget is 1.3M-1.8M tris for the whole frame on Quest 3. Ready Player Me ships full-body avatars at ~6k-15k tris with a 50-75% LOD reduction option. Mixamo / VRChat-Quest avatars target 5k-30k. Even if rendering were clean, 193k for one character is a perf cliff before any background.
4. **Quest URP requires Skin Weights ≤ 2 (Meta's own guidance).** glTFast imports all 4 bone weights at design time but the QualitySettings.skinWeights cap will silently drop influences at runtime. Meshy's auto-rig will saturate 4 bones per vertex; on Quest, the bottom 2 get dropped and you get visible deformation seams along the skinning falloff. This is consistent with "shimmer concentrated on shirt + jeans during animation" (high deformation zones).
5. **Two-track plan:** (A) ship-fix path — run the GLB through `gltf-transform weld + simplify --ratio 0.15` (193k -> ~30k) and `gltf-transform optimize` to renormalize attributes, then re-test. (B) root-cause path — confirm with the static-rigged-no-animation GLB whether the rig process or the playback math triggers the issue. If (A) ships, do (B) post-demo.

---

## A. Why Meshy preview is clean but Babylon / Quest URP isn't

### A.1 What Meshy uses to preview their own output

Meshy does not publish their preview stack. Their `meshy.ai/3d-tools/online-viewer/glb` page advertises an in-house viewer with auto-rotate / grid options ([Meshy GLB Viewer](https://www.meshy.ai/3d-tools/online-viewer/glb)). No primary source confirms Three.js vs Babylon.js vs custom WebGL — multiple searches for "Meshy preview Three.js Babylon" returned no answer. The behaviorally relevant question, though, is not *which* engine but *what defaults they apply*. Two telltales from your evidence:

- **Headless / missing-face-on-Babylon was solved by setting `_Cull = 0` everywhere.** Babylon.js's GLB loader strictly honors `material.doubleSided`. If Meshy's preview ships with backface culling forced off (or if their preview swaps the loader for `babylonjs.loaders.min.js`'s alternate path), the missing-face issue is masked. The Babylon forum confirms exactly this disparity: a user on the [Normals reversed imported glTF](https://forum.babylonjs.com/t/normals-reversed-imported-gltf/5941) thread found that one Babylon loader inverted normals while another didn't — same GLB, different visual result. So Meshy's GLB very plausibly has `material.doubleSided = false` even though some faces have inverted normals; their preview just doesn't cull, and so the bug is invisible.

- **The "wet/oily" sheen on PBR is a tangent-basis artifact.** This is independent of the engine: any normal map sampled with the wrong tangent space produces directional sheen that wobbles when the surface deforms. If Meshy's preview either (a) recomputes MikkTSpace tangents at load time, (b) rasterizes through a renderer that uses derivative-based tangent reconstruction (avoiding the stored TANGENT attribute), or (c) shows their preview from an internal cache that still has source-engine tangents, the GLB on disk can be wrong while the preview is fine.

### A.2 Meshy's glTF export quirks

The official Meshy auto-rigging API doc ([docs.meshy.ai/en/api/rigging-and-animation](https://docs.meshy.ai/en/api/rigging-and-animation)) is silent on:

- Whether the rigged GLB preserves the input mesh's TANGENT attribute or regenerates it
- What MikkTSpace convention is used (or if they even compute tangents)
- Whether bone weights are normalized (sum to 1.0)
- Whether the rig step modifies vertex order, normals, or UVs

Meshy's own docs only commit to "industry-standard bone hierarchies" with "bones, weights, and animations transfer[ring] cleanly" ([Meshy Unity integration guide](https://help.meshy.ai/en/articles/11973241-integrating-meshy-assets-into-unity-unreal-engine)) — no mention of glTF spec compliance for vertex attributes.

Two things this matters for:

1. **MikkTSpace requires unindexed (unwelded) input** ([Khronos glTF spec discussion](https://github.com/KhronosGroup/glTF/issues/2056)). Most pipelines weld vertices for compactness, then run MikkTSpace, then re-index. If Meshy skips the unweld step, their tangents are mathematically not MikkTSpace-canonical, so any client that re-bakes MikkTSpace tangents (Babylon, Unity glTFast) gets a basis mismatch with the normal map.

2. **glTF tangent.w sign convention requires a flip.** Quoting the spec discussion verbatim: *"When generating vertex tangents for glTF 2.0 assets, you will want to flip the sign of the tangents (tangent.w *= -1) before storing them in the glTF file."* If Meshy's exporter forgets this flip, every viewer that follows the spec computes the bitangent with the wrong handedness, and on a *deforming* surface this manifests exactly as our artifact: shimmer concentrated where the skinning math twists the surface most.

### A.3 Verbatim community reports of the same disparity

- glTFast issue #340 ("[Missing normal must be calculated as flat normals](https://github.com/atteneder/glTFast/issues/340)"): the reporter shows a comparison render where glTFast and a web viewer disagree *for the exact same GLB* when normals are missing. Quote: *"tangent should be not smoothed if there are no normals included in glTF."* If Meshy ships a GLB without NORMAL on the skinned mesh, glTFast and Babylon will compute different fallbacks and produce different shading.

- glTFast issue #282 ("[Scrambled Normal Maps after meshopt compression](https://github.com/atteneder/glTFast/issues/282)"): only affects meshopt-compressed files. We don't think Meshy uses meshopt, but worth running `gltfpack` to confirm. Symptoms: *"normal maps appear to be completely scrambled and reduced to noise."*

- glTFast issue #437 ("[Import setting to enforce normals/tangents on meshes](https://github.com/atteneder/glTFast/issues/437)"): this is the killer. Quote: *"glTFast only computes tangents when required by a material."* Meaning: if Meshy ships the GLB *without* TANGENT and our material doesn't yet have a normal map bound at the moment of import, glTFast skips tangent generation entirely. Then later, if anything (URP shader path, our `RecalculateTangents` call, GPU skinning) needs tangents, they're either zero or implicitly recomputed under non-MikkTSpace defaults.

- glTFast 6.18.0 changelog entry ([changelog](https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.18/changelog/CHANGELOG.html)): *"Back-face normals are now correctly flipped in URP (fixes #38)."* This was fixed in our exact version, but the prior wrongness fingerprint matches the Babylon headlessness — many GLBs in the wild were authored to depend on the broken behavior, and Meshy's preview may be one of them.

- glTFast 6.16.1 changelog: *"Incorrect normal unpacking when using default normal map on Android (fixes #791 and #802)."* Quest = Android. We are on 6.18.0 so we should have this fix, but worth verifying the `Resources/` placeholder material's `_BumpMap` is actually being consumed (not the default normal).

- Three.js forum, [Texture Artifacts ONLY in Meta Quest 3 Browser](https://discourse.threejs.org/t/texture-artifacts-only-in-meta-quest-3-browser/88506): a developer hit *"jagged / 'cut' or shimmering"* artifacts only on Quest 3, fixed by changing shader precision from `mediump` to `highp`. URP Shader Graph's PBR variants default to `half`/medium precision on mobile. Could compound with our tangent issue.

---

## B. Quest 3 mobile VR animated character constraints

### B.1 Recommended polycount

Sources, ranked by authority:

| Source | Total per-frame budget (Quest 3) | Per-character |
|---|---|---|
| Meta official ([Unity perf docs](https://developers.meta.com/horizon/documentation/unity/unity-perf/)) | **1.3M-1.8M tris** per frame | not specified |
| Ready Player Me ([Modeling guidelines](https://docs.readyplayer.me/ready-player-me/customizing-guides/create-custom-assets/modeling-guidelines)) | n/a | Their full-body avatar is ~6k tris on Sketchfab ([example](https://sketchfab.com/3d-models/ready-player-me-female-avatar-vrchatgame-4b58e590e9fc422dbbf176c1848dc898)). Their LOD parameter offers 75% reduction on top of that. |
| VRChat on Quest (community-documented) | n/a | 5,000 tris max for "good" avatar rating, 1 material, 3 draw calls, 66 bones |
| Meshy's own guidance ([Mesh topology guide](https://www.meshy.ai/blog/optimize-3d-models-for-better-quality)) | n/a | Their guide says "30k-100k for PC/console targets" — implicitly *over budget* for Quest |
| Meta Avatars SDK | n/a | Meta's first-party avatars target ~30k-50k tris (community-reverse-engineered, no official figure) |

**At 193k tris on a single character with full PBR + skinning + animation, we are 3-6x over the safe per-character budget on Quest 3, and we will eat 11-14% of the *whole frame's* triangle budget on one avatar with nothing else in the room.** That alone won't cause the wet/oily artifact, but it does mean GPU is under more pressure, which makes any precision/aliasing issue worse.

Recommended target for HoloBorn EOW demo: **15,000-30,000 tris**. This matches Wolf3D / Mixamo / Meta first-party output and gives 4-5x headroom for the rest of the scene.

### B.2 CPU vs GPU skinning on Quest 3

- Meta's official stance ([Tech Note: Unity Settings for Mobile VR](https://developers.meta.com/horizon/blog/tech-note-unity-settings-for-mobile-vr/)): **"GPU Skinning: Enabled for VR apps using OpenGL ES 3."** Vulkan path same recommendation in practice.
- Counter-evidence: Unity Discussions thread "[Skinned Meshes With GPU (Batched Skinning) Breaks on Android Build](https://discussions.unity.com/t/skinned-meshes-with-gpu-batched-skinning-breaks-on-android-build/1693083)" — Unity staff confirmed Dec 3, 2025: *"we've identified the changes that caused this issue. We don't have a fix yet."* Symptom: corrupt skinning, only on `GPU (Batched)` mode, only on Android build, fine in editor. CPU and plain GPU modes both work.
- Practical recommendation: set Project Settings > Player > Other Settings > **GPU Skinning = GPU (not "GPU (Batched)")**. If still artifacted, drop to CPU as a diagnostic. CPU skinning on a 96k-vert mesh is ~1ms/frame on Snapdragon XR2 Gen 2 — acceptable as a debug knob even though we wouldn't ship it.

### B.3 Normal map sampling on skinned meshes (mobile URP)

This is where the static-vs-animated differential lives. Direct quotes from the research:

- Unity Discussions "[Skinned Mesh Renderer - Update Normals](https://forum.unity.com/threads/skinned-mesh-renderer-update-normals.375497/)": *"On mobiles, normals/tangents are not normalized after skinning on the CPU, so if you are writing your own shaders, you should handle the normalization yourself."* The glTFast/URP `Shader Graphs/glTF-pbrMetallicRoughness` may or may not include the post-skinning re-normalize, depending on which precision target it compiles for.

- Stanford skinning paper context (general): linear blend skinning of the tangent vector produces a tangent that is *not unit length* and *not orthogonal to the post-skinning normal*. If the shader uses the stored tangent without re-orthonormalizing, the bitangent reconstruction `cross(N, T) * T.w` produces a basis that drifts as joints rotate. This is exactly the "wet/oily" sheen — directional reflectance that wobbles with bone rotation.

- The fix landscape:
  - Force `precision highp float` in the URP shader graph (not exposed by default on URP/Lit; you'd need to drop to a hand-written shader).
  - Re-orthonormalize tangent in the vertex output of the shader graph.
  - Or: ensure the *stored* tangents are MikkTSpace-canonical so the LBS-induced drift averages out across triangles consistent with the normal map's bake convention.

### B.4 Bone influence count

- Meta's explicit guidance: **"Blend Weights: not be set to more than 2 bones"** ([Tech Note: Unity Settings for Mobile VR](https://developers.meta.com/horizon/blog/tech-note-unity-settings-for-mobile-vr/)).
- Unity Quality Setting `skinWeights` caps how many bone influences the runtime uses, regardless of mesh data ([scripting API](https://docs.unity3d.com/ScriptReference/QualitySettings-skinWeights.html)).
- glTFast 4.8.0 changelog: *"All four bone weights are imported at design-time, regardless of quality setting."* So our mesh has 4 weights per vertex from Meshy, but Quest URP runtime will use 2.
- glTF spec allows up to 4 bone influences in JOINTS_0/WEIGHTS_0; an 8-influence mesh adds JOINTS_1/WEIGHTS_1 ([glTF spec](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html)). Meshy almost certainly outputs 4 (single set). Not the issue, but confirms we're not over the spec.
- The dropped influences (3rd and 4th, sorted by weight) cause deformation discontinuity along seams. If Meshy distributes weights densely (typical of auto-riggers — they don't aggressively prune to 2), the runtime drop will visibly tear/shimmer on bend zones (shoulders, hips, knees) — matches "shirt + jeans during animation."

### B.5 Other Quest-specific aliasing/shimmer mitigations

From [Meta's Common Rendering Mistakes blog](https://developers.meta.com/horizon/blog/common-rendering-mistakes-how-to-find-them-and-how-to-fix-them/):
- **4x MSAA** mandatory.
- **Mipmaps + trilinear filtering** on every texture (note: glTFast `ImportSettings.GenerateMipMaps` defaults to false; we should set it to true).
- **Anisotropic filtering** for oblique surfaces.
- **Mipmap bias of -0.7** for high-detail textures.
- Confusing twist: Meta's own Mobile VR tech note says *"Anisotropic Filtering: Disabled due to ARM Mali GPU limitations."* That's outdated guidance from the Quest 1 era (Mali GPU). Quest 3 is on Adreno 740, no such limit. Use anisotropic 2x or 4x.

---

## C. glTFast 6.18 specific quirks

### C.1 Verbatim relevant changelog entries

From [glTFast 6.x changelog](https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.18/changelog/CHANGELOG.html):

- **6.18.0:** *"(Shader) Back-face normals are now correctly flipped in URP (fixes #38)."*
- **6.16.1:** *"Implicit/add normals to the vertex attribute layout if tangents are required."* AND *"Incorrect normal unpacking when using default normal map on Android (fixes #791 and #802)."*
- **6.16.0:** *"Normal map scale on shader graphs"* fixed. *"Incorrect normal unpacking when using default normal map on Android."*
- **6.13.0:** *"Use XYZ-style normals in shaders even if DXT5nm-style is enabled."*
- **6.5.0:** *"Vertex attributes are discarded if they are not used/referenced."*
- **6.3.0:** *"Draco compressed tangents import tangents correctly now"* (was being recalculated, now correctly decoded). *"Removed invalid attempt to calculate normals or tangents on point or line meshes."*
- **4.8.0 (still relevant):** *"Re-normalize bone weights (always for design-time import and opt-in at runtime via `GLTFAST_SAFE` scripting define)."*

### C.2 Settings worth trying that we haven't

| Setting | Where | What it does | Try? |
|---|---|---|---|
| `GLTFAST_SAFE` scripting define | Project Settings > Player > Scripting Define Symbols | Renormalizes bone weights at runtime, plus other safety checks | **Yes — high priority. Meshy's auto-rig may produce non-normalized weights.** |
| `GLTFAST_KEEP_MESH_DATA` | Same | Keeps mesh data CPU-readable after upload (lets us inspect post-load) | Diagnostic only |
| `ImportSettings.GenerateMipMaps = true` | C# call site | Generates mipmaps from PNG/JPEG textures embedded in GLB | **Yes — addresses texture shimmer specifically** |
| `ImportSettings.AnisotropicFilterLevel = 4` | Same | Anisotropic filtering | Yes |
| `InstantiationSettings.SkinUpdateWhenOffscreen = true` | Same | Disables culling-by-bounds for skinned meshes (default in glTFast — already on) | Already on per docs |
| Quality Settings > Skin Weights = "Four Bones" | Project Settings | Override Meta's "2 bones" guidance to verify the dropped-influence theory | Diagnostic — if cleaning up at 4 bones, root cause confirmed |
| Player Settings > GPU Skinning = `GPU` (not `GPU (Batched)`) | Project Settings | Workaround for the documented Unity 6 Android skinning corruption | **Yes — high priority.** |

### C.3 PBR Shader Graph variants and skinned variant handling

Per glTFast docs ([Project Setup](https://github.com/atteneder/glTFast/blob/main/Documentation~/ProjectSetup.md)): the shader auto-selects per render pipeline. For URP 12+ it uses `Shader Graphs/glTF-pbrMetallicRoughness`. There is **no separate "skinned" variant** of the URP shader graph in glTFast — Unity's Shader Graph compiles a single program that handles both static and skinned input via the SkinnedMeshRenderer pipeline.

The relevant gotcha: shader stripping. Unity strips Shader Graph keyword variants aggressively for builds. The user's `Resources/` folder placeholder Material trick (already in place) defeats stripping for the runtime-bound case but doesn't guarantee that *every* keyword combination Meshy's GLB needs (e.g., normal map present, occlusion present, double-sided present) is preserved. If a needed variant gets stripped, URP silently falls back and the missing keyword is what produces the artifact.

Verification: open Build > Analyze > Shader Variants to dump compiled variants. If `glTFast_NORMAL_MAP_ON` (or whatever the actual keyword is named) isn't in the list, that's the strip we need to defeat.

---

## D. Topology optimization workflow

### D.1 Tool comparison (skinned-aware)

| Tool | Skinned-aware? | Output | Cost | Verdict for HoloBorn |
|---|---|---|---|---|
| **Meshy Remesh API** ([docs.meshy.ai/en/api/remesh](https://docs.meshy.ai/en/api/remesh)) | Unknown — docs don't say. Their UI demos were all on un-rigged static meshes. | Quad or triangle topology, configurable target polycount 1k-300k | 5 credits per task | Risky — likely strips rig. Don't use post-rig. |
| **gltf-transform `simplify`** ([gltf-transform.dev](https://gltf-transform.dev/modules/functions/functions/simplify)) | Wraps meshoptimizer. Preserves attribute discontinuities by default; vertex_lock for protected verts. Bone weights & joints are vertex attributes — should pass through. **Not explicitly tested for skinned.** | Triangle, target ratio | Free, npm | **Best ship-fix.** Run `weld + simplify --ratio 0.15` on the 193k Meshy GLB -> ~30k. |
| **Blender Decimate Modifier** | Yes — when applied to a mesh with Armature parent, weights get redistributed to remaining verts. *But*: decimate is known to "destroy topology" for character meshes (polycount.com forum). Better than nothing. | Triangle (Collapse) or planar | Free | OK fallback. Manual step. |
| **InstantMeshes** | No — generates new topology, breaks rig binding. Re-rigging needed. | Quad | Free | Don't use post-rig. |
| **gltfpack** ([meshoptimizer.org/gltf](https://meshoptimizer.org/gltf/)) | Same backend as gltf-transform simplify, plus mesh compression. Can hit issue #282 (scrambled normals on Android). | meshopt-compressed | Free | Use for compression *after* simplify, not for simplify itself, and skip if Quest renders wrong. |
| **SimplyGon Cloud** | Yes, professional pipeline. | Tri/quad, LOD chain | Paid | Overkill for EOW. |
| **Meshy in-app polycount slider** ([blog](https://www.meshy.ai/blog/optimize-3d-models-for-better-quality)) | Applies *before* the rig step in Meshy's pipeline | Configurable | Included | **Best clean fix:** set the polycount slider to 0.15 ratio in Meshy *before* running auto-rig, so the rig binds against a 30k-tri mesh from the start. |

### D.2 Recommended target polycount

For HoloBorn (Quest 3, single character, ~2m viewing distance, MR avatar where the user inspects the hologram up close):

- **Floor: 15,000 tris** (matches Wolf3D / RPM full-body)
- **Ceiling: 30,000 tris** (matches Meta first-party avatars; gives margin for facial detail)
- **Stretch: 50,000 tris** if we want extra fidelity post-demo, but only after verifying tangent/skinning is clean at 15-30k

### D.3 Skinned-mesh decimation specifics

The thing that breaks naive decimation on skinned meshes: bone weight smoothing across the collapsed edge. If the decimator merges a vert weighted to bone A with a vert weighted to bone B and their weights get re-averaged uniformly, the resulting deformation is wrong (visible tearing).

Tools that handle it correctly:
- **Blender Decimate** with armature applied: redistributes weights to remaining verts via the armature's vertex group. Tested for Sansar / VRChat workflows ([Sansar guide](https://help.sansar.com/hc/en-us/articles/360029762011-Blender-Using-the-Decimate-Geometry-tool-to-reduce-triangle-count-on-a-skinned-mesh)).
- **meshoptimizer** with `meshopt_simplifyWithAttributes` and `attribute_weights` tuned for joints/weights. gltf-transform's wrapper exposes this implicitly via "preserves attribute discontinuities by default."
- **meshoptimizer's `meshopt_SimplifyRegularize` flag**: docs say *"produces more regular triangle sizes and shapes during simplification, which can improve geometric quality under deformation such as skinning."* Worth trying.

The pragmatic recipe:

```bash
npm i -g @gltf-transform/cli
gltf-transform inspect input.glb              # confirms current state
gltf-transform weld input.glb welded.glb      # required for simplify
gltf-transform simplify welded.glb out.glb --ratio 0.15 --error 0.001
gltf-transform inspect out.glb                # verify joints/weights survived
```

---

## E. Static-vs-animated differential diagnosis

### E.1 Mechanisms by which adding animation tracks changes per-frame rendering

There are exactly three:

1. **Skinning math.** SkinnedMeshRenderer recomputes per-frame vertex positions, normals, and tangents via linear blend skinning. The mesh data is the same; the *output* of LBS is different per frame. If stored tangents are non-MikkTSpace-canonical, the LBS-deformed tangents won't match the normal map's expected basis, and lighting drifts per frame (= shimmer/sheen).

2. **Bounds.** Animated SkinnedMeshRenderers use the mesh's stored bounds (or `localBounds`) by default; if Meshy's bounds are wrong, parts of the mesh may be culled per-frame. glTFast issue #301 documents this exact bug, and the workaround is `Update When Offscreen = true` (which glTFast sets by default per the latest changelog). Won't cause sheen, will cause disappearing parts. **Doesn't match our symptom — skip.**

3. **Shader keyword variants.** Adding an Animator can flip the SkinnedMeshRenderer code path in URP, which can compile a different Shader Graph variant. Possible but unlikely with `Shader Graphs/glTF-pbrMetallicRoughness` — the shader is variant-stripped at build time, not at runtime mode-switch.

**Conclusion:** the artifact is mechanism 1 — skinning-induced tangent drift on top of bad stored tangents.

### E.2 SkinnedMeshRenderer vs MeshRenderer rendering paths

Same shader, *but* SkinnedMeshRenderer:
- Disables some SRP Batcher fast paths (skinned meshes don't batch). Already known.
- Runs CPU or GPU skinning before rasterization (see B.2).
- Loses per-frame tangent re-orthonormalization unless the shader does it explicitly.
- Updates bounds per-frame if Update When Offscreen is on.

The shader graph variant *is* the same. The mesh data path is what differs.

### E.3 Did Meshy's auto-rig modify the mesh?

Almost certainly yes — at minimum the rig step rewelds vertices for skin weight assignment. Meshy's docs don't promise to preserve vertex order, normal smoothing groups, or UV islands. Plausible mutations during rig:
- Re-weld near skin seams (changes index buffer)
- Re-normalize per-vertex normals along seams to share between welded verts
- Drop the input TANGENT attribute and regenerate (or skip regeneration, leaving runtime to compute)
- Add JOINTS_0 / WEIGHTS_0 with potentially non-normalized weights

Any of these can break what was a clean static mesh.

### E.4 Definitive isolation test

You said you have `character_output.glb` (rigged-but-no-animation, 36 MB) sitting around.

**Test:** load `character_output.glb` on Quest with the same code path. Do not call `RecalculateTangents` or `RecalculateNormals` post-spawn (turn that off for this test).

**Outcomes:**

- **A — Static rigged renders clean, animated rigged shows artifacts.** -> the issue is *skinning math + bad tangents*. Animation playback drives bone rotations, which drives LBS, which drifts tangents. Fix: either fix tangents at the source (re-export from Meshy with MikkTSpace, or re-bake tangents in Blender) or compensate at the shader (re-orthonormalize in the vertex stage of a custom shader graph variant).

- **B — Static rigged ALSO shows artifacts.** -> the rig step itself broke the mesh data. The animation is incidental. Fix: skip Meshy's auto-rig, use Mixamo or a Blender-based rig, OR run `gltf-transform optimize` over the rigged GLB to renormalize attributes.

- **C — Static rigged shows different artifacts (e.g., normal seams, different distribution).** -> mixed: rig damaged the mesh AND skinning further amplifies the damage on the animated version. Likely the real answer.

**This test is the single highest-information-density action.** Run it before any further fixes.

---

## F. Recommended next-step ordering (high-confidence -> low)

### F.1 Run the isolation test (E.4) first — 15 minutes
Load `character_output.glb` on Quest. No `RecalculateTangents`. Note artifacts.

### F.2 Decimate to 30k via gltf-transform — 30 minutes
```bash
gltf-transform weld meshy_output.glb welded.glb
gltf-transform simplify welded.glb decimated.glb --ratio 0.15 --error 0.001
gltf-transform inspect decimated.glb  # verify joints/weights
```
Test on Quest. This addresses the perf-budget overrun and may incidentally fix tangent drift if the decimator regenerates tangents.

### F.3 Add `GLTFAST_SAFE` scripting define + GenerateMipMaps — 5 minutes
Project Settings > Player > Scripting Define Symbols: add `GLTFAST_SAFE`. In your `LoadGltfBinary` call site, set `ImportSettings.GenerateMipMaps = true` and `AnisotropicFilterLevel = 4`. Rebuild, test.

### F.4 Stop calling `Mesh.RecalculateTangents` / `RecalculateNormals` post-spawn — 5 minutes
The Unity forum thread "[RecalculateTangents breaks existing normal map](https://forum.unity.com/threads/recalculatetangents-breaks-existing-normal-map.1049003/)" says this directly: *"If you have a tangent space normal map using tangents that no longer exist on the mesh and don't match those Unity generates ... then you're fudged."* If Meshy's exported tangents are correct (or even half-correct), our recompute is making it *worse*. Keep `RecalculateBounds` only.

### F.5 Set GPU Skinning to `GPU` (not `GPU (Batched)`) — 2 minutes
Player Settings. Defends against the documented Unity 6 Android batched-skinning corruption.

### F.6 Set Quality Settings > Skin Weights = `Two Bones` — 2 minutes
Per Meta's official guidance. Test for visible deformation seams. If acceptable, ship. If not, raise to Four Bones and accept the perf cost (one character at 30k can afford it).

### F.7 Re-rig in Blender as a fallback — 1-2 hours
If F.1-F.6 don't resolve it: open the static TRELLIS GLB in Blender, run *File > Import > glTF 2.0* (this triggers a MikkTSpace tangent recompute on import per Blender's importer), apply Blender's Rigify or AccuRIG, bake the animations in Blender, export with *File > Export > glTF 2.0* with "Tangents" checkbox enabled. Test on Quest. This eliminates Meshy's exporter as a variable.

### F.8 Pre-decimate inside Meshy before auto-rigging — manual UI step
Open the static TRELLIS GLB in Meshy, set the polycount slider to 0.15 (or directly to 30000), regenerate, *then* auto-rig. This is the cleanest path for ongoing pipeline use because Meshy's rig step then operates on a smaller mesh from the start.

### F.9 Geometric Specular AA in shader (only if F.1-F.8 don't fully resolve)
URP doesn't expose this in the stock Lit shader graph; HDRP does. Workaround in URP: drop a `GeometricSpecularAA` Custom Function node in a forked Shader Graph. Meaningful for high-density meshes; less so once we're at 30k tris.

### F.10 Drop URP's `precision mediump` -> `highp` (only if we still see shimmer)
Per the [Three.js Quest 3 forum thread](https://discourse.threejs.org/t/texture-artifacts-only-in-meta-quest-3-browser/88506). Requires custom shader graph fork — significant effort. Last resort.

---

## Sources cited

### Primary (most actionable)
- [glTFast issue #437 — Import setting to enforce normals/tangents](https://github.com/atteneder/glTFast/issues/437)
- [glTFast issue #340 — Missing normal must be calculated as flat normals](https://github.com/atteneder/glTFast/issues/340)
- [glTFast issue #301 — Animated SkinnedMeshRenderer bounds stay static](https://github.com/atteneder/glTFast/issues/301)
- [glTFast issue #282 — Scrambled Normal Maps after meshopt compression](https://github.com/atteneder/glTFast/issues/282)
- [glTFast 6.18 changelog](https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.18/changelog/CHANGELOG.html)
- [glTFast Project Setup — GLTFAST_SAFE scripting define](https://github.com/atteneder/glTFast/blob/main/Documentation~/ProjectSetup.md)
- [Unity Discussions — RecalculateTangents breaks existing normal map](https://forum.unity.com/threads/recalculatetangents-breaks-existing-normal-map.1049003/)
- [Unity Discussions — Skinned Meshes With GPU (Batched) Breaks on Android](https://discussions.unity.com/t/skinned-meshes-with-gpu-batched-skinning-breaks-on-android-build/1693083)
- [Khronos glTF issue #2056 — Remaining issues with the tangent space](https://github.com/KhronosGroup/glTF/issues/2056)
- [Khronos glTF issue #1252 — Tangent-basis workflow for correct normal-mapping](https://github.com/KhronosGroup/glTF/issues/1252)
- [Khronos glTF issue #1213 — Are skin weights normalized?](https://github.com/KhronosGroup/glTF/issues/1213)
- [Three.js forum — Texture Artifacts ONLY in Meta Quest 3 Browser](https://discourse.threejs.org/t/texture-artifacts-only-in-meta-quest-3-browser/88506)

### Meta / Quest official
- [Meta — Common Rendering Mistakes blog](https://developers.meta.com/horizon/blog/common-rendering-mistakes-how-to-find-them-and-how-to-fix-them/)
- [Meta — Tech Note: Unity Settings for Mobile VR](https://developers.meta.com/horizon/blog/tech-note-unity-settings-for-mobile-vr/)
- [Meta — Unity Performance Analysis docs](https://developers.meta.com/horizon/documentation/unity/unity-perf/)

### Meshy
- [Meshy — Auto-Rigging & Animation API docs](https://docs.meshy.ai/en/api/rigging-and-animation)
- [Meshy — Remesh API docs](https://docs.meshy.ai/en/api/remesh)
- [Meshy — Optimize 3D Models for Better Quality blog](https://www.meshy.ai/blog/optimize-3d-models-for-better-quality)
- [Meshy — Mesh Topology Guide](https://www.meshy.ai/blog/mesh-topology)
- [Meshy — Integrating Assets into Unity / Unreal](https://help.meshy.ai/en/articles/11973241-integrating-meshy-assets-into-unity-unreal-engine)
- [Meshy — GLB Online Viewer](https://www.meshy.ai/3d-tools/online-viewer/glb)

### Babylon.js
- [Babylon forum — Normals reversed imported glTF](https://forum.babylonjs.com/t/normals-reversed-imported-gltf/5941)
- [Babylon Medium — A Mysterious Case of Skinned Mesh Disappearances](https://babylonjs.medium.com/a-mysterious-case-of-skinned-mesh-disappearances-5fee23dd9cd6)
- [Babylon forum — How to fix backface culling when importing GLB](https://forum.babylonjs.com/t/how-to-fix-backface-culling-when-importing-glb/48426)
- [Babylon Sandbox](https://sandbox.babylonjs.com/)

### Topology / decimation
- [gltf-transform — simplify function](https://gltf-transform.dev/modules/functions/functions/simplify)
- [gltf-transform — CLI](https://gltf-transform.dev/cli)
- [meshoptimizer](https://meshoptimizer.org/) and [GitHub](https://github.com/zeux/meshoptimizer)
- [gltfpack](https://meshoptimizer.org/gltf/)
- [Sansar — Decimate skinned mesh in Blender guide](https://help.sansar.com/hc/en-us/articles/360029762011-Blender-Using-the-Decimate-Geometry-tool-to-reduce-triangle-count-on-a-skinned-mesh)

### Avatar pipelines for reference targets
- [Ready Player Me — Modeling Guidelines](https://docs.readyplayer.me/ready-player-me/customizing-guides/create-custom-assets/modeling-guidelines)
- [Ready Player Me — Avatar Performance API options](https://readyplayer.me/blog/improving-avatar-performance-with-new-avatar-api-options)
- [Ready Player Me example avatar on Sketchfab](https://sketchfab.com/3d-models/ready-player-me-female-avatar-vrchatgame-4b58e590e9fc422dbbf176c1848dc898)

### Tangent / MikkTSpace
- [pixel.engineer — glTF in Unity optimization: Avoid Tangents and Normals Calculation](https://pixel.engineer/posts/gltfast-no-tangents/)
- [Unity scripting API — Mesh.RecalculateTangents](https://docs.unity3d.com/ScriptReference/Mesh.RecalculateTangents.html)
- [Unity scripting API — QualitySettings.skinWeights](https://docs.unity3d.com/ScriptReference/QualitySettings-skinWeights.html)
- [glTF 2.0 spec](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html)
- [MikkTSpace reference](https://github.com/mmikk/MikkTSpace)
- [Marmoset — Tangent & Handedness](https://docs.marmoset.co/docs/tangent-handedness/)
