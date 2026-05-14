# Pipeline Progress Indicator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan in the current session. Steps use checkbox (`- [ ]`) syntax for tracking. **Subagent-driven mode is NOT recommended for this plan** — the work is Unity-side scene + script wiring + sideload validation in the operator's Unity Editor, which a fresh subagent cannot do.

**Goal:** Add a holographic neural-network-growth progress indicator that floats to the right of the Stage 1 mannequin during backend processing, surfacing each pipeline stage (Capture → Refining Portrait → Sculpting Body → Painting Skin → Adding Bones → Awakening) so non-technical users always know what the system is doing.

**Architecture:** New `PipelineProgressController` MonoBehaviour subscribes to extended `SpawnRitualController` events (`OnRitualBegin` + `OnBackendStatusChanged(string, int)`). Six nodes are procedurally instantiated one at a time as backend events arrive — each completion grows a cyan emissive `LineRenderer` from the previous node, terminates at the next node's position, fades in the new node (disc mesh + TextMeshPro label). No prefabs — fully procedural so all geometry/material/text lives in one controller file. Mirrors the existing per-component-on-SpawnRitualController pattern (ScanLineTransitionController, Stage3GracefulArrivalController) — drop a MonoBehaviour on the same GameObject, no scene reorganization needed.

**Tech Stack:** Unity 6.4.5f1 + Meta XR + URP. C# with coroutines for growth animation. LineRenderer + procedural Quad + TextMeshPro (world-space). NUnit EditMode tests for pure-logic mapping. Sideload-based validation for spatial/visual behavior.

**Brick decomposition:** 6 tasks, ~3-4 hours total. Each task = one self-contained brick.

---

## Task 1: SpawnRitualController — `OnBackendStatusChanged` + `OnRitualBegin` events

**Files:**
- Modify: `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scripts/SpawnRitual/SpawnRitualController.cs`
- Test: `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Tests/EditMode/SpawnRitualControllerEventsTests.cs`

The state machine already maps "rigging"/"complete" to phase transitions. For the progress indicator we need GRANULAR events that fire on every status string change — "portraitizing", "generating", "retexturing", "rigging" — even when they don't trigger a phase transition. Also need a discrete "ritual just begun" event so the Capture node can seed at t=0.

- [ ] **Step 1: Write failing EditMode test**

Create the test file at `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Tests/EditMode/SpawnRitualControllerEventsTests.cs`:

```csharp
using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;
using HoloBorn.SpawnRitual;

namespace HoloBorn.SpawnRitual.Tests
{
    public class SpawnRitualControllerEventsTests
    {
        private GameObject _go;
        private SpawnRitualController _controller;
        private List<(string status, int progress)> _statusEvents;
        private int _ritualBeginCount;

        [SetUp]
        public void SetUp()
        {
            _go = new GameObject("TestSpawnRitual");
            _controller = _go.AddComponent<SpawnRitualController>();
            _statusEvents = new List<(string, int)>();
            _ritualBeginCount = 0;
            _controller.OnBackendStatusChanged += (s, p) => _statusEvents.Add((s, p));
            _controller.OnRitualBegin += () => _ritualBeginCount++;
        }

        [TearDown]
        public void TearDown() { Object.DestroyImmediate(_go); }

        [Test]
        public void OnRitualBegin_FiresOnce_OnBeginRitualCall()
        {
            _controller.BeginRitual("test-task");
            Assert.AreEqual(1, _ritualBeginCount);
        }

        [Test]
        public void OnRitualBegin_SeedsCapturedStatus()
        {
            _controller.BeginRitual("test-task");
            Assert.AreEqual(1, _statusEvents.Count);
            Assert.AreEqual("captured", _statusEvents[0].status);
            Assert.AreEqual(0, _statusEvents[0].progress);
        }

        [Test]
        public void OnBackendStatusChanged_FiresOnEachUniqueStatus()
        {
            _controller.BeginRitual("test-task");
            _controller.FeedBackendStatus("portraitizing", 10);
            _controller.FeedBackendStatus("generating", 30);
            _controller.FeedBackendStatus("retexturing", 60);
            // captured + 3 changes
            Assert.AreEqual(4, _statusEvents.Count);
            Assert.AreEqual("portraitizing", _statusEvents[1].status);
            Assert.AreEqual("generating", _statusEvents[2].status);
            Assert.AreEqual("retexturing", _statusEvents[3].status);
        }

        [Test]
        public void OnBackendStatusChanged_DoesNotFireOnSameStatusRepeated()
        {
            _controller.BeginRitual("test-task");
            _controller.FeedBackendStatus("portraitizing", 10);
            _controller.FeedBackendStatus("portraitizing", 20);  // same status, different progress
            _controller.FeedBackendStatus("portraitizing", 30);
            // captured + 1 portraitizing (repeated calls suppressed)
            Assert.AreEqual(2, _statusEvents.Count);
        }
    }
}
```

- [ ] **Step 2: Run test, verify it fails**

Run via Unity Test Runner (Window → General → Test Runner → EditMode → Run All) or command-line:
```
"/Applications/Unity/Hub/Editor/6.4.5f1/Unity.app/Contents/MacOS/Unity" -batchmode -projectPath "/Users/digispoc06/Documents/UnityProjects/HoloBornUnity" -runTests -testPlatform EditMode -testResults /tmp/test_results.xml -logFile -
```
Expected: 4 failures with "OnRitualBegin event not found" / "OnBackendStatusChanged event not found".

