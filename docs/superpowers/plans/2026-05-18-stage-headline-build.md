# Stage Headline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan in the current session. Steps use checkbox (`- [ ]`) syntax for tracking. **Subagent-driven mode is NOT recommended** — Unity tests can't run from CLI without batch mode setup, and the final Inspector wiring + APK build is a tomorrow-morning step on Parthiv's Mac with Quest in hand.

**Goal:** Add a billboarded stage-headline above the avatar (big readable word + small evolving mandala glyph) that announces the active backend pipeline stage during the ~3-5 min processing wait, readable from 5m in MR. The existing Diagnostic Crescent is unchanged.

**Architecture:** Two new MonoBehaviours, both fully procedural (no prefab assets, no PNGs, no custom shaders — same pattern as the existing `PipelineProgressController`). `EvolvingMandalaController` spawns concentric `LineRenderer` rings on demand, one new ring per stage advance, with fade-in animation and slow Y-rotation. `StageHeadlineController` lives on the SpawnRitual root GameObject, subscribes to the same status events the crescent uses, spawns the headline root with a world-space `TextMeshPro` word + the mandala child + `FaceCameraYawBillboard`, drives stage transitions via fade in/out coroutines.

**Tech Stack:** Unity 6.4.5f1 + Meta XR + URP. C# with coroutines. TextMeshPro 3D world-space. LineRenderer for procedural mandala rings. NUnit EditMode tests for pure-logic mapping + ring spawn logic. Visual validation tomorrow on Quest.

