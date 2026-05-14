# Stage 1 Premium Build — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a fully premium Stage 1 of the HoloBorn summoning ritual — cyan sacred-geometry sigil disc + floating anatomical mannequin with layered arrival (audio → anchor → pre-cast light → dissolve) — verified on Quest device.

**Architecture:** Unity 6.4 URP. Spawn ritual state machine already refactored to 5-state model (Phase A complete). Stage 1 adds: sigil disc prefab + mannequin material (rim+dissolve Shader Graph) + pre-cast Point Light + layered arrival coroutine + 2 audio stems. No VFX Graph, no particle math. All assets pre-generated in `drafts/`.

**Tech Stack:** Unity 6.4, Universal Render Pipeline, Shader Graph (Unlit target), C# coroutines, Mixamo Y-Bot rig, AudioSource spatialized playback. Asset generation via Python (already complete).

**Spec:** `docs/superpowers/specs/2026-05-11-stage-1-premium-design.md`

---

## Pre-flight — already complete (do not redo)

- ✅ `drafts/summoning_sigil.png` — 1024×1024 cyan sacred-geometry texture
- ✅ `drafts/audio/summoning_drone.wav` — 8s seamless loopable low drone
- ✅ `drafts/audio/summoning_chime.wav` — 1.5s magical chime
- ✅ `tools/gen_summoning_sigil.py` — regen sigil with tweakable constants
- ✅ `tools/gen_summoning_audio.py` — regen audio with tweakable parameters
- ✅ Phase A: SpawnRitualStateMachine refactored to 5-state enum, 12 EditMode tests green, cube cloud .cs + prefabs deleted
- ✅ `SpawnRitualController.cs` has events: OnShellManifestEnter, OnRevealedEnter, OnAwakenedEnter, OnFailedEnter
- ✅ `AnatomicalMannequinController.cs` file exists (will be refactored in Task 8)

---

## Execution notes