- [ ] **Step 3: Add events + emit logic to SpawnRitualController**

Edit `SpawnRitualController.cs`:

a) Add new events near the existing event declarations (around line 30-33):
```csharp
public event Action OnRitualBegin;
public event Action<string, int> OnBackendStatusChanged;
```

b) Add private field for last-seen status (near `_latestGlbUrl` field):
```csharp
private string _lastStatus = "";
```

c) Modify `BeginRitual(string taskId)`:
```csharp
public void BeginRitual(string taskId)
{
    _activeTaskId = taskId;
    _latestGlbUrl = null;
    _lastStatus = "";
    _stateMachine.BeginRitual();
    DetectPhaseTransition();

    OnRitualBegin?.Invoke();
    OnBackendStatusChanged?.Invoke("captured", 0);  // seed Capture stage for progress indicator

    if (_pollingCoroutine != null) StopCoroutine(_pollingCoroutine);
    if (!string.IsNullOrEmpty(serverBaseUrl) && !string.IsNullOrEmpty(taskId))
    {
        _pollingCoroutine = StartCoroutine(PollBackendStatus());
    }
    else
    {
        Debug.LogWarning($"[SpawnRitual] BeginRitual skipped polling: serverBaseUrl='{serverBaseUrl}', taskId='{taskId}'. Simulator must drive the state machine.");
    }
}
```

d) Modify `FeedBackendStatus(string status, int progress)`:
```csharp
public void FeedBackendStatus(string status, int progress)
{
    _stateMachine.OnBackendStatus(status, progress);
    if (status != _lastStatus)
    {
        _lastStatus = status;
        OnBackendStatusChanged?.Invoke(status, progress);
    }
    DetectPhaseTransition();
}
```

- [ ] **Step 4: Run test, verify it passes**

Re-run EditMode tests. Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/digispoc06/Documents/UnityProjects/HoloBornUnity
git add Assets/HoloBorn/Scripts/SpawnRitual/SpawnRitualController.cs \
        Assets/HoloBorn/Tests/EditMode/SpawnRitualControllerEventsTests.cs
git commit -m "$(cat <<'EOF'
feat(spawn-ritual): granular OnBackendStatusChanged + OnRitualBegin events

Phase events (ShellManifest/Revealed/Awakened) are too coarse for the
pipeline progress indicator — it needs to know about every backend status
transition, including portraitizing/generating/retexturing/rigging that
all live within the ShellManifest phase.