**Brick decomposition:** 7 tasks, ~3-4 hours total focused. Each task = one self-contained brick. Commit after each (stage with `git add`, ask Parthiv before `git commit` — per [feedback_commit_cadence](file:///Users/digispoc06/.claude/projects/-Users-digispoc06-Documents-holoborn-server/memory/feedback_commit_cadence.md)).

**Test execution note:** Unity NUnit tests are authored today as compile-clean `.cs` files. They are RUN tomorrow morning in Unity Editor's Test Runner window (EditMode tab → Run All) before APK build. This plan's "verify test fails / passes" steps are documented but executed tomorrow in the Editor, not from CLI today.

**File location convention:**
- Plan/spec docs live in this repo (`holoborn-server`)
- All implementation files live in the Unity repo at `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/`

---

## Task 1: `EvolvingMandalaController` — state + ring spawn

**Files:**
- Create: `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scripts/SpawnRitual/EvolvingMandalaController.cs`
- Test: `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Tests/EditMode/EvolvingMandalaControllerTests.cs`

This controller manages the mandala glyph above the headline word. Each stage advance (1 → 4) spawns one additional concentric `LineRenderer` ring. Rings persist; they only grow in count. Ring radii and spoke patterns are parameterized per-stage so each ring reads distinctly.

- [ ] **Step 1: Write the failing EditMode test**

Create the test file with this exact content:

```csharp
using NUnit.Framework;
using UnityEngine;
using HoloBorn.SpawnRitual;

namespace HoloBorn.SpawnRitual.Tests
{
    public class EvolvingMandalaControllerTests
    {
        private GameObject _go;
        private EvolvingMandalaController _ctrl;

        [SetUp]
        public void SetUp()
        {
            _go = new GameObject("MandalaTest");
            _ctrl = _go.AddComponent<EvolvingMandalaController>();
            _ctrl.fadeDuration = 0f; // instant for tests
        }

        [TearDown]
        public void TearDown() { Object.DestroyImmediate(_go); }

        [Test]
        public void AdvanceToStage_One_SpawnsExactlyOneRing()
        {
            _ctrl.AdvanceToStage(1);
            Assert.AreEqual(1, _ctrl.RingCount);
        }

        [Test]
        public void AdvanceToStage_TwoThenThree_SpawnsThreeRings()
        {
            _ctrl.AdvanceToStage(2);
            _ctrl.AdvanceToStage(3);
            Assert.AreEqual(3, _ctrl.RingCount);
        }

        [Test]
        public void AdvanceToStage_Backwards_DoesNotRemoveRings()
        {
            _ctrl.AdvanceToStage(3);
            _ctrl.AdvanceToStage(1);
            Assert.AreEqual(3, _ctrl.RingCount);
        }

        [Test]
        public void AdvanceToStage_SameStageTwice_DoesNotDuplicate()
        {
            _ctrl.AdvanceToStage(2);
            _ctrl.AdvanceToStage(2);
            Assert.AreEqual(2, _ctrl.RingCount);
        }

        [Test]
        public void AdvanceToStage_Zero_DoesNothing()
        {
            _ctrl.AdvanceToStage(0);
            Assert.AreEqual(0, _ctrl.RingCount);
        }

        [Test]
        public void AdvanceToStage_FivePlus_ClampsToFour()
        {
            _ctrl.AdvanceToStage(99);
            Assert.AreEqual(4, _ctrl.RingCount);
        }
    }
}
```

- [ ] **Step 2: Verify test fails (TOMORROW in Unity Test Runner)**

Open Unity → Window → General → Test Runner → EditMode tab → expand `HoloBorn.SpawnRitual.Tests` → run `EvolvingMandalaControllerTests`.
Expected today: tests fail to compile (`EvolvingMandalaController` doesn't exist).
Expected after Step 3: tests pass.

- [ ] **Step 3: Implement the controller**

Create `EvolvingMandalaController.cs` with this exact content:

```csharp
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace HoloBorn.SpawnRitual
{
    /// Procedural evolving mandala glyph for the stage headline. Each call to
    /// AdvanceToStage(N) spawns the Nth ring (if not already present), giving
    /// the glyph "grows-as-progress" semantics. Rings persist for the lifetime
    /// of the headline — they never retract.
    ///
    /// Each ring is a single LineRenderer circle at a fixed radius. Ring 4
    /// (outermost) also includes 4 cardinal spokes for visual richness.
    /// All rings share the same emissive cyan color; the controller's parent
    /// transform rotates them as a unit.
    public class EvolvingMandalaController : MonoBehaviour
    {
        [Header("Ring geometry (meters)")]
        [Tooltip("Radii of rings 1..4. Index 0 is ring 1 (innermost).")]
        public float[] ringRadii = new float[] { 0.04f, 0.08f, 0.12f, 0.15f };
        [Tooltip("Number of vertices per ring — higher = smoother circle.")]
        public int ringVertexCount = 64;
        [Tooltip("LineRenderer width in meters.")]
        public float lineWidth = 0.004f;
        [Tooltip("Whether the outermost ring (ring 4) draws 4 cardinal spokes inside.")]
        public bool outermostRingHasSpokes = true;
        [Tooltip("Spoke length in meters (inner endpoint distance from center).")]
        public float spokeInnerRadius = 0.02f;

        [Header("Appearance")]
        [Tooltip("Emissive cyan for rings.")]
        public Color ringColor = new Color(0f, 0.88f, 1f, 1f);
        [Tooltip("Emissive intensity multiplier (> 1 triggers URP bloom).")]
        public float ringEmissiveIntensity = 3.5f;

        [Header("Animation")]
        [Tooltip("Seconds for a newly spawned ring to fade from alpha 0 to full.")]
        public float fadeDuration = 0.6f;
        [Tooltip("Seconds for one full Y-axis rotation of the mandala. 0 = no rotation.")]
        public float secondsPerRotation = 60f;

        private readonly List<GameObject> _rings = new List<GameObject>();
        private int _currentStage = 0;

        public int RingCount => _rings.Count;
        public int CurrentStage => _currentStage;

        /// Advances the mandala to the given stage (1..4). Spawns one ring per
        /// step from current to target. Going backwards or to 0 is a no-op.
        /// Stages > 4 clamp to 4.
        public void AdvanceToStage(int targetStage)
        {
            int clamped = Mathf.Clamp(targetStage, 0, 4);
            while (_currentStage < clamped)
            {
                int nextRingIdx = _currentStage; // 0-based ring index = current stage before increment
                SpawnRing(nextRingIdx);
                _currentStage++;
            }
        }

        private void Update()
        {
            if (secondsPerRotation > 0.001f)
            {
                float degPerSec = 360f / secondsPerRotation;
                transform.Rotate(0f, degPerSec * Time.deltaTime, 0f, Space.Self);
            }
        }

        private void SpawnRing(int ringIdx)
        {
            if (ringIdx < 0 || ringIdx >= ringRadii.Length) return;

            var ringGo = new GameObject($"MandalaRing_{ringIdx + 1}");
            ringGo.transform.SetParent(this.transform, worldPositionStays: false);
            ringGo.transform.localPosition = Vector3.zero;
            ringGo.transform.localRotation = Quaternion.identity;

            var line = ringGo.AddComponent<LineRenderer>();
            line.useWorldSpace = false;
            line.loop = true;
            line.startWidth = lineWidth;
            line.endWidth = lineWidth;
            line.positionCount = ringVertexCount;
            line.material = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
            Color startCol = ringColor * ringEmissiveIntensity;
            startCol.a = 0f;
            line.material.SetColor("_BaseColor", startCol);

            float radius = ringRadii[ringIdx];
            for (int i = 0; i < ringVertexCount; i++)
            {
                float a = (i / (float)ringVertexCount) * 2f * Mathf.PI;
                line.SetPosition(i, new Vector3(Mathf.Cos(a) * radius, 0f, Mathf.Sin(a) * radius));
            }

            _rings.Add(ringGo);

            // Outermost ring (ring 4 = idx 3) also gets 4 spokes
            if (outermostRingHasSpokes && ringIdx == 3)
                SpawnSpokes(ringGo, radius);

            if (fadeDuration > 0.001f && Application.isPlaying)
                StartCoroutine(FadeIn(line.material));
            else
            {
                Color final = ringColor * ringEmissiveIntensity;
                final.a = 1f;
                line.material.SetColor("_BaseColor", final);
            }
        }

        private void SpawnSpokes(GameObject parent, float outerRadius)
        {
            for (int s = 0; s < 4; s++)
            {
                var spokeGo = new GameObject($"MandalaSpoke_{s}");
                spokeGo.transform.SetParent(parent.transform, false);
                var sl = spokeGo.AddComponent<LineRenderer>();
                sl.useWorldSpace = false;
                sl.startWidth = lineWidth;
                sl.endWidth = lineWidth;
                sl.positionCount = 2;
                sl.material = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
                Color c = ringColor * ringEmissiveIntensity;
                c.a = 0f;
                sl.material.SetColor("_BaseColor", c);
                float a = s * (Mathf.PI / 2f);
                Vector3 inner = new Vector3(Mathf.Cos(a) * spokeInnerRadius, 0f, Mathf.Sin(a) * spokeInnerRadius);
                Vector3 outer = new Vector3(Mathf.Cos(a) * outerRadius,       0f, Mathf.Sin(a) * outerRadius);
                sl.SetPosition(0, inner);
                sl.SetPosition(1, outer);
                if (fadeDuration > 0.001f && Application.isPlaying)
                    StartCoroutine(FadeIn(sl.material));
                else
                {
                    Color final = ringColor * ringEmissiveIntensity;
                    final.a = 1f;
                    sl.material.SetColor("_BaseColor", final);
                }
            }
        }

        private IEnumerator FadeIn(Material mat)
        {
            Color baseCol = ringColor * ringEmissiveIntensity;
            float t = 0f;
            while (t < fadeDuration)
            {
                t += Time.deltaTime;
                float u = Mathf.Clamp01(t / fadeDuration);
                Color c = baseCol;
                c.a = u;
                mat.SetColor("_BaseColor", c);
                yield return null;
            }
            Color final = baseCol;
            final.a = 1f;
            mat.SetColor("_BaseColor", final);
        }
    }
}
```

- [ ] **Step 4: Stage for commit (do not commit — wait for Parthiv's go)**

```bash
cd /Users/digispoc06/Documents/UnityProjects/HoloBornUnity
git add Assets/HoloBorn/Scripts/SpawnRitual/EvolvingMandalaController.cs
git add Assets/HoloBorn/Tests/EditMode/EvolvingMandalaControllerTests.cs
git status
```

Expected output: 2 new files staged in `Assets/HoloBorn/`.

---

## Task 2: `EvolvingMandalaController` — `.meta` files

**Files:**
- Create: `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scripts/SpawnRitual/EvolvingMandalaController.cs.meta`
- Create: `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Tests/EditMode/EvolvingMandalaControllerTests.cs.meta`

Unity auto-generates `.meta` files when it next imports the asset folder. We pre-create stable `.meta` files so the GUIDs are deterministic across machines and so the new files don't break the asmdef linkage (if Unity generates GUIDs lazily).

- [ ] **Step 1: Create the controller `.meta` file**

Write exactly:

```yaml
fileFormatVersion: 2
guid: c8a1f4e7b2d04e44a8b3c1d9f3e5a712
MonoImporter:
  externalObjects: {}
  serializedVersion: 2
  defaultReferences: []
  executionOrder: 0
  icon: {instanceID: 0}
  userData:
  assetBundleName:
  assetBundleVariant:
```

- [ ] **Step 2: Create the test `.meta` file**

Write exactly:

```yaml
fileFormatVersion: 2
guid: d9b2e5f8c3a14f55b9c4d2e0f4f6b823
MonoImporter:
  externalObjects: {}
  serializedVersion: 2
  defaultReferences: []
  executionOrder: 0
  icon: {instanceID: 0}
  userData:
  assetBundleName:
  assetBundleVariant:
```

- [ ] **Step 3: Stage**

```bash
cd /Users/digispoc06/Documents/UnityProjects/HoloBornUnity
git add Assets/HoloBorn/Scripts/SpawnRitual/EvolvingMandalaController.cs.meta
git add Assets/HoloBorn/Tests/EditMode/EvolvingMandalaControllerTests.cs.meta
git status
```

Expected: 4 total files staged (controller + test + 2 metas).

---

## Task 3: `StageHeadlineController` — state mapping + stage advance logic

**Files:**
- Create: `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scripts/SpawnRitual/StageHeadlineController.cs`
- Test: `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Tests/EditMode/StageHeadlineMappingTests.cs`

The orchestrator. Subscribes to `SpawnRitualController` status events. Holds the current stage index, advances on new status, ignores backwards/duplicate, queues if anchor not ready.

- [ ] **Step 1: Write the failing EditMode test**

Create the test file with this exact content:

```csharp
using NUnit.Framework;
using UnityEngine;
using HoloBorn.SpawnRitual;

namespace HoloBorn.SpawnRitual.Tests
{
    public class StageHeadlineMappingTests
    {
        [Test]
        public void MapStatusToHeadlineIndex_PortraitizingIsOne()
        {
            Assert.AreEqual(1, StageHeadlineController.MapStatusToHeadlineIndex("portraitizing"));
        }

        [Test]
        public void MapStatusToHeadlineIndex_GeneratingIsTwo()
        {
            Assert.AreEqual(2, StageHeadlineController.MapStatusToHeadlineIndex("generating"));
        }

        [Test]
        public void MapStatusToHeadlineIndex_RetexturingIsThree()
        {
            Assert.AreEqual(3, StageHeadlineController.MapStatusToHeadlineIndex("retexturing"));
        }

        [Test]
        public void MapStatusToHeadlineIndex_RiggingIsFour()
        {
            Assert.AreEqual(4, StageHeadlineController.MapStatusToHeadlineIndex("rigging"));
        }

        [Test]
        public void MapStatusToHeadlineIndex_CapturedIsNegativeOne()
        {
            // capture is not a headline stage — instant moment, no wait
            Assert.AreEqual(-1, StageHeadlineController.MapStatusToHeadlineIndex("captured"));
        }

        [Test]
        public void MapStatusToHeadlineIndex_CompleteIsNegativeOne()
        {
            // complete fades the headline out via OnAwakenedEnter, not a stage value
            Assert.AreEqual(-1, StageHeadlineController.MapStatusToHeadlineIndex("complete"));
        }

        [Test]
        public void MapStatusToHeadlineIndex_UnknownIsNegativeOne()
        {
            Assert.AreEqual(-1, StageHeadlineController.MapStatusToHeadlineIndex("garbage"));
            Assert.AreEqual(-1, StageHeadlineController.MapStatusToHeadlineIndex(""));
        }

        [Test]
        public void HeadlineLabels_HasFourEntries_MatchingCrescent()
        {
            // Labels mirror PipelineProgressController.StageLabels[1..4]
            Assert.AreEqual(4, StageHeadlineController.HeadlineLabels.Length);
            Assert.AreEqual("Refining Portrait", StageHeadlineController.HeadlineLabels[0]);
            Assert.AreEqual("Sculpting Body",    StageHeadlineController.HeadlineLabels[1]);
            Assert.AreEqual("Painting Skin",     StageHeadlineController.HeadlineLabels[2]);
            Assert.AreEqual("Adding Bones",      StageHeadlineController.HeadlineLabels[3]);
        }
    }
}
```

- [ ] **Step 2: Implement `StageHeadlineController` skeleton (mapping only — runtime spawning in Task 5)**

Create `StageHeadlineController.cs` with this exact content (full implementation; later tasks fill in the runtime spawn body):

```csharp
using System.Collections;
using System.Collections.Generic;
using TMPro;
using UnityEngine;

namespace HoloBorn.SpawnRitual
{
    /// Stage Headline — billboarded big-text + evolving-mandala announcer that
    /// sits above the avatar's head during the backend processing wait,
    /// readable from 5m. Reuses the same SpawnRitualController event chain as
    /// the existing Diagnostic Crescent (PipelineProgressController). The two
    /// indicators coexist and stay in sync without coupling.
    ///
    /// Stages announced (indices 1..4 only — capture and awakening don't get
    /// headlines because they're instant moments, not waits):
    ///   1 portraitizing → "Refining Portrait"
    ///   2 generating    → "Sculpting Body"
    ///   3 retexturing   → "Painting Skin"
    ///   4 rigging       → "Adding Bones"
    [RequireComponent(typeof(SpawnRitualController))]
    public class StageHeadlineController : MonoBehaviour
    {
        [Header("Scene refs")]
        [Tooltip("Mannequin controller — provides SpawnedSigil reference for the headline's world anchor.")]
        public AnatomicalMannequinController mannequinController;

        [Header("Placement (sigil-anchored, world-locked)")]
        [Tooltip("Y-height above the sigil center where the BIG WORD baseline sits (meters). 2.0m baseline + ~22cm characters → headline top ~2.2m.")]
        public float headlineHeight = 2.0f;
        [Tooltip("Additional Y-gap from word top to mandala glyph baseline (meters).")]
        public float glyphGap = 0.08f;

        [Header("Word appearance")]
        [Tooltip("TextMeshPro fontSize in world-space meters. 0.22 ≈ 22cm character height — readable at 5m.")]
        public float wordFontSize = 0.22f;
        [Tooltip("Warm-white word fill color.")]
        public Color wordColor = new Color(0.902f, 0.957f, 0.961f, 1f);
        [Tooltip("Cyan glow color (TMP outline + dilate).")]
        public Color wordGlowColor = new Color(0.5f, 0.86f, 0.91f, 1f);
        [Tooltip("TMP outline width (0-1). Higher = thicker glow halo.")]
        [Range(0f, 1f)] public float wordOutlineWidth = 0.2f;
        [Tooltip("Letter spacing (TMP characterSpacing units).")]
        public float wordCharacterSpacing = 0.05f;

        [Header("Transitions")]
        [Tooltip("Seconds for the previous word to fade out before the new one fades in.")]
        public float wordFadeOutDuration = 0.4f;
        [Tooltip("Seconds for a new word to fade in with subtle scale-pop.")]
        public float wordFadeInDuration = 0.5f;
        [Tooltip("Scale multiplier the new word starts at before settling to 1.0.")]
        public float wordScalePopFrom = 1.1f;
        [Tooltip("Seconds for the headline to fade out on OnAwakenedEnter (Stage 3 reveal).")]
        public float awakenFadeOutDuration = 1.0f;
        [Tooltip("Seconds for the headline to fade out on OnFailedEnter.")]
        public float failFadeOutDuration = 0.6f;

        public static readonly string[] HeadlineLabels = new[]
        {
            "Refining Portrait",   // stage 1
            "Sculpting Body",      // stage 2
            "Painting Skin",       // stage 3
            "Adding Bones",        // stage 4
        };

        private SpawnRitualController _controller;
        private int _currentStage = 0;
        private readonly Queue<int> _pendingTargets = new Queue<int>();
        private Coroutine _processCoroutine;
        private GameObject _headlineRoot;
        private TextMeshPro _wordTmp;
        private EvolvingMandalaController _mandala;
        private bool _anchorReady;

        public int CurrentStage => _currentStage;

        public static int MapStatusToHeadlineIndex(string status)
        {
            switch (status)
            {
                case "portraitizing": return 1;
                case "generating":    return 2;
                case "retexturing":   return 3;
                case "rigging":       return 4;
                default:              return -1;
            }
        }

        private void Awake()
        {
            _controller = GetComponent<SpawnRitualController>();
            if (mannequinController == null)
                mannequinController = GetComponent<AnatomicalMannequinController>();
        }

        private void Start()
        {
            _controller.OnRitualBegin += HandleRitualBegin;
            _controller.OnBackendStatusChanged += HandleStatusChanged;
            _controller.OnAwakenedEnter += HandleAwakened;
            _controller.OnFailedEnter += HandleFailed;
        }

        private void OnDestroy()
        {
            if (_controller == null) return;
            _controller.OnRitualBegin -= HandleRitualBegin;
            _controller.OnBackendStatusChanged -= HandleStatusChanged;
            _controller.OnAwakenedEnter -= HandleAwakened;
            _controller.OnFailedEnter -= HandleFailed;
        }

        private void HandleRitualBegin()
        {
            Debug.Log("[StageHeadline] ritual begin — resetting");
            DespawnAll();
            _currentStage = 0;
            _anchorReady = false;
        }

        private void HandleStatusChanged(string status, int progress)
        {
            int target = MapStatusToHeadlineIndex(status);
            Debug.Log($"[StageHeadline] status='{status}' progress={progress}% → headline idx {target}");
            if (target < 0) return;
            AdvanceTo(target);
        }

        private void HandleAwakened()
        {
            Debug.Log("[StageHeadline] awakened — fading out");
            StartCoroutine(FadeOutAndDestroy(awakenFadeOutDuration));
        }

        private void HandleFailed()
        {
            Debug.Log("[StageHeadline] failed — fading out");
            StartCoroutine(FadeOutAndDestroy(failFadeOutDuration));
        }

        private void AdvanceTo(int target)
        {
            if (target <= _currentStage) return;
            _pendingTargets.Enqueue(target);
            if (_processCoroutine == null)
                _processCoroutine = StartCoroutine(ProcessQueue());
        }

        // Filled in Task 5
        private IEnumerator ProcessQueue() { yield break; }

        // Filled in Task 5
        private IEnumerator FadeOutAndDestroy(float duration) { yield break; }

        // Filled in Task 5
        private void DespawnAll() { }
    }
}
```

- [ ] **Step 3: Create `.meta` files**

Create `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scripts/SpawnRitual/StageHeadlineController.cs.meta`:

```yaml
fileFormatVersion: 2
guid: e0c3f6a9b4e21f66cad5e3f1b5f7c934
MonoImporter:
  externalObjects: {}
  serializedVersion: 2
  defaultReferences: []
  executionOrder: 0
  icon: {instanceID: 0}
  userData:
  assetBundleName:
  assetBundleVariant:
```

Create `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Tests/EditMode/StageHeadlineMappingTests.cs.meta`:

```yaml
fileFormatVersion: 2
guid: f1d4e7baa5f32f77dbe6f4a2c6f8da45
MonoImporter:
  externalObjects: {}
  serializedVersion: 2
  defaultReferences: []
  executionOrder: 0
  icon: {instanceID: 0}
  userData:
  assetBundleName:
  assetBundleVariant:
```

- [ ] **Step 4: Stage**

```bash
cd /Users/digispoc06/Documents/UnityProjects/HoloBornUnity
git add Assets/HoloBorn/Scripts/SpawnRitual/StageHeadlineController.cs
git add Assets/HoloBorn/Scripts/SpawnRitual/StageHeadlineController.cs.meta
git add Assets/HoloBorn/Tests/EditMode/StageHeadlineMappingTests.cs
git add Assets/HoloBorn/Tests/EditMode/StageHeadlineMappingTests.cs.meta
git status
```

Expected: 4 new files staged.

---

## Task 4: `StageHeadlineController` — runtime spawn (word + mandala + billboard)

**Files:**
- Modify: `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scripts/SpawnRitual/StageHeadlineController.cs` — fill in `EnsureSpawned`, `ProcessQueue`, helper coroutines

This task adds the runtime spawn logic + the transition coroutines. No new test file — runtime spawning is integration-level (verified in Editor Play mode + Quest tomorrow).

- [ ] **Step 1: Replace the three stub method bodies with real implementations**

Open `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scripts/SpawnRitual/StageHeadlineController.cs` and replace the three stub bodies (`ProcessQueue`, `FadeOutAndDestroy`, `DespawnAll`) with:

```csharp
        private IEnumerator ProcessQueue()
        {
            // Wait for sigil to exist before first spawn (matches crescent pattern).
            while (mannequinController != null && mannequinController.SpawnedSigil == null)
                yield return null;
            EnsureSpawned();

            while (_pendingTargets.Count > 0)
            {
                int target = _pendingTargets.Dequeue();
                while (_currentStage < target)
                {
                    int next = _currentStage + 1;
                    Debug.Log($"[StageHeadline] AdvanceTo: stage {next} ('{HeadlineLabels[next - 1]}')");
                    yield return SwapWord(next);
                    _mandala?.AdvanceToStage(next);
                    _currentStage = next;
                }
            }
            _processCoroutine = null;
        }

        private IEnumerator SwapWord(int newStage)
        {
            // Fade out previous word + scale-down slightly (only if a word exists already)
            if (_wordTmp != null && _currentStage > 0)
            {
                float t = 0f;
                Color start = _wordTmp.color;
                Color end = start; end.a = 0f;
                while (t < wordFadeOutDuration)
                {
                    t += Time.deltaTime;
                    float u = Mathf.Clamp01(t / wordFadeOutDuration);
                    _wordTmp.color = Color.Lerp(start, end, u);
                    yield return null;
                }
                _wordTmp.color = end;
            }

            // Update text + fade in with scale-pop
            if (_wordTmp != null)
            {
                _wordTmp.text = HeadlineLabels[newStage - 1].ToUpper();
                _wordTmp.transform.localScale = Vector3.one * wordScalePopFrom;
                Color from = wordColor; from.a = 0f;
                Color to = wordColor;
                float t = 0f;
                while (t < wordFadeInDuration)
                {
                    t += Time.deltaTime;
                    float u = Mathf.Clamp01(t / wordFadeInDuration);
                    float scale = Mathf.Lerp(wordScalePopFrom, 1.0f, u);
                    _wordTmp.transform.localScale = Vector3.one * scale;
                    _wordTmp.color = Color.Lerp(from, to, u);
                    yield return null;
                }
                _wordTmp.color = to;
                _wordTmp.transform.localScale = Vector3.one;
            }
        }

        private IEnumerator FadeOutAndDestroy(float duration)
        {
            if (_headlineRoot == null) yield break;
            float t = 0f;
            Color wordStart = _wordTmp != null ? _wordTmp.color : Color.clear;
            while (t < duration)
            {
                t += Time.deltaTime;
                float u = Mathf.Clamp01(t / duration);
                if (_wordTmp != null)
                {
                    Color c = wordStart;
                    c.a = Mathf.Lerp(wordStart.a, 0f, u);
                    _wordTmp.color = c;
                }
                // mandala fade out: scale uniformly to 0
                if (_mandala != null)
                    _mandala.transform.localScale = Vector3.one * Mathf.Lerp(1f, 0f, u);
                yield return null;
            }
            DespawnAll();
        }

        private void DespawnAll()
        {
            if (_headlineRoot != null)
            {
                Destroy(_headlineRoot);
                _headlineRoot = null;
                _wordTmp = null;
                _mandala = null;
            }
            _pendingTargets.Clear();
            if (_processCoroutine != null)
            {
                StopCoroutine(_processCoroutine);
                _processCoroutine = null;
            }
            _anchorReady = false;
        }

        private void EnsureSpawned()
        {
            if (_anchorReady && _headlineRoot != null) return;

            Vector3 sigilCenter = mannequinController != null && mannequinController.SpawnedSigil != null
                ? mannequinController.SpawnedSigil.transform.position
                : transform.position;

            _headlineRoot = new GameObject("StageHeadline");
            _headlineRoot.transform.SetParent(this.transform, worldPositionStays: true);
            _headlineRoot.transform.position = sigilCenter + Vector3.up * headlineHeight;
            _headlineRoot.AddComponent<FaceCameraYawBillboard>();

            // Word
            var wordGo = new GameObject("StageHeadlineWord");
            wordGo.transform.SetParent(_headlineRoot.transform, worldPositionStays: false);
            wordGo.transform.localPosition = Vector3.zero;
            _wordTmp = wordGo.AddComponent<TextMeshPro>();
            _wordTmp.text = "";
            _wordTmp.fontSize = wordFontSize;
            _wordTmp.alignment = TextAlignmentOptions.Center;
            _wordTmp.color = new Color(wordColor.r, wordColor.g, wordColor.b, 0f);
            _wordTmp.characterSpacing = wordCharacterSpacing * 100f; // TMP characterSpacing is in font-size-percent units
            _wordTmp.fontStyle = FontStyles.Bold;
            _wordTmp.outlineWidth = wordOutlineWidth;
            _wordTmp.outlineColor = wordGlowColor;
            _wordTmp.rectTransform.sizeDelta = new Vector2(2.0f, 0.5f);

            // Mandala child — sits above the word
            var mandalaGo = new GameObject("StageHeadlineMandala");
            mandalaGo.transform.SetParent(_headlineRoot.transform, worldPositionStays: false);
            mandalaGo.transform.localPosition = new Vector3(0f, wordFontSize + glyphGap, 0f);
            // Mandala draws in XZ plane by default — rotate so it faces the camera (XY plane)
            mandalaGo.transform.localRotation = Quaternion.Euler(90f, 0f, 0f);
            _mandala = mandalaGo.AddComponent<EvolvingMandalaController>();

            _anchorReady = true;
            Debug.Log($"[StageHeadline] spawned at {_headlineRoot.transform.position:F3}");
        }
    }
}
```

⚠ **Important:** the closing `}` at the end here is for the class. Make sure when you replace the three stub methods, the existing `}` closing the class and namespace remain — DO NOT delete and re-add them. Place the new code in-line where the stubs are.

- [ ] **Step 2: Stage**

```bash
cd /Users/digispoc06/Documents/UnityProjects/HoloBornUnity
git add Assets/HoloBorn/Scripts/SpawnRitual/StageHeadlineController.cs
git status
```

Expected: `StageHeadlineController.cs` shows as modified, staged.

---

## Task 5: Wire into demo scene

**Files:**
- Modify: `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scenes/` — the demo scene where `SpawnRitualController` is hosted (likely `HoloBornDemo.unity` or similar — verify with `find` step below)

The new `StageHeadlineController` has `[RequireComponent(typeof(SpawnRitualController))]`, so dropping it on the existing SpawnRitual GameObject in the demo scene attaches automatically. The `mannequinController` reference auto-wires from the same GameObject if blank (see `Awake`).

This step has TWO paths — pick one based on Parthiv's preference tomorrow morning:

**Path A: Unity Editor Inspector (recommended for tomorrow morning).** Open Unity → demo scene → SpawnRitualController GameObject → Add Component → `StageHeadlineController`. Done. Inspector auto-wires `mannequinController`.

**Path B: Edit the `.unity` YAML directly today (if you want a clean state for tomorrow).** More fragile because Unity GUID linkage; only do this if you're comfortable with Unity scene YAML.

- [ ] **Step 1: Locate the demo scene file**

```bash
find /Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets -name "*.unity" -type f
```

Expected: 1-3 scene files. The one containing SpawnRitualController is the target.

- [ ] **Step 2: Verify SpawnRitualController is in the scene**

```bash
grep -l "SpawnRitualController" /Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scenes/*.unity 2>/dev/null
```

Expected: the demo scene path is printed.

- [ ] **Step 3: Decision point — Path A or Path B?**

Pause here, ask Parthiv. **Path A is the default** (defer wire to tomorrow's Inspector pass). If Path A: skip to Task 6. If Path B: see "Optional Scene YAML Patch" appendix below — it's risky and not in the critical path.

---

## Task 6: Verify compile-clean (sanity check today)

The Unity Editor isn't open today (WFH, no Quest), but we can still grep for obvious issues.

- [ ] **Step 1: Confirm all new files exist**

```bash
ls -la /Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scripts/SpawnRitual/EvolvingMandalaController.cs \
       /Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scripts/SpawnRitual/StageHeadlineController.cs \
       /Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Tests/EditMode/EvolvingMandalaControllerTests.cs \
       /Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Tests/EditMode/StageHeadlineMappingTests.cs
```

Expected: all 4 files exist.

- [ ] **Step 2: Eyeball compile-cleanliness**

Read each `.cs` file once end-to-end. Check:
- All braces balanced
- All `using` directives present (`UnityEngine`, `TMPro`, `System.Collections`, `System.Collections.Generic`, `NUnit.Framework` where appropriate)
- Method signatures match what tests call
- No stray `// TODO` markers in implementation paths

- [ ] **Step 3: Cross-reference with `PipelineProgressController` for asmdef visibility**

```bash
grep -n "namespace HoloBorn.SpawnRitual" /Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scripts/SpawnRitual/*.cs
```

Expected: every script file in that directory shows the same namespace. New files should match.

```bash
grep -n "namespace HoloBorn.SpawnRitual.Tests" /Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Tests/EditMode/*.cs
```

Expected: test files match the test namespace.

---

## Task 7: Tomorrow morning's Quest validation checklist (documentation only)

This is a checklist for Parthiv to run **tomorrow morning** when Quest is in hand. Not a code task. Save here so it travels with the plan.

- [ ] Open `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/` in Unity.
- [ ] Open Window → General → Test Runner → EditMode tab.
- [ ] Click "Run All". Expected: all green including the 13 new tests (6 mandala + 7 headline).
- [ ] If any red: read the assertion failure, identify the brick that broke, fix in-place. Iterate.
- [ ] Open the demo scene. Select the SpawnRitualController GameObject.
- [ ] Add Component → `StageHeadlineController`. Verify Inspector shows all the tuning fields.
- [ ] Press Play in the Editor. Manually simulate the pipeline via the test panel (or trigger a real backend run). Verify:
  - Headline spawns above the avatar's head when the first status arrives
  - Word transitions smoothly between "REFINING PORTRAIT" → "SCULPTING BODY" → "PAINTING SKIN" → "ADDING BONES"
  - Mandala adds a new ring per stage
  - Stage 3 reveal: headline fades out cleanly before sigil-rise
- [ ] **Tune Inspector values by eye:**
  - `headlineHeight` — does it sit above the avatar head with breathing room? (Default 2.0m; raise if too close)
  - `wordFontSize` — readable at 5m? Bump to 0.28 or 0.32 if too small
  - `wordOutlineWidth` — enough halo to read against the dim room background?
  - `wordCharacterSpacing` — letters too crowded or too spread?
- [ ] Build APK → sideload to Quest.
- [ ] First headset look: stand 5m from sigil during a real backend run. Confirm readability. If not readable, bump font size or outline.
- [ ] Once it lands, capture MP4.

---

## Optional Appendix: Scene YAML Patch (Path B, do NOT execute unless explicitly chosen)

If Path B is chosen in Task 5, append this block to the GameObject that hosts SpawnRitualController. The component fileID must be unique; choose one that doesn't collide.

```yaml
--- !u!114 &<unique-component-fileID>
MonoBehaviour:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  m_GameObject: {fileID: <existing-spawn-ritual-gameobject-fileID>}
  m_Enabled: 1
  m_EditorHideFlags: 0
  m_Script: {fileID: 11500000, guid: e0c3f6a9b4e21f66cad5e3f1b5f7c934, type: 3}
  m_Name: 
  m_EditorClassIdentifier: HoloBorn.SpawnRitual::HoloBorn.SpawnRitual.StageHeadlineController
  mannequinController: {fileID: 0}
  headlineHeight: 2.0
  glyphGap: 0.08
  wordFontSize: 0.22
  wordColor: {r: 0.902, g: 0.957, b: 0.961, a: 1}
  wordGlowColor: {r: 0.5, g: 0.86, b: 0.91, a: 1}
  wordOutlineWidth: 0.2
  wordCharacterSpacing: 0.05
  wordFadeOutDuration: 0.4
  wordFadeInDuration: 0.5
  wordScalePopFrom: 1.1
  awakenFadeOutDuration: 1.0
  failFadeOutDuration: 0.6
```

Also add a corresponding component reference under the GameObject's `m_Component` list. Verify with diff before staging.

---

## Self-Review Notes

- **Spec coverage:** every section of `2026-05-18-stage-headline-design.md` maps to a task. Architecture → Tasks 1, 3, 4. Components → Tasks 1, 3, 4. Placement → Task 4 EnsureSpawned. Sizing → Task 3 Inspector fields. Transitions → Task 4 SwapWord + FadeOutAndDestroy. Stage event mapping → Task 3 MapStatusToHeadlineIndex. Side crescent (unchanged) → no task, intentional. Failure modes → Task 4 (queue + null guards). Testing → Tasks 1, 3 plus Task 7 manual checklist.
- **No placeholders in critical paths.** Inspector tuning ranges in Task 7 are intentional — they're tomorrow's headset-pass values.
- **Type consistency:** `EvolvingMandalaController.AdvanceToStage(int)` returns `void`, accessed via `_mandala?.AdvanceToStage(next)` in Task 4. `MapStatusToHeadlineIndex` static, signature matches `MapStatusToStageIndex` from existing code. `HeadlineLabels[newStage - 1]` consistent across Task 3 + Task 4.
- **TDD discipline preserved despite delayed test execution.** Tests authored before implementation, expected outcomes documented, batch-run tomorrow in Editor.
- **Commit discipline:** all tasks end with "Stage" (`git add`) not "Commit." Per Parthiv's memory rule, `git commit` waits for his explicit go.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-18-stage-headline-build.md`.

Two execution options:

1. **Subagent-Driven** (NOT recommended for this plan) — Unity tests can't run from CLI without batch-mode setup, and a fresh subagent can't open Unity Editor. Skip.

2. **Inline Execution (recommended)** — I execute Tasks 1-6 in this session using `superpowers:executing-plans`, with checkpoints between each task for your review. Task 7 is your tomorrow-morning checklist on Quest, not part of today's execution.

Which approach?