- **Hybrid handoff:** Claude writes/generates code + assets, user executes Unity Editor steps (drag-drop, Shader Graph node assembly, prefab creation, scene wiring). Claude cannot click in Unity Editor.
- **Commit cadence:** stage changes after each task but DO NOT commit without explicit user approval (per user's commit cadence rule).
- **TDD:** unit tests added for pure logic (rotation math, state subscriptions). Visual/material/animation tasks verified by Editor playmode + Quest device. Acceptance criteria from spec serve as final tests.
- **Path conventions:** all paths absolute from project root. Unity asset paths are relative to `Assets/`. Quest project lives at `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/`.

---

### Task 1: Import sigil + audio assets into Unity

**Files:**
- Copy: `drafts/summoning_sigil.png` → `Assets/HoloBorn/Textures/summoning_sigil.png`
- Copy: `drafts/audio/summoning_drone.wav` → `Assets/HoloBorn/Audio/summoning_drone.wav`
- Copy: `drafts/audio/summoning_chime.wav` → `Assets/HoloBorn/Audio/summoning_chime.wav`

- [ ] **Step 1.1:** User drags `summoning_sigil.png` from Finder into Unity's Project window at `Assets/HoloBorn/Textures/` (create folder if missing).
- [ ] **Step 1.2:** Select the imported texture in Project window. In Inspector: `Alpha Source = Input Texture Alpha`, `Alpha Is Transparency = true`. Click Apply.
- [ ] **Step 1.3:** User drags both `.wav` files into `Assets/HoloBorn/Audio/` (create folder if missing).
- [ ] **Step 1.4:** Select `summoning_drone.wav` in Project. In Inspector: `Load Type = Decompress on Load`, `Compression Format = Vorbis` (or PCM if size tolerable). Click Apply.
- [ ] **Step 1.5:** Select `summoning_chime.wav` in Project. In Inspector: `Load Type = Decompress on Load`, `Compression Format = PCM`. Click Apply.
- [ ] **Step 1.6:** Verify: all 3 assets visible in Project; audio clips play in Inspector preview; sigil shows transparent background with cyan pattern.

**Acceptance:** assets imported, alpha + audio settings correct.

---

### Task 2: Write SummoningSigilController.cs

**Files:**
- Create: `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scripts/SpawnRitual/SummoningSigilController.cs`
- Create: `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Tests/EditMode/SummoningSigilControllerTests.cs`

- [ ] **Step 2.1: Write the test first**

```csharp
using NUnit.Framework;
using UnityEngine;
using HoloBorn.SpawnRitual;

namespace HoloBorn.Tests
{
    public class SummoningSigilControllerTests
    {
        [Test]
        public void Rotation_OneSecondAt30SecRotation_Adds12Degrees()
        {
            var go = new GameObject("SigilTest");
            var ctrl = go.AddComponent<SummoningSigilController>();
            ctrl.secondsPerRotation = 30f;

            float initialY = go.transform.eulerAngles.y;
            ctrl.RotateBy(1.0f); // 1s of advance via test hook
            float finalY = go.transform.eulerAngles.y;

            Assert.AreEqual(12f, Mathf.DeltaAngle(initialY, finalY), 0.01f);
            Object.DestroyImmediate(go);
        }

        [Test]
        public void Rotation_HalfSecondAt30SecRotation_Adds6Degrees()
        {
            var go = new GameObject("SigilTest2");
            var ctrl = go.AddComponent<SummoningSigilController>();
            ctrl.secondsPerRotation = 30f;

            float initialY = go.transform.eulerAngles.y;
            ctrl.RotateBy(0.5f);
            float finalY = go.transform.eulerAngles.y;

            Assert.AreEqual(6f, Mathf.DeltaAngle(initialY, finalY), 0.01f);
            Object.DestroyImmediate(go);
        }
    }
}
```

- [ ] **Step 2.2: Run the test in Unity Test Runner — expect FAIL (class not defined)**

Open `Window → General → Test Runner → EditMode tab`. Run `SummoningSigilControllerTests`. Expected: both tests fail (compilation error: `SummoningSigilController` not found).

- [ ] **Step 2.3: Write the implementation**

```csharp
using UnityEngine;

namespace HoloBorn.SpawnRitual
{
    /// Rotates the summoning sigil slowly on its Y axis during Stage 1 hold.
    /// One revolution per `secondsPerRotation` (default 30s).
    public class SummoningSigilController : MonoBehaviour
    {
        [Tooltip("Seconds for one full Y-axis rotation. 30s = subtle ritual rotation.")]
        public float secondsPerRotation = 30f;

        private void Update()
        {
            RotateBy(Time.deltaTime);
        }

        /// Test-friendly rotation hook. Called from Update() at runtime,
        /// directly from EditMode tests with deterministic dt.
        public void RotateBy(float deltaTime)
        {
            float degreesPerSecond = 360f / secondsPerRotation;
            transform.Rotate(0f, degreesPerSecond * deltaTime, 0f, Space.Self);
        }
    }
}
```

- [ ] **Step 2.4: Run tests — expect PASS**

Re-run `SummoningSigilControllerTests` in Test Runner. Expected: 2/2 green.

- [ ] **Step 2.5: Stage (do not commit yet)**

```bash
cd /Users/digispoc06/Documents/UnityProjects/HoloBornUnity && git add Assets/HoloBorn/Scripts/SpawnRitual/SummoningSigilController.cs Assets/HoloBorn/Scripts/SpawnRitual/SummoningSigilController.cs.meta Assets/HoloBorn/Tests/EditMode/SummoningSigilControllerTests.cs Assets/HoloBorn/Tests/EditMode/SummoningSigilControllerTests.cs.meta
```

---

### Task 3: Build SummoningSigil_Prefab

**Files:**
- Create: `Assets/HoloBorn/Materials/SummoningSigil_Mat.mat`
- Create: `Assets/HoloBorn/Prefabs/SummoningSigil_Prefab.prefab`

User actions in Unity Editor:

- [ ] **Step 3.1:** Right-click `Assets/HoloBorn/Materials/` → Create → Material. Name it `SummoningSigil_Mat`.
- [ ] **Step 3.2:** Select `SummoningSigil_Mat`. In Inspector, set shader to `Universal Render Pipeline/Unlit`. Surface Options: `Surface Type = Transparent`, `Blending Mode = Alpha`. Drag `summoning_sigil.png` into the Base Map slot. Set Base Map color tint to white (#FFFFFF) with alpha 255. Enable `Emission` toggle, set Emission color to cyan #00E0FF with HDR intensity ~1.5.
- [ ] **Step 3.3:** In Hierarchy, right-click → 3D Object → Quad. Rename to `SummoningSigil`. Set Transform: position (0, 0, 0), rotation (90, 0, 0) (so it lays flat on XZ plane), scale (1.2, 1.2, 1.2).
- [ ] **Step 3.4:** Apply `SummoningSigil_Mat` to the Quad's MeshRenderer.
- [ ] **Step 3.5:** Add Component → `SummoningSigilController`. Confirm `secondsPerRotation = 30`.
- [ ] **Step 3.6:** Add Component → AudioSource. Set `AudioClip = summoning_drone`, `Loop = true`, `Play On Awake = false`, `Spatial Blend = 1.0` (full 3D), `Volume = 0.6`, `Min Distance = 0.5`, `Max Distance = 5.0`.
- [ ] **Step 3.7:** Drag the `SummoningSigil` GameObject from Hierarchy into `Assets/HoloBorn/Prefabs/` to create `SummoningSigil_Prefab.prefab`. Delete the Hierarchy instance.
- [ ] **Step 3.8:** Verify: drag prefab back into scene at origin temporarily; press Play; sigil rotates slowly on Y axis, no audio (Play On Awake is off). Delete the temporary instance.

**Acceptance:** prefab exists, applies texture+material, rotates on play, AudioSource configured but quiet.

---

### Task 4: Build MannequinRimDissolve Shader Graph

**Files:**
- Create: `Assets/HoloBorn/Shaders/MannequinRimDissolve.shadergraph`

User actions in Unity Shader Graph editor:

- [ ] **Step 4.1:** Right-click `Assets/HoloBorn/Shaders/` → Create → Shader Graph → URP → Unlit Shader Graph. Name it `MannequinRimDissolve`. Open it (double-click).

- [ ] **Step 4.2:** In Graph Settings (gear icon, top right): Surface = `Transparent`, Blend = `Alpha`, Allow Material Override = `true`.

- [ ] **Step 4.3:** Add Blackboard properties (click "+" on Blackboard panel):
  - `BaseColor` — Color (HDR off), default #E8E8EAFF
  - `BaseAlpha` — Float, mode = Slider, min 0, max 1, default 0.4
  - `RimColor` — Color (HDR on), default #00E0FFFF, intensity 1.0
  - `RimIntensity` — Float, mode = Default, default 1.2
  - `RimPower` — Float, mode = Slider, min 0.5, max 8, default 2.0
  - `DissolveThreshold` — Float, mode = Default, default 0.0 (will be animated 2.0 → 0.0 at runtime)
  - `DissolveEdgeWidth` — Float, mode = Slider, min 0.01, max 0.3, default 0.06
  - `DissolveEdgeIntensity` — Float, mode = Default, default 3.0

- [ ] **Step 4.4:** Build the dissolve mask branch (these are visible-mask + edge-mask):
  - Add node: `Position` (Mode: Object) → drag from output to `Split` node
  - From `Split.Y` → connect to first input of `Step` node
  - `DissolveThreshold` property → drag onto graph → connect to second input of `Step` (Step expects Edge, In — Edge=threshold, In=Y. Output is `1 if Y >= threshold, 0 if Y < threshold`)
  - Call this output `visible_mask` (you can label nodes via right-click → "Convert to subgraph" for clarity, but optional)
  - For edge band: `Subtract` node, A = Split.Y, B = DissolveThreshold → output is `Y - threshold`
  - `Absolute` node on the subtract result → `|Y - threshold|`
  - `Step` node: Edge = DissolveEdgeWidth, In = absolute result → returns `1 if |diff| >= edgeWidth else 0`
  - `One Minus` node on that Step → inverts to `1 if |diff| < edgeWidth else 0` — this is `near_edge`
  - `Multiply` node: visible_mask * near_edge → `edge_mask` (edge band only on visible side)

- [ ] **Step 4.5:** Build the rim glow branch:
  - Add node: `Fresnel Effect` — set Power input to `RimPower` property
  - `Multiply` node: Fresnel output * RimColor → rim_tinted
  - `Multiply` node: rim_tinted * RimIntensity → rim_emission

- [ ] **Step 4.6:** Build the edge emission:
  - `Multiply` node: edge_mask * RimColor → edge_tinted
  - `Multiply` node: edge_tinted * DissolveEdgeIntensity → edge_emission

- [ ] **Step 4.7:** Combine into Base Color output:
  - `Add` node: BaseColor + rim_emission → mid_color
  - `Add` node: mid_color + edge_emission → final_color
  - Connect final_color → Master Stack `Base Color` input

- [ ] **Step 4.8:** Combine into Alpha output:
  - `Multiply` node: visible_mask * BaseAlpha → base_alpha
  - `One Minus` node on BaseAlpha → `1 - BaseAlpha` → alpha_complement
  - `Multiply` node: edge_mask * alpha_complement → edge_alpha_boost
  - `Add` node: base_alpha + edge_alpha_boost → final_alpha
  - `Saturate` node on final_alpha (clamps to 0-1) → clamped_alpha
  - Connect clamped_alpha → Master Stack `Alpha` input

- [ ] **Step 4.9:** Click "Save Asset" (top left). Verify: no shader compilation errors in Inspector.

**Acceptance:** shader graph asset exists; opens in editor with all properties exposed; saves without errors.

---

### Task 5: Create Mannequin_RimDissolve.mat material

**Files:**
- Create: `Assets/HoloBorn/Materials/Mannequin_RimDissolve.mat`

- [ ] **Step 5.1:** Right-click `Assets/HoloBorn/Materials/` → Create → Material. Name `Mannequin_RimDissolve`.
- [ ] **Step 5.2:** In Inspector, set Shader to `Shader Graphs/MannequinRimDissolve`.
- [ ] **Step 5.3:** Verify exposed properties visible: BaseColor, BaseAlpha, RimColor, RimIntensity, RimPower, DissolveThreshold, DissolveEdgeWidth, DissolveEdgeIntensity.
- [ ] **Step 5.4:** Set defaults: BaseColor=#E8E8EA Alpha 255, BaseAlpha=0.4, RimColor=#00E0FF, RimIntensity=1.2, RimPower=2.0, DissolveThreshold=0.0, DissolveEdgeWidth=0.06, DissolveEdgeIntensity=3.0.
- [ ] **Step 5.5:** Quick visual test: drag a temporary Sphere into the scene, apply this material. Confirm visible with subtle cyan edge rim (not Tron-cyan-body). Drag DissolveThreshold up from 0 to 2 in the material Inspector — sphere should erode away from the bottom up with a cyan emissive edge band traveling up. Reset threshold to 0. Delete the test sphere.

**Acceptance:** material renders with edge rim + working dissolve threshold animation.

---

### Task 6: Build Mannequin_Prefab from Y-Bot mesh + breath Animator

**Files:**
- Existing: `Assets/HoloBorn/Models/silhouette_placeholder.fbx` (Y-Bot, Mixamo-rigged)
- Create: `Assets/HoloBorn/Animations/MannequinBreath.controller`
- Create: `Assets/HoloBorn/Animations/MannequinBreath.anim` (looped 2s clip)
- Create: `Assets/HoloBorn/Prefabs/Mannequin_Prefab.prefab`

- [ ] **Step 6.1:** Drag `silhouette_placeholder.fbx` from Project into Hierarchy at (0, 0, 0). Rename root to `Mannequin`.
- [ ] **Step 6.2:** In Hierarchy, expand the Mannequin root and locate the SkinnedMeshRenderer (typically on a child like `Beta_Surface` or similar). Select all SkinnedMeshRenderers (Ctrl/Cmd + click each).
- [ ] **Step 6.3:** With all SkinnedMeshRenderers selected, drag `Mannequin_RimDissolve.mat` onto them (replaces existing materials). Verify the mannequin now shows translucent off-white with subtle cyan edge rim.
- [ ] **Step 6.4:** Create the breath clip:
  - Right-click `Assets/HoloBorn/Animations/` → Create → Animation. Name `MannequinBreath`.
  - Right-click `Assets/HoloBorn/Animations/` → Create → Animator Controller. Name `MannequinBreath`.
  - Open Animator Controller, drag the `MannequinBreath.anim` into the Animator graph. It auto-creates a state. Set it as default (right-click → Set As Layer Default State).
  - Open the animation clip. With Mannequin selected in Hierarchy, find the spine bone (`mixamorig:Spine` or similar). Record (red circle) → at t=0 set spine localScale = (1, 1, 1) → at t=1 set spine localScale = (1, 1.03, 1) → at t=2 set spine localScale = (1, 1, 1). Stop recording. Set clip to Loop Time = true.
- [ ] **Step 6.5:** Add Animator component to Mannequin root. Set Controller = `MannequinBreath`.
- [ ] **Step 6.6:** Drag `Mannequin` from Hierarchy into `Assets/HoloBorn/Prefabs/` to create `Mannequin_Prefab.prefab`. Delete the Hierarchy instance.
- [ ] **Step 6.7:** Verify: drag prefab into scene temporarily, press Play → mannequin shows translucent + cyan rim, breathes subtly. Delete temp instance.

**Acceptance:** prefab spawns translucent rim-glow mannequin with looping breath.

---

### Task 7: Build PreCastLight_Prefab

**Files:**
- Create: `Assets/HoloBorn/Prefabs/PreCastLight_Prefab.prefab`

- [ ] **Step 7.1:** In Hierarchy, right-click → Light → Point Light. Rename to `PreCastLight`.
- [ ] **Step 7.2:** Configure: Color = cyan #00E0FF, Intensity = 0 (will be animated up at runtime), Range = 2.0, Shadows = No Shadows (perf on Quest), Render Mode = Important, Cull Mask = Everything.
- [ ] **Step 7.3:** Drag `PreCastLight` from Hierarchy into `Assets/HoloBorn/Prefabs/` to create `PreCastLight_Prefab.prefab`. Delete Hierarchy instance.

**Acceptance:** prefab exists with cyan point light, intensity 0, range 2m.

---

### Task 8: Refactor AnatomicalMannequinController.cs for layered arrival

**Files:**
- Modify: `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scripts/SpawnRitual/AnatomicalMannequinController.cs`

This is the central orchestration script. Subscribes to `OnShellManifestEnter`, runs the 4-layered arrival coroutine, holds Stage 1 visuals until next state.

- [ ] **Step 8.1: Replace the entire file contents with:**

```csharp
using System.Collections;
using UnityEngine;

namespace HoloBorn.SpawnRitual
{
    /// Orchestrates Stage 1 of the origin story ritual:
    /// audio drone start → sigil scale+fade → pre-cast light ramp →
    /// mannequin dissolve from sigil plane with cyan edge band → chime at chest height →
    /// hold (breath + slow Y-drift) until next state transition.
    public class AnatomicalMannequinController : MonoBehaviour
    {
        [Header("Prefab references")]
        public GameObject sigilPrefab;
        public GameObject mannequinPrefab;
        public GameObject preCastLightPrefab;

        [Header("Audio clips")]
        public AudioClip chimeClip;

        [Header("Scene refs")]
        public Transform ritualAnchor;        // floor anchor X/Z (typically a child of CenterEyeAnchor or rig)
        public SpawnRitualController spawnController;

        [Header("Arrival timing (seconds)")]
        public float sigilArrivalDuration = 0.6f;
        public float preCastLightStart = 0.4f;
        public float preCastLightRiseDuration = 1.0f;
        public float preCastLightPeakIntensity = 1.5f;
        public float preCastLightHoldIntensity = 0.3f;
        public float mannequinStartTime = 0.6f;
        public float mannequinDissolveStart = 1.0f;
        public float mannequinDissolveDuration = 1.8f;
        public float chimeTime = 1.8f;
        public float lightFadeDuration = 0.4f;

        [Header("Mannequin behavior")]
        public float mannequinFloatOffset = 0.03f;
        public float mannequinRiseAmount = 0.05f;
        public float mannequinYRotationDegPerSec = 1.5f;
        public float dissolveThresholdMax = 2.0f;     // mesh-Y above this is clipped
        public float dissolveThresholdRest = -0.1f;   // fully visible

        // Runtime
        private GameObject _sigilInstance;
        private GameObject _mannequinInstance;
        private GameObject _lightInstance;
        private Light _lightComponent;
        private Material _mannequinMaterial;
        private Coroutine _arrivalRoutine;
        private bool _arrivalComplete;
        private static readonly int DissolveThresholdId = Shader.PropertyToID("_DissolveThreshold");

        private void OnEnable()
        {
            if (spawnController != null)
                spawnController.OnShellManifestEnter += HandleShellManifestEnter;
        }

        private void OnDisable()
        {
            if (spawnController != null)
                spawnController.OnShellManifestEnter -= HandleShellManifestEnter;
        }

        private void HandleShellManifestEnter()
        {
            if (_arrivalRoutine != null) StopCoroutine(_arrivalRoutine);
            _arrivalRoutine = StartCoroutine(RunArrival());
        }

        private IEnumerator RunArrival()
        {
            _arrivalComplete = false;

            // --- Spawn sigil at floor anchor, start audio drone ---
            Vector3 anchorPos = ritualAnchor != null ? ritualAnchor.position : Vector3.zero;
            Vector3 floorPos = new Vector3(anchorPos.x, anchorPos.y - 1.6f, anchorPos.z); // assume anchor is eye-level

            _sigilInstance = Instantiate(sigilPrefab, floorPos, sigilPrefab.transform.rotation);
            _sigilInstance.transform.localScale = sigilPrefab.transform.localScale * 0.8f;
            var sigilSpriteRenderer = _sigilInstance.GetComponent<Renderer>();
            var sigilMat = sigilSpriteRenderer.material;
            SetMaterialAlpha(sigilMat, 0f);

            var sigilAudio = _sigilInstance.GetComponent<AudioSource>();
            if (sigilAudio != null) sigilAudio.Play();

            // --- Coroutines fire in parallel along the timeline ---
            StartCoroutine(SigilArrival(sigilMat));
            StartCoroutine(PreCastLightSequence(floorPos, anchorPos));
            StartCoroutine(MannequinArrival(anchorPos));
            StartCoroutine(ChimeAt(chimeTime, anchorPos));

            // Wait for full arrival window
            float totalArrival = Mathf.Max(mannequinDissolveStart + mannequinDissolveDuration,
                                            preCastLightStart + preCastLightRiseDuration + lightFadeDuration);
            yield return new WaitForSeconds(totalArrival + 0.2f);

            _arrivalComplete = true;
        }

        private IEnumerator SigilArrival(Material sigilMat)
        {
            float t = 0f;
            Vector3 fromScale = _sigilInstance.transform.localScale;
            Vector3 toScale = sigilPrefab.transform.localScale;
            while (t < sigilArrivalDuration)
            {
                t += Time.deltaTime;
                float u = EaseOutCubic(Mathf.Clamp01(t / sigilArrivalDuration));
                _sigilInstance.transform.localScale = Vector3.Lerp(fromScale, toScale, u);
                SetMaterialAlpha(sigilMat, u);
                yield return null;
            }
        }

        private IEnumerator PreCastLightSequence(Vector3 floorPos, Vector3 anchorPos)
        {
            yield return new WaitForSeconds(preCastLightStart);
            _lightInstance = Instantiate(preCastLightPrefab, anchorPos, Quaternion.identity);
            _lightComponent = _lightInstance.GetComponent<Light>();

            float t = 0f;
            while (t < preCastLightRiseDuration)
            {
                t += Time.deltaTime;
                float u = EaseOutCubic(Mathf.Clamp01(t / preCastLightRiseDuration));
                _lightComponent.intensity = Mathf.Lerp(0f, preCastLightPeakIntensity, u);
                yield return null;
            }
            // Hold briefly at peak, then fade to ambient hold level
            yield return new WaitForSeconds(0.2f);
            t = 0f;
            float startInt = _lightComponent.intensity;
            while (t < lightFadeDuration)
            {
                t += Time.deltaTime;
                float u = Mathf.Clamp01(t / lightFadeDuration);
                _lightComponent.intensity = Mathf.Lerp(startInt, preCastLightHoldIntensity, u);
                yield return null;
            }
        }

        private IEnumerator MannequinArrival(Vector3 anchorPos)
        {
            yield return new WaitForSeconds(mannequinStartTime);
            _mannequinInstance = Instantiate(mannequinPrefab,
                anchorPos + Vector3.up * (mannequinFloatOffset - mannequinRiseAmount),
                Quaternion.identity);
            // Cache material instance for dissolve property
            var skinned = _mannequinInstance.GetComponentInChildren<SkinnedMeshRenderer>();
            _mannequinMaterial = skinned != null ? skinned.material : null;
            if (_mannequinMaterial != null)
                _mannequinMaterial.SetFloat(DissolveThresholdId, dissolveThresholdMax);

            // Wait for dissolve start offset (relative to mannequin spawn)
            float dissolveOffset = Mathf.Max(0f, mannequinDissolveStart - mannequinStartTime);
            yield return new WaitForSeconds(dissolveOffset);

            // Animate dissolve threshold from max → rest while rising
            float t = 0f;
            Vector3 fromPos = _mannequinInstance.transform.position;
            Vector3 toPos = anchorPos + Vector3.up * mannequinFloatOffset;
            while (t < mannequinDissolveDuration)
            {
                t += Time.deltaTime;
                float u = EaseOutCubic(Mathf.Clamp01(t / mannequinDissolveDuration));
                if (_mannequinMaterial != null)
                    _mannequinMaterial.SetFloat(DissolveThresholdId,
                        Mathf.Lerp(dissolveThresholdMax, dissolveThresholdRest, u));
                _mannequinInstance.transform.position = Vector3.Lerp(fromPos, toPos, u);
                yield return null;
            }
        }

        private IEnumerator ChimeAt(float time, Vector3 pos)
        {
            yield return new WaitForSeconds(time);
            if (chimeClip != null)
                AudioSource.PlayClipAtPoint(chimeClip, pos, 0.8f);
        }

        private void Update()
        {
            if (_arrivalComplete && _mannequinInstance != null)
                _mannequinInstance.transform.Rotate(0f,
                    mannequinYRotationDegPerSec * Time.deltaTime, 0f, Space.Self);
        }

        private static void SetMaterialAlpha(Material mat, float a)
        {
            if (mat == null) return;
            Color c = mat.color;
            c.a = a;
            mat.color = c;
        }

        private static float EaseOutCubic(float u) => 1f - Mathf.Pow(1f - u, 3f);
    }
}
```

- [ ] **Step 8.2:** Save the file. Unity recompiles. Expect zero errors in Console.

- [ ] **Step 8.3:** Verify: Project shows the file at the right path, no red-text errors in Console.

---

### Task 9: Wire AnatomicalMannequinController in scene + Inspector refs

User actions in the Unity scene (`SampleScene.unity` or whichever main scene):

- [ ] **Step 9.1:** Locate the `SpawnRitualController` GameObject in Hierarchy. Right-click → Create Empty Child. Name it `AnatomicalMannequinController`.
- [ ] **Step 9.2:** Add Component → AnatomicalMannequinController to the new GameObject.
- [ ] **Step 9.3:** In Inspector, fill all references:
  - Sigil Prefab = drag `SummoningSigil_Prefab.prefab` from Project
  - Mannequin Prefab = drag `Mannequin_Prefab.prefab` from Project
  - Pre Cast Light Prefab = drag `PreCastLight_Prefab.prefab` from Project
  - Chime Clip = drag `summoning_chime.wav` from Project
  - Ritual Anchor = drag the anchor Transform (typically the CenterEyeAnchor of OVRCameraRig, or a dedicated child placed 1.5m forward at eye-level)
  - Spawn Controller = drag the parent `SpawnRitualController` component
- [ ] **Step 9.4:** Verify Inspector shows no missing-reference warnings (yellow icons).

**Acceptance:** all Inspector fields filled, no missing-ref warnings.

---

### Task 10: Editor playmode verification via `_DebugStatusSimulator`

- [ ] **Step 10.1:** Press Play in Unity Editor. Wait for scene to initialize.
- [ ] **Step 10.2:** Locate the `_DebugStatusSimulator` GameObject in Hierarchy. In Game view, find its on-screen "ShellManifest" button. Click it.
- [ ] **Step 10.3:** Watch Game view. Expected sequence:
  - t=0.0s: drone audio audible (check speakers/headphones)
  - t=0.0-0.6s: sigil fades + scales in on the floor
  - t=0.4-1.4s: cyan glow appears at anchor position (light is invisible unless on a surface — may not be obvious without floor mesh)
  - t=1.0-2.8s: mannequin materializes bottom-up with cyan edge band traveling up
  - t=1.8s: chime sound plays
  - t=2.8+: mannequin fully visible, subtle edge rim, breathing, slowly rotating
- [ ] **Step 10.4:** If any beat looks wrong, tune values in the AnatomicalMannequinController Inspector (timings, intensities) until the arrival reads clean. Save scene after tuning.

**Acceptance:** all 10 spec acceptance criteria visible in Editor playmode.

---

### Task 11: Quest device build + on-device verification

- [ ] **Step 11.1:** File → Build Settings → ensure `SampleScene` is in Scenes In Build, Platform = Android, target Quest.
- [ ] **Step 11.2:** Connect Quest 3 via USB-C. Verify `adb devices` shows the headset (or check via Unity's device dropdown).
- [ ] **Step 11.3:** Click Build And Run. Wait for build to complete and install on device (~5-10 min for first build).
- [ ] **Step 11.4:** On Quest, navigate to the app. Trigger the simulator's ShellManifest equivalent (likely via a controller button or auto-firing on app load).
- [ ] **Step 11.5:** Verify all 10 spec acceptance criteria on device:
  1. Audio drone audible at t=0
  2. Sigil fades + scales in on real floor over ~0.6s
  3. Pre-cast cyan glow visible at anchor ~0.4s after sigil (may show as subtle floor wash from the Point Light)
  4. Mannequin dissolves bottom-up with cyan edge band ~1.0s
  5. Chime audible at ~1.8s
  6. Mannequin reads as subtle cyan EDGE RIM, not Tron-cyan body
  7. Mannequin breathes
  8. Mannequin slowly rotates
  9. Sigil slowly rotates
  10. State holds for 5+ min without frame drops, no z-fighting, no artifacts
- [ ] **Step 11.6:** If any beat fails on device but worked in Editor: tune values in Inspector, rebuild. Common issues: light too dim through passthrough (boost intensity 1.5→3.0), audio too quiet (boost AudioSource volume), dissolve edge too faint (boost DissolveEdgeIntensity 3→5).

**Acceptance:** all 10 criteria pass on Quest. Stage 1 is shippable.

---

## Self-review (post-write)

**Spec coverage:**
- ✅ Sigil PNG asset + import + Quad/material/rotation script (Tasks 1, 3)
- ✅ Mannequin mesh + rim+dissolve shader graph + material + prefab (Tasks 4, 5, 6)
- ✅ Pre-cast Light prefab (Task 7)
- ✅ Audio drone + chime clips imported (Task 1)
- ✅ Layered arrival sequence with all 4 layers (Task 8)
- ✅ Wiring in scene (Task 9)
- ✅ Acceptance criteria verified (Tasks 10, 11)
- ✅ TDD on the one pure-logic component (SummoningSigilController, Task 2)

**Placeholder scan:**
- No "TBD", "TODO", or "implement later" present.
- Shader Graph build (Task 4) gives concrete node-by-node walkthrough.
- AnatomicalMannequinController body (Task 8) is full implementation, not pseudocode.

**Type consistency:**
- `SummoningSigilController.secondsPerRotation` consistent across Tasks 2, 3.
- `_DissolveThreshold` Shader property name matches between Task 4 (Blackboard creation) and Task 8 (Shader.PropertyToID lookup).
- `OnShellManifestEnter` event matches Phase A's existing controller refactor.

**No gaps identified.**

---

## Risk reminders

- **Stock URP Lit emission trap:** the spec explicitly avoids stock URP Lit (yesterday's Tron-cyan mistake). All materials use either Unlit (sigil) or Shader Graph Unlit (mannequin). Don't substitute.
- **Synth audio reads clinical:** acceptable for ship; swap to freesound CC0 if first device pass feels off.
- **AudioSource.PlayClipAtPoint** spawns a temporary GameObject — fine for one-shot chime but creates garbage. For production polish, swap to a pooled AudioSource.
- **Material instancing:** accessing `.material` on a renderer creates a runtime instance — intentional for dissolve property animation. Don't switch to `.sharedMaterial` (would affect all instances).