- OnRitualBegin fires once when BeginRitual() is called
- OnBackendStatusChanged fires every time the status string changes
  (deduped against last-seen, so a slow-polling progress increment on
  the same status doesn't spam subscribers)
- "captured" is seeded as the t=0 status on BeginRitual so the progress
  indicator's first node can light up immediately

EditMode tests cover: ritual-begin fires once, captured seeds, status
changes propagate, same-status repeats are suppressed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Debug simulator — granular pipeline-stage buttons

**Files:**
- Modify: `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scripts/SpawnRitual/_DebugStatusSimulator.cs`

The existing simulator advances through PHASES on each Y press, but we now need to test the granular pipeline progress. Add separate GUI buttons + on-device key bindings (number keys 4-7 in Editor; trigger button + grip cycling on device) to fire individual pipeline status strings without backend connection.

- [ ] **Step 1: Modify `_DebugStatusSimulator.cs` to add per-stage buttons**

Replace the `OnGUI()` method body:

```csharp
private void OnGUI()
{
    GUILayout.BeginArea(new Rect(10, 10, 380, 420), GUI.skin.box);
    GUILayout.Label($"Spawn Ritual — Phase: {_controller.CurrentPhase}");
    GUILayout.Space(6);
    if (GUILayout.Button("1 → BeginRitual  (Idle → ShellManifest)"))
    {
        Debug.Log("[Sim] 1 → BeginRitual");
        _controller.BeginRitual("debug-task-id");
    }
    GUILayout.Space(4);
    GUILayout.Label("--- Granular pipeline stages (ShellManifest only) ---");
    if (GUILayout.Button("4 → 'portraitizing' (Capture → Refining Portrait)"))
    {
        Debug.Log("[Sim] 4 → status='portraitizing'");
        _controller.FeedBackendStatus("portraitizing", 10);
    }
    if (GUILayout.Button("5 → 'generating'    (→ Sculpting Body)"))
    {
        Debug.Log("[Sim] 5 → status='generating'");
        _controller.FeedBackendStatus("generating", 30);
    }
    if (GUILayout.Button("6 → 'retexturing'   (→ Painting Skin)"))
    {
        Debug.Log("[Sim] 6 → status='retexturing'");
        _controller.FeedBackendStatus("retexturing", 60);
    }
    GUILayout.Space(4);
    GUILayout.Label("--- Phase transitions ---");
    if (GUILayout.Button("2 → 'rigging'   (ShellManifest → Revealed)"))
    {
        Debug.Log("[Sim] 2 → status='rigging'");
        _controller.FeedBackendStatus("rigging", 80);
    }
    if (GUILayout.Button("3 → 'complete'  (Revealed → Awakened)"))
    {
        Debug.Log("[Sim] 3 → status='complete'");
        _controller.FeedBackendStatus("complete", 100);
    }
    if (GUILayout.Button("F → 'failed'    (any → Failed)"))
    {
        Debug.Log("[Sim] F → status='failed'");
        _controller.FeedBackendStatus("failed", 0);
    }
    GUILayout.EndArea();
}
```

Note: device Y-button binding stays unchanged (still phase-advance). The granular buttons are Editor-only for now; on-device the Y button still cycles phases, but real backend will drive the granular status transitions automatically.

- [ ] **Step 2: Verify in Unity Editor**

Open Unity Editor, Play scene, click button 1 (BeginRitual), then buttons 4 / 5 / 6 in sequence. Verify Console shows `[Sim] N → status='X'` logs.

- [ ] **Step 3: Commit**

```bash
cd /Users/digispoc06/Documents/UnityProjects/HoloBornUnity
git add Assets/HoloBorn/Scripts/SpawnRitual/_DebugStatusSimulator.cs
git commit -m "$(cat <<'EOF'
feat(debug-sim): granular pipeline-stage GUI buttons for progress indicator dev

Adds Editor-only GUI buttons 4/5/6 for portraitizing/generating/retexturing
so the pipeline progress indicator can be developed + iterated without
running the real backend. Existing buttons 1/2/3/F for phase transitions
preserved. Device Y-button binding unchanged (phase-cycle).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: PipelineProgressController scaffold + stage mapping (EditMode tested)

**Files:**
- Create: `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scripts/SpawnRitual/PipelineProgressController.cs`
- Create: `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scripts/SpawnRitual/PipelineProgressController.cs.meta`
- Test: `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Tests/EditMode/PipelineProgressMappingTests.cs`

Pure-logic scaffold: stage-index mapping + event subscription. No rendering yet (that's Task 4-5). Use logging to verify subscription works on sideload.

- [ ] **Step 1: Write failing EditMode test for stage mapping**

```csharp
using NUnit.Framework;

namespace HoloBorn.SpawnRitual.Tests
{
    public class PipelineProgressMappingTests
    {
        [Test]
        public void MapStatusToStageIndex_CapturedSeed()
        {
            Assert.AreEqual(0, PipelineProgressController.MapStatusToStageIndex("captured"));
        }

        [Test]
        public void MapStatusToStageIndex_PipelineStages()
        {
            Assert.AreEqual(1, PipelineProgressController.MapStatusToStageIndex("portraitizing"));
            Assert.AreEqual(2, PipelineProgressController.MapStatusToStageIndex("generating"));
            Assert.AreEqual(3, PipelineProgressController.MapStatusToStageIndex("retexturing"));
            Assert.AreEqual(4, PipelineProgressController.MapStatusToStageIndex("rigging"));
        }

        [Test]
        public void MapStatusToStageIndex_CompleteIsFinalStage()
        {
            Assert.AreEqual(5, PipelineProgressController.MapStatusToStageIndex("complete"));
        }

        [Test]
        public void MapStatusToStageIndex_UnknownStatusReturnsNegative()
        {
            Assert.AreEqual(-1, PipelineProgressController.MapStatusToStageIndex("garbage"));
            Assert.AreEqual(-1, PipelineProgressController.MapStatusToStageIndex(""));
            Assert.AreEqual(-1, PipelineProgressController.MapStatusToStageIndex("failed"));  // failed handled separately
        }

        [Test]
        public void StageLabels_HasSixEntries()
        {
            Assert.AreEqual(6, PipelineProgressController.StageLabels.Length);
            Assert.AreEqual("Capture", PipelineProgressController.StageLabels[0]);
            Assert.AreEqual("Refining Portrait", PipelineProgressController.StageLabels[1]);
            Assert.AreEqual("Sculpting Body", PipelineProgressController.StageLabels[2]);
            Assert.AreEqual("Painting Skin", PipelineProgressController.StageLabels[3]);
            Assert.AreEqual("Adding Bones", PipelineProgressController.StageLabels[4]);
            Assert.AreEqual("Awakening", PipelineProgressController.StageLabels[5]);
        }
    }
}
```

- [ ] **Step 2: Run test, verify failure**

Run EditMode tests. Expected: 5 failures with "PipelineProgressController not found" / type errors.

- [ ] **Step 3: Create `PipelineProgressController.cs` scaffold**

```csharp
using System.Collections.Generic;
using UnityEngine;

namespace HoloBorn.SpawnRitual
{
    /// Pipeline Progress Indicator — neural-network-growth UI element that
    /// floats to the right of the Stage 1 mannequin and surfaces which backend
    /// pipeline stage is currently active. Six stages from Capture → Awakening,
    /// each one BIRTHED in sequence: a cyan emissive line grows from the
    /// previous node, terminates at the next position, and a new node + label
    /// fades in. Like a neuron extending its axon.
    ///
    /// Scope (Brick T3): scaffold + subscription + stage mapping (pure logic +
    /// logging). Rendering primitives + growth animation in Brick T4-5.
    [RequireComponent(typeof(SpawnRitualController))]
    public class PipelineProgressController : MonoBehaviour
    {
        [Header("Scene refs")]
        [Tooltip("Mannequin controller — used to anchor the progress column relative to the mannequin's world position.")]
        public AnatomicalMannequinController mannequinController;

        public static readonly string[] StageLabels = new[]
        {
            "Capture",
            "Refining Portrait",
            "Sculpting Body",
            "Painting Skin",
            "Adding Bones",
            "Awakening"
        };

        private SpawnRitualController _controller;
        private int _currentStageIndex = -1;

        private void Awake()
        {
            _controller = GetComponent<SpawnRitualController>();
            if (mannequinController == null) mannequinController = GetComponent<AnatomicalMannequinController>();
        }

        private void Start()
        {
            _controller.OnRitualBegin += HandleRitualBegin;
            _controller.OnBackendStatusChanged += HandleStatusChanged;
            _controller.OnAwakenedEnter += HandleAwakened;
        }

        private void HandleRitualBegin()
        {
            Debug.Log("[PipelineProgress] ritual begin — resetting indicator");
            _currentStageIndex = -1;
            // Brick T4-5: DespawnAllNodes() here
        }

        private void HandleStatusChanged(string status, int progress)
        {
            int target = MapStatusToStageIndex(status);
            Debug.Log($"[PipelineProgress] status='{status}' progress={progress}% → stage idx {target}");
            if (target < 0) return;
            AdvanceTo(target);
        }

        private void HandleAwakened()
        {
            Debug.Log("[PipelineProgress] Awakened — advancing to final stage 'Awakening'");
            AdvanceTo(5);
        }

        public static int MapStatusToStageIndex(string status)
        {
            switch (status)
            {
                case "captured":      return 0;
                case "portraitizing": return 1;
                case "generating":    return 2;
                case "retexturing":   return 3;
                case "rigging":       return 4;
                case "complete":      return 5;
                default:              return -1;
            }
        }

        private void AdvanceTo(int target)
        {
            while (_currentStageIndex < target)
            {
                int nextIdx = _currentStageIndex + 1;
                Debug.Log($"[PipelineProgress] AdvanceTo: spawning stage {nextIdx} ('{StageLabels[nextIdx]}')");
                // Brick T4-5: SpawnNode(nextIdx) + GrowLineToNext()
                _currentStageIndex = nextIdx;
            }
        }
    }
}
```

- [ ] **Step 4: Create `.cs.meta` with a fresh GUID**

Run from terminal:
```bash
python3 -c "import uuid; print(uuid.uuid4().hex)"
```
Copy the output as the guid value in the .meta:

```yaml
fileFormatVersion: 2
guid: <PASTE_GENERATED_GUID_HERE>
```

Save to `Assets/HoloBorn/Scripts/SpawnRitual/PipelineProgressController.cs.meta`.

- [ ] **Step 5: Run EditMode tests, verify pass**

Expected: all 5 mapping tests PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/digispoc06/Documents/UnityProjects/HoloBornUnity
git add Assets/HoloBorn/Scripts/SpawnRitual/PipelineProgressController.cs \
        Assets/HoloBorn/Scripts/SpawnRitual/PipelineProgressController.cs.meta \
        Assets/HoloBorn/Tests/EditMode/PipelineProgressMappingTests.cs
git commit -m "$(cat <<'EOF'
feat(progress-indicator): T3 — scaffold + stage mapping + subscription

PipelineProgressController.cs subscribes to SpawnRitualController's new
granular events (OnRitualBegin, OnBackendStatusChanged, OnAwakenedEnter),
maps backend status strings → stage indices (0-5), and logs each stage
advance. No rendering yet — that's Brick T4-T5.

Stage labels locked: Capture / Refining Portrait / Sculpting Body /
Painting Skin / Adding Bones / Awakening — short, verb-based, readable
in MR.

EditMode tests cover the pure mapping logic.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Node spawn primitive (procedural emissive disc + TMP label)

**Files:**
- Modify: `Assets/HoloBorn/Scripts/SpawnRitual/PipelineProgressController.cs`

Procedural creation: no .prefab assets. Each node = a Quad mesh primitive + a cyan-emissive URP/Lit material instance + a child world-space TextMeshPro label. The node mesh is positioned in world-space at a column offset right of the mannequin.

**Why procedural:** keeps all geometry/material/text logic in one source file (single source of truth), no prefab GUID coupling, easier to tune via Inspector serialized fields.

- [ ] **Step 1: Add serialized Inspector fields to PipelineProgressController**

Add inside the class, after the `mannequinController` field:

```csharp
[Header("Column layout")]
[Tooltip("World-space offset from mannequin position to the FIRST (top) node's center. Default = 80cm right, 0.4m above mannequin's hip.")]
public Vector3 columnOffsetFromMannequin = new Vector3(0.8f, 0.4f, 0f);
[Tooltip("Vertical spacing between consecutive nodes (meters). Negative = stack downward.")]
public float nodeVerticalSpacing = -0.20f;

[Header("Node appearance")]
[Tooltip("Disc diameter (meters). Quad rendered with billboarded emissive material.")]
public float nodeDiameterMeters = 0.12f;
[Tooltip("Cyan emissive color for nodes when fully lit.")]
public Color nodeEmissiveColor = new Color(0f, 0.88f, 1f, 1f);  // #00E0FF
[Tooltip("Emissive intensity multiplier for active node (currently pulsing).")]
public float nodeEmissiveIntensity = 2.0f;

[Header("Label appearance")]
[Tooltip("Label TextMeshPro font size in world-space units.")]
public float labelFontSize = 0.06f;
[Tooltip("Label color (cyan emissive).")]
public Color labelColor = new Color(0f, 0.88f, 1f, 1f);
[Tooltip("Vertical offset of label below node center (meters, negative = below).")]
public float labelVerticalOffset = -0.10f;
```

- [ ] **Step 2: Add node-tracking lists**

After `_currentStageIndex` private field:

```csharp
private List<GameObject> _nodes = new List<GameObject>();
private List<TMPro.TextMeshPro> _nodeLabels = new List<TMPro.TextMeshPro>();
```

Add `using TMPro;` at top if not present (note: TMPro is the namespace for TextMesh Pro).

- [ ] **Step 3: Implement `SpawnNode(int idx)` helper**

Add to the class:

```csharp
private GameObject SpawnNode(int idx)
{
    Vector3 worldPos = GetNodeWorldPosition(idx);

    // Quad mesh primitive — built-in Unity primitive
    var node = GameObject.CreatePrimitive(PrimitiveType.Quad);
    node.name = $"PipelineNode_{idx:D2}_{StageLabels[idx].Replace(" ", "")}";
    node.transform.SetParent(this.transform, worldPositionStays: true);
    node.transform.position = worldPos;
    node.transform.localScale = new Vector3(nodeDiameterMeters, nodeDiameterMeters, nodeDiameterMeters);

    // Strip the built-in MeshCollider — UI element, don't want physics
    var col = node.GetComponent<Collider>();
    if (col != null) Destroy(col);

    // URP/Lit material instance with emission enabled
    var rend = node.GetComponent<Renderer>();
    var mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
    mat.SetColor("_BaseColor", nodeEmissiveColor * 0.3f);  // dim base, emission carries it
    mat.EnableKeyword("_EMISSION");
    mat.SetColor("_EmissionColor", nodeEmissiveColor * nodeEmissiveIntensity);
    mat.SetFloat("_Surface", 1f);  // transparent
    mat.renderQueue = 3000;
    rend.material = mat;

    // World-space TextMeshPro label as a child
    var labelGo = new GameObject($"Label_{idx:D2}");
    labelGo.transform.SetParent(node.transform, worldPositionStays: false);
    labelGo.transform.localPosition = new Vector3(0f, labelVerticalOffset / nodeDiameterMeters, 0f);  // scale-compensated
    labelGo.transform.localScale = Vector3.one;  // override parent scale via TMP fontSize
    var tmp = labelGo.AddComponent<TextMeshPro>();
    tmp.text = StageLabels[idx];
    tmp.fontSize = labelFontSize * 100f;  // TMP world-space fontSize is in points*scale
    tmp.color = labelColor;
    tmp.alignment = TextAlignmentOptions.Center;
    // Compensate label for parent scale (parent Quad is scaled to nodeDiameterMeters)
    labelGo.transform.localScale = Vector3.one / nodeDiameterMeters;
    labelGo.transform.localPosition = new Vector3(0f, labelVerticalOffset / nodeDiameterMeters, 0f);

    _nodes.Add(node);
    _nodeLabels.Add(tmp);
    Debug.Log($"[PipelineProgress] spawned node {idx} '{StageLabels[idx]}' at world {worldPos:F3}");
    return node;
}

private Vector3 GetNodeWorldPosition(int idx)
{
    Vector3 mannequinPos = mannequinController != null && mannequinController.SpawnedMannequin != null
        ? mannequinController.SpawnedMannequin.transform.position
        : transform.position;
    return mannequinPos + columnOffsetFromMannequin + Vector3.up * (idx * nodeVerticalSpacing);
}
```

- [ ] **Step 4: Call `SpawnNode` from `AdvanceTo`**

Replace the existing `AdvanceTo` body:

```csharp
private void AdvanceTo(int target)
{
    while (_currentStageIndex < target)
    {
        int nextIdx = _currentStageIndex + 1;
        Debug.Log($"[PipelineProgress] AdvanceTo: spawning stage {nextIdx} ('{StageLabels[nextIdx]}')");
        SpawnNode(nextIdx);
        _currentStageIndex = nextIdx;
    }
}
```

- [ ] **Step 5: Add despawn logic for ritual restart**

In `HandleRitualBegin`:

```csharp
private void HandleRitualBegin()
{
    Debug.Log("[PipelineProgress] ritual begin — resetting indicator");
    DespawnAll();
    _currentStageIndex = -1;
}

private void DespawnAll()
{
    foreach (var n in _nodes)
    {
        if (n != null) Destroy(n);
    }
    _nodes.Clear();
    _nodeLabels.Clear();
}
```

- [ ] **Step 6: Commit (visual test happens in Brick T6 sideload)**

```bash
cd /Users/digispoc06/Documents/UnityProjects/HoloBornUnity
git add Assets/HoloBorn/Scripts/SpawnRitual/PipelineProgressController.cs
git commit -m "$(cat <<'EOF'
feat(progress-indicator): T4 — procedural node spawn (quad + emissive + TMP label)

SpawnNode(idx) procedurally creates a quad mesh, applies URP/Lit material
with cyan emission, and parents a TextMeshPro world-space label below.
No prefab dependency. Column position computed from mannequin's
SpawnedMannequin transform plus columnOffsetFromMannequin Inspector field.

DespawnAll() cleans the column on BeginRitual so re-running the ritual
doesn't accumulate stale nodes.

Visual verification deferred to Brick T6 sideload — Brick T5 (growth
animation) ships first to avoid jarring instant-pop spawns.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Growth animation — LineRenderer grow + node fade-in

**Files:**
- Modify: `Assets/HoloBorn/Scripts/SpawnRitual/PipelineProgressController.cs`

Each non-zero-index node arrives via a growth animation: thin cyan line draws from previous node to next-node's position over `lineGrowDuration` (Smootherstep), then a new node fades in by lerping emission from 0 to full over `nodeFadeInDuration`. Node 0 (Capture) spawns immediately at full emission since there's no previous node to grow from.

- [ ] **Step 1: Add growth-animation Inspector fields**

Inside class, after node-appearance fields:

```csharp
[Header("Growth animation")]
[Tooltip("Seconds for a connecting line to fully draw from previous node to next-node position.")]
public float lineGrowDuration = 0.8f;
[Tooltip("Seconds for a new node to fade in (emission lerp 0 → full) after the line completes.")]
public float nodeFadeInDuration = 0.5f;
[Tooltip("Connecting line width in meters.")]
public float lineWidth = 0.008f;
```

- [ ] **Step 2: Add line-tracking list**

After `_nodeLabels`:
```csharp
private List<LineRenderer> _lines = new List<LineRenderer>();
```

- [ ] **Step 3: Refactor `AdvanceTo` to use coroutines + queue**

Replace `AdvanceTo`:

```csharp
private Coroutine _growthCoroutine;
private readonly Queue<int> _pendingTargets = new Queue<int>();

private void AdvanceTo(int target)
{
    if (target <= _currentStageIndex) return;
    _pendingTargets.Enqueue(target);
    if (_growthCoroutine == null)
        _growthCoroutine = StartCoroutine(ProcessGrowthQueue());
}

private System.Collections.IEnumerator ProcessGrowthQueue()
{
    while (_pendingTargets.Count > 0)
    {
        int target = _pendingTargets.Dequeue();
        while (_currentStageIndex < target)
        {
            int nextIdx = _currentStageIndex + 1;
            if (_currentStageIndex < 0)
            {
                // Node 0 (Capture) — instant spawn, no line precedes it
                SpawnNode(nextIdx);
                yield return new WaitForSeconds(nodeFadeInDuration);  // visual breathing room
            }
            else
            {
                // Grow line from previous node to next position, then spawn + fade
                yield return GrowLineToNext(nextIdx);
                SpawnNode(nextIdx);
                yield return FadeInNode(nextIdx);
            }
            _currentStageIndex = nextIdx;
        }
    }
    _growthCoroutine = null;
}
```

- [ ] **Step 4: Implement `GrowLineToNext` coroutine**

```csharp
private System.Collections.IEnumerator GrowLineToNext(int nextIdx)
{
    if (_nodes.Count == 0) yield break;
    GameObject prevNode = _nodes[_nodes.Count - 1];
    Vector3 startPos = prevNode.transform.position;
    Vector3 endPos = GetNodeWorldPosition(nextIdx);

    // Create LineRenderer GameObject
    var lineGo = new GameObject($"PipelineLine_{nextIdx - 1:D2}_to_{nextIdx:D2}");
    lineGo.transform.SetParent(this.transform, worldPositionStays: true);
    var line = lineGo.AddComponent<LineRenderer>();
    line.useWorldSpace = true;
    line.positionCount = 2;
    line.startWidth = lineWidth;
    line.endWidth = lineWidth;
    line.material = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
    line.material.SetColor("_BaseColor", nodeEmissiveColor * nodeEmissiveIntensity);
    line.material.EnableKeyword("_EMISSION");
    line.material.SetColor("_EmissionColor", nodeEmissiveColor * nodeEmissiveIntensity);
    line.SetPosition(0, startPos);
    line.SetPosition(1, startPos);  // start collapsed
    _lines.Add(line);

    Debug.Log($"[PipelineProgress] growing line {nextIdx - 1}→{nextIdx}: {startPos:F3} → {endPos:F3}");

    float t = 0f;
    while (t < lineGrowDuration)
    {
        t += Time.deltaTime;
        float u = Smootherstep(Mathf.Clamp01(t / lineGrowDuration));
        Vector3 cur = Vector3.Lerp(startPos, endPos, u);
        line.SetPosition(1, cur);
        yield return null;
    }
    line.SetPosition(1, endPos);
}
```

- [ ] **Step 5: Implement `FadeInNode` coroutine**

```csharp
private System.Collections.IEnumerator FadeInNode(int idx)
{
    if (idx >= _nodes.Count) yield break;
    GameObject node = _nodes[idx];
    Renderer rend = node.GetComponent<Renderer>();
    Material mat = rend.material;
    TextMeshPro label = idx < _nodeLabels.Count ? _nodeLabels[idx] : null;

    Color startEmission = nodeEmissiveColor * 0f;
    Color endEmission = nodeEmissiveColor * nodeEmissiveIntensity;
    Color startLabelColor = labelColor;
    startLabelColor.a = 0f;
    Color endLabelColor = labelColor;

    float t = 0f;
    while (t < nodeFadeInDuration)
    {
        t += Time.deltaTime;
        float u = Mathf.Clamp01(t / nodeFadeInDuration);
        mat.SetColor("_EmissionColor", Color.Lerp(startEmission, endEmission, u));
        if (label != null) label.color = Color.Lerp(startLabelColor, endLabelColor, u);
        yield return null;
    }
    mat.SetColor("_EmissionColor", endEmission);
    if (label != null) label.color = endLabelColor;
}
```

- [ ] **Step 6: Add Smootherstep helper**

```csharp
private static float Smootherstep(float u) => u * u * u * (u * (u * 6f - 15f) + 10f);
```

- [ ] **Step 7: Modify `SpawnNode` to spawn with ZERO emission for non-zero indices (let `FadeInNode` ramp them up)**

In the material setup section of `SpawnNode`, change:
```csharp
mat.SetColor("_EmissionColor", nodeEmissiveColor * nodeEmissiveIntensity);
```
to:
```csharp
// Node 0 spawns at full emission; others start at 0 and FadeInNode ramps them up
float initialIntensity = idx == 0 ? nodeEmissiveIntensity : 0f;
mat.SetColor("_EmissionColor", nodeEmissiveColor * initialIntensity);
```

And in the label setup, similarly start non-zero indices at alpha=0:
```csharp
Color initialLabelColor = labelColor;
initialLabelColor.a = idx == 0 ? 1f : 0f;
tmp.color = initialLabelColor;
```

- [ ] **Step 8: Extend `DespawnAll` to also nuke lines**

```csharp
private void DespawnAll()
{
    foreach (var n in _nodes)
        if (n != null) Destroy(n);
    foreach (var l in _lines)
        if (l != null && l.gameObject != null) Destroy(l.gameObject);
    _nodes.Clear();
    _nodeLabels.Clear();
    _lines.Clear();
    _pendingTargets.Clear();
    if (_growthCoroutine != null) { StopCoroutine(_growthCoroutine); _growthCoroutine = null; }
}
```

- [ ] **Step 9: Commit**

```bash
cd /Users/digispoc06/Documents/UnityProjects/HoloBornUnity
git add Assets/HoloBorn/Scripts/SpawnRitual/PipelineProgressController.cs
git commit -m "$(cat <<'EOF'
feat(progress-indicator): T5 — neural-axon growth animation

Each non-zero-index node now ARRIVES via animation instead of instant-pop:
1. Thin cyan emissive LineRenderer grows from previous node to next-node
   world position over lineGrowDuration (Smootherstep)
2. New node spawns at zero emission + invisible label
3. FadeInNode coroutine lerps emission 0 → full + label alpha 0 → 1 over
   nodeFadeInDuration

Node 0 (Capture) bypasses growth — instant spawn at full emission as the
seed of the chain.

Queue-based AdvanceTo handles multiple stages arriving close together
(rare in practice but defensive).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Scene wiring + sideload verify

**Files:**
- Modify: `/Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/Scenes/SampleScene.unity`

Add `PipelineProgressController` MonoBehaviour to the SpawnRitualController GameObject (the same one that hosts ScanLineTransitionController, Stage3GracefulArrivalController, etc.).

- [ ] **Step 1: Find PipelineProgressController GUID**

```bash
cat /Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/HoloBorn/Scripts/SpawnRitual/PipelineProgressController.cs.meta
```

Note the `guid:` value (e.g. `abc123...`).

- [ ] **Step 2: Find the SpawnRitualController GameObject's components list in SampleScene.unity**

```bash
grep -n "1975890377\|Stage3GracefulArrivalController\|1975890369" /Users/digispoc06/Documents/UnityProjects/HoloBornUnity/Assets/Scenes/SampleScene.unity | head -20
```

The GameObject is `&1975890369` and currently lists components 1975890370–1975890377 (Stage3GracefulArrivalController is the last). Read lines 1540-1560 to see the components array.

- [ ] **Step 3: Add new MonoBehaviour entry after the Stage3GracefulArrivalController block**

Find the end of Stage3GracefulArrivalController block (after `matchRiggedScaleToRetex: 1`) and INSERT a new MonoBehaviour block before `--- !u!1660057539 &9223372036854775807`:

```yaml
--- !u!114 &1975890378
MonoBehaviour:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  m_GameObject: {fileID: 1975890369}
  m_Enabled: 1
  m_EditorHideFlags: 0
  m_Script: {fileID: 11500000, guid: <PASTE_PipelineProgressController_GUID_HERE>, type: 3}
  m_Name:
  m_EditorClassIdentifier:
  mannequinController: {fileID: 1975890375}
  columnOffsetFromMannequin: {x: 0.8, y: 0.4, z: 0}
  nodeVerticalSpacing: -0.2
  nodeDiameterMeters: 0.12
  nodeEmissiveColor: {r: 0, g: 0.88, b: 1, a: 1}
  nodeEmissiveIntensity: 2
  labelFontSize: 0.06
  labelColor: {r: 0, g: 0.88, b: 1, a: 1}
  labelVerticalOffset: -0.1
  lineGrowDuration: 0.8
  nodeFadeInDuration: 0.5
  lineWidth: 0.008
```

- [ ] **Step 4: Add the component fileID to the GameObject's `m_Component` list**

Find the GameObject block at `&1975890369` (around line 1540). Look for the `m_Component:` array. After the last entry (which references `{fileID: 1975890377}`), add:

```yaml
  - component: {fileID: 1975890378}
```

So the array grows from 8 entries to 9.

- [ ] **Step 5: Sideload build and run**

In Unity Editor: File → Build And Run (or use existing build script).

On Quest with simulator open:
1. Press `1` (Editor) or Y (device) → BeginRitual fires → Node 0 ("Capture") appears instantly at full brightness
2. Press `4` → "portraitizing" status → line grows from Capture → Refining Portrait node appears
3. Press `5` → "generating" → line + Sculpting Body
4. Press `6` → "retexturing" → line + Painting Skin
5. Press `2` → "rigging" → line + Adding Bones (phase transitions to Revealed; Stage 2 scan begins)
6. Press `3` → "complete" → phase transitions to Awakened → Stage 3 ritual fires + final node ("Awakening") grows in

Capture logs via:
```bash
adb logcat -s "Unity:*" | grep -E "PipelineProgress|SpawnRitual"
```

- [ ] **Step 6: Verify each stage**

Expected sideload checklist:
- [ ] Node 0 spawns at full emission within ~0.5s of BeginRitual
- [ ] Each subsequent stage: line grows ~0.8s, node fades in ~0.5s (total ~1.3s per stage)
- [ ] Labels readable at MR viewing distance (~1-2m)
- [ ] Column position right of mannequin, ~80cm offset, vertical stack readable in headset
- [ ] No frame drops during growth animation
- [ ] BeginRitual restart: column despawns cleanly, no orphan nodes/lines
- [ ] Stage 6 ("Awakening") fires when Awakened phase entered (during Stage 3 ritual)

- [ ] **Step 7: Commit**

```bash
cd /Users/digispoc06/Documents/UnityProjects/HoloBornUnity
git add Assets/Scenes/SampleScene.unity
git commit -m "$(cat <<'EOF'
feat(progress-indicator): T6 — scene wiring + sideload verified

PipelineProgressController MonoBehaviour wired to the SpawnRitualController
GameObject in SampleScene.unity. Inspector defaults match Brick T4-T5 design
(column 80cm right of mannequin, -20cm vertical spacing, 12cm node disc,
800ms line grow, 500ms node fade).

Sideload verified end-to-end: Y1 → Capture node, 4/5/6 advance through
Refining Portrait/Sculpting Body/Painting Skin with neural-axon growth,
2 fires rigging (Adding Bones + Stage 2 scan), 3 fires complete (Awakening
+ Stage 3 ritual).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- ✓ Neural-axon growth pattern (one node visible at start, axons extending to birth next nodes) — Task 5
- ✓ 6 stages with non-tech labels — Task 3 (StageLabels array)
- ✓ Curved vertical column to right of mannequin — Task 4 (columnOffsetFromMannequin)
- ✓ Backend granular events — Task 1
- ✓ Sideload-testable without real backend — Task 2 (debug simulator)

**2. Placeholder scan:**
- One `<PASTE_GENERATED_GUID_HERE>` in Task 3.4 — by design (engineer generates GUID at execution time)
- One `<PASTE_PipelineProgressController_GUID_HERE>` in Task 6.3 — by design (depends on Task 3.4 result)
- No "TBD" / "implement later" / vague references

**3. Type consistency:**
- `MapStatusToStageIndex(string)` — declared in Task 3.3, tested in Task 3.1, called in Task 3.3 `HandleStatusChanged` — consistent
- `StageLabels[]` — declared as `public static readonly string[]` in Task 3.3, tested in Task 3.1, indexed in Tasks 4 + 5 — consistent
- `SpawnNode(int idx)` returns `GameObject`, called in Tasks 4 and 5 — consistent
- `_nodes` / `_nodeLabels` / `_lines` lists — consistently typed across Tasks 4 + 5
- `Vector3 columnOffsetFromMannequin`, `float nodeVerticalSpacing` — Inspector field types match scene YAML floats in Task 6.3

---

## Open Questions Resolved Pre-Build

| Question | Decision | Rationale |
|---|---|---|
| Distinct glyph icons per stage? | Skip for v1 — text labels carry semantics | Procedural icons add 1-2 hours; labels are unambiguous (per Parthiv's non-tech-user rule). Add icons in a polish brick if labels read flat. |
| Halo ring vs vertical column? | Vertical column to right | 6 nodes crowd a halo at 60° spacing; column is more readable and matches the ChatGPT visualization we converged on. |
| Real backend integration today? | Use existing FeedBackendStatus polling | Backend already emits "portraitizing/generating/retexturing/rigging" status strings; PipelineProgressController is layered on top of the existing polling chain via the new OnBackendStatusChanged event. |

---

## What This Plan Does NOT Decide

- Audio cues per stage (deferred — Brick 5b polish if needed)
- Icon assets per node (deferred — text-only v1)
- Stage 3 callback animation (column dissolving into avatar's halo on Awakened) — possible polish, not needed for EOW
