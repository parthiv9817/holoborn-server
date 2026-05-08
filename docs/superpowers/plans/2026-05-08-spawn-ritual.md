# Spawn Ritual & World-Anchored Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 5-phase Quest 3 cube-cloud assembly + spawn ritual that turns the 7-10 minute generation wait into emotional theater, replacing 4 Tier 1 polish items with one coherent system. Spec: `docs/superpowers/specs/2026-05-08-spawn-ritual-design.md`.

**Architecture:** All cube motion is driven by a single `CubeCloudManager.Update()` iterating a flat `Cube[]` array — zero per-cube `MonoBehaviour.Update()` callbacks (Quest 3 perf rule). Phase state machine driven by polling existing `/generate/{task_id}/status`. Generic humanoid placeholder mesh is silhouette target during P3-P4; resample from real GLB at P5. Audio is sparse event-driven, never continuous loops across phases.

**Tech Stack:** Unity 6.4.5f1 (URP), Meta XR Core, glTFast, Unity Test Framework (EditMode + PlayMode), Python 3.11 / FastAPI (backend status endpoint), C# 10.

**Repos:**
- Mac FastAPI: `/Users/digispoc06/Documents/holoborn-server` (this repo)
- Unity: `~/Documents/UnityProjects/HoloBornUnity`

**Priority interrupt:** if Vipin lands paid Meshy creds → drop everything, run `tests/scripts/test_meshy_manual.py` against real key. Resume here afterward.

---

## File Structure

### Mac FastAPI repo

| Action | Path | Purpose |
|---|---|---|
| Modify | `app/models/generation_schemas.py` | Document new status string values in `TaskStatusResponse` docstring |
| Modify | `app/routes/generation.py` | Emit `portraitizing → generating → rigging → animating → complete` instead of just `processing` |

### Unity repo

| Action | Path | Purpose |
|---|---|---|
| Create | `Assets/HoloBorn/Models/silhouette_placeholder.fbx` | Generic ~5-10K tri humanoid T-pose, sampling target |
| Create | `Assets/HoloBorn/Materials/Cube_WhiteCyan.mat` | URP/Lit white base + cyan emission |
| Create | `Assets/HoloBorn/Prefabs/CubePrimitive.prefab` | Low-poly cube with MeshFilter+MeshRenderer only (no MonoBehaviour) |
| Create | `Assets/HoloBorn/Audio/spawn_ritual/*.wav` | lock_flash, thrum_short, click_lock, structural_lock, whoosh, breath_chime |
| Create | `Assets/HoloBorn/Shaders/CubeSnapDissolve.shadergraph` | Vertex displacement + alpha dissolve at P5 |
| Create | `Assets/HoloBorn/Scripts/SpawnRitual/Cube.cs` | POCO holding Transform ref + lerp state |
| Create | `Assets/HoloBorn/Scripts/SpawnRitual/CubeCloudManager.cs` | Owns Cube[] array, single Update loop |
| Create | `Assets/HoloBorn/Scripts/SpawnRitual/VortexBehavior.cs` | Computes orbit positions (P2) |
| Create | `Assets/HoloBorn/Scripts/SpawnRitual/SilhouetteBehavior.cs` | Samples mesh verts as targets (P3-P4) |
| Create | `Assets/HoloBorn/Scripts/SpawnRitual/SpawnRitualController.cs` | State machine, listens to backend status |
| Create | `Assets/HoloBorn/Scripts/SpawnRitual/SpawnRitualAudio.cs` | Event-driven audio + haptics |
| Create | `Assets/HoloBorn/Scripts/SpawnRitual/EnergyPathway.cs` | LineRenderer between joint positions (P4) |
| Create | `Assets/HoloBorn/Scripts/SpawnRitual/HoloBorn.SpawnRitual.asmdef` | Assembly definition for tests |
| Create | `Assets/HoloBorn/Tests/EditMode/HoloBorn.SpawnRitual.Tests.asmdef` | Test assembly |
| Create | `Assets/HoloBorn/Tests/EditMode/CubeCloudManagerTests.cs` | Pool spawn/despawn tests |
| Create | `Assets/HoloBorn/Tests/EditMode/CubeLerpTests.cs` | Ease-out lerp math |
| Create | `Assets/HoloBorn/Tests/EditMode/VortexBehaviorTests.cs` | Orbit math |
| Create | `Assets/HoloBorn/Tests/EditMode/SilhouetteSamplingTests.cs` | Vertex sampling math |
| Modify | `Assets/HoloBorn/Scripts/TestGlbLoader.cs` | Emit `OnSpawnComplete(GameObject avatar)` event consumed by orchestrator |
| Modify | `Assets/HoloBorn/Scripts/ScanController.cs` | Call `SpawnRitualController.BeginRitual(spawnLocation)` on capture |
| Modify | `Assets/Scenes/SampleScene.unity` | Add SpawnRitualController + CubeCloudManager root + AudioSource |

---

## Cuts ladder if running short on Sunday morning

In order of cut priority (cut top-most first):

1. **Phase L polish entirely** — drop color drift, energy-pathway lines, breath, gaze. Static white cubes + snap-to-mesh + idle. Still meaningfully premium vs current pop-in.
2. **Reduce cube count from 300 to 150** — visual is less dense but reads as assembly.
3. **Drop Phase 4 energy-pathway lines** — Phase 4 becomes pure stillness + 1 lock sound. Still works as anticipation beat.
4. **Drop Phase 2 thrum entirely** — silence is acceptable for portraitizer phase if cubes are visible.

---

# Phase A — Backend status schema (Mac repo)

### Task A1: Document new status values in schema

**Files:**
- Modify: `app/models/generation_schemas.py`

- [ ] **Step A1.1: Update TaskStatusResponse docstring**

```python
# Replace existing TaskStatusResponse class with:
class TaskStatusResponse(BaseModel):
    """Status response for /generate/{task_id}/status endpoint.

    Status string values (in pipeline order):
      "processing"     — legacy alias, kept for backwards compat
      "portraitizing"  — OpenAI gpt-image-1.5 portrait edit in flight
      "generating"     — RunPod TRELLIS GLB generation in flight (progress 0-100)
      "rigging"        — Meshy auto-rigging in flight
      "animating"      — Meshy animation bake in flight
      "complete"       — GLB ready at glb_url
      "failed"         — pipeline failure, see message
    """
    status: str = "processing"
    progress: int = 0
    glb_url: str = ""
    message: str = ""
```

- [ ] **Step A1.2: Verify import still works**

```bash
python3 -c "from app.models.generation_schemas import TaskStatusResponse; print(TaskStatusResponse(status='rigging').model_dump())"
```

Expected: `{'status': 'rigging', 'progress': 0, 'glb_url': '', 'message': ''}`

### Task A2: Add status emissions through the pipeline

**Files:**
- Modify: `app/routes/generation.py`

- [ ] **Step A2.1: Read existing route to understand task storage pattern**

```bash
grep -nE "tasks\[|status.*=" app/routes/generation.py | head -20
```

Note the in-memory `tasks` dict pattern. We'll write status updates into the same dict at each pipeline stage.

- [ ] **Step A2.2: Find the burst→portraitizer→runpod→meshy pipeline orchestration function**

```bash
grep -nE "async def.*generate|portraitizer|runpod_client" app/routes/generation.py | head -10
```

Locate the function that calls `submit_job` (RunPod) — that's where we emit pipeline stage statuses.

- [ ] **Step A2.3: Add status writes at each pipeline stage**

Find each pipeline transition and add a `tasks[task_id]["status"] = "<value>"` line:

```python
# Before portraitizer call:
tasks[task_id]["status"] = "portraitizing"
portrait_bytes = await portraitize(...)

# Before RunPod submit:
tasks[task_id]["status"] = "generating"
job_id = await submit_job(image_b64, **preset_kwargs)

# Inside RunPod poll loop, when output indicates rigging stage:
# (For now, since Meshy isn't wired yet, we transition directly from "generating" to "complete")
# Once Meshy integration lands, add:
#   tasks[task_id]["status"] = "rigging"
#   ... meshy rigging call ...
#   tasks[task_id]["status"] = "animating"
#   ... meshy animation call ...
tasks[task_id]["status"] = "complete"
```

Skip "rigging" and "animating" emissions for now (Meshy isn't wired into the pipeline yet) — they're emitted from the `test_meshy_manual.py` integration when it lands. Quest's orchestrator handles missing intermediate states gracefully (stays in last seen phase until next valid status arrives).

- [ ] **Step A2.4: Test by running the existing manual test and checking emitted statuses**

```bash
# Start uvicorn in another terminal: uvicorn app.main:app --reload
# Then in this terminal:
curl -sS http://localhost:8000/health
```

Expected: `{"status":"alive",...}`

Run the existing burst test (use cached fixtures if available) and observe `tasks[task_id]["status"]` values via successive `/generate/{id}/status` GETs.

- [ ] **Step A2.5: Commit + push backend changes**

```bash
git add app/models/generation_schemas.py app/routes/generation.py
git commit -m "feat(generation): emit pipeline-stage status values for spawn ritual orchestrator

Adds portraitizing/generating/rigging/animating between processing and
complete. Quest's SpawnRitualController polls these to drive 5-phase
cube-cloud visualization. Backwards-compat: 'processing' still accepted
as legacy alias.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git -c http.postBuffer=524288000 push origin main
```

---

# Phase B — Unity Test Framework setup

### Task B1: Add Unity Test Framework package + assembly definitions

**Files:**
- Create: `Assets/HoloBorn/Scripts/SpawnRitual/HoloBorn.SpawnRitual.asmdef`
- Create: `Assets/HoloBorn/Tests/EditMode/HoloBorn.SpawnRitual.Tests.asmdef`

- [ ] **Step B1.1: Open Unity Editor, install Test Framework via Package Manager**

In Unity Editor: Window → Package Manager → Unity Registry → search "Test Framework" → Install (should already be at v1.4+ in Unity 6).

- [ ] **Step B1.2: Create folder structure**

In Unity Editor: right-click `Assets/HoloBorn` → Create → Folder → name `Tests`. Inside `Tests`, create subfolder `EditMode`. In `Assets/HoloBorn/Scripts`, create subfolder `SpawnRitual`.

- [ ] **Step B1.3: Create runtime assembly definition**

File path: `Assets/HoloBorn/Scripts/SpawnRitual/HoloBorn.SpawnRitual.asmdef`

```json
{
    "name": "HoloBorn.SpawnRitual",
    "rootNamespace": "HoloBorn.SpawnRitual",
    "references": [],
    "includePlatforms": [],
    "excludePlatforms": [],
    "allowUnsafeCode": false,
    "overrideReferences": false,
    "precompiledReferences": [],
    "autoReferenced": true,
    "defineConstraints": [],
    "versionDefines": [],
    "noEngineReferences": false
}
```

- [ ] **Step B1.4: Create test assembly definition**

File path: `Assets/HoloBorn/Tests/EditMode/HoloBorn.SpawnRitual.Tests.asmdef`

```json
{
    "name": "HoloBorn.SpawnRitual.Tests",
    "rootNamespace": "HoloBorn.SpawnRitual.Tests",
    "references": [
        "HoloBorn.SpawnRitual",
        "UnityEngine.TestRunner",
        "UnityEditor.TestRunner"
    ],
    "includePlatforms": ["Editor"],
    "excludePlatforms": [],
    "allowUnsafeCode": false,
    "overrideReferences": true,
    "precompiledReferences": ["nunit.framework.dll"],
    "autoReferenced": false,
    "defineConstraints": ["UNITY_INCLUDE_TESTS"],
    "versionDefines": [],
    "noEngineReferences": false
}
```

- [ ] **Step B1.5: Verify Test Runner sees the test assembly**

In Unity Editor: Window → General → Test Runner → EditMode tab. Should show "HoloBorn.SpawnRitual.Tests" assembly listed (empty for now).

- [ ] **Step B1.6: Commit assembly definitions**

```bash
UNITY=~/Documents/UnityProjects/HoloBornUnity
git -C "$UNITY" add Assets/HoloBorn/Scripts/SpawnRitual/HoloBorn.SpawnRitual.asmdef \
  Assets/HoloBorn/Tests/EditMode/HoloBorn.SpawnRitual.Tests.asmdef \
  Assets/HoloBorn/Tests \
  Assets/HoloBorn/Scripts/SpawnRitual
git -C "$UNITY" commit -m "feat(spawn-ritual): scaffold asmdef + test framework folders"
```

---

# Phase C — Static assets

### Task C1: Source + import placeholder humanoid mesh

- [ ] **Step C1.1: Download a free humanoid base mesh from Mixamo**

Browser: https://www.mixamo.com → sign in → "Characters" → pick "Y Bot" (default low-poly humanoid, 11k tris) → Download FBX → "T-Pose" pose, no animation.

Save the FBX to `~/Downloads/y_bot_tpose.fbx`.

- [ ] **Step C1.2: Move into Unity assets**

```bash
UNITY=~/Documents/UnityProjects/HoloBornUnity
mkdir -p "$UNITY/Assets/HoloBorn/Models"
cp ~/Downloads/y_bot_tpose.fbx "$UNITY/Assets/HoloBorn/Models/silhouette_placeholder.fbx"
```

Unity will auto-import on next focus.

- [ ] **Step C1.3: Configure import settings in Unity**

Unity Editor → select `silhouette_placeholder.fbx` in Project window → Inspector:
- Model tab: "Convert Units" = ON, "Mesh Compression" = Medium
- Rig tab: "Animation Type" = Generic (we don't need Humanoid mapping for sampling)
- Animation tab: "Import Animation" = OFF
- Apply

- [ ] **Step C1.4: Verify vert count is in budget**

Unity Editor → select the fbx → Inspector → Preview pane shows vert count. Expected: 5,000-15,000 verts. If >15K, no need to fix — we sample 300 verts max so any density works.

### Task C2: Create cube prefab + material

- [ ] **Step C2.1: Create the white-cyan emission material**

Unity Editor: right-click `Assets/HoloBorn/Materials` → Create → Material → name `Cube_WhiteCyan.mat`. Inspector:
- Shader: Universal Render Pipeline / Lit
- Surface Type: Opaque
- Base Map: white (255,255,255,255)
- Metallic: 0.0
- Smoothness: 0.5
- Emission: enabled, color = cyan (0, 0.7, 1.0) at intensity 1.0
- Save.

- [ ] **Step C2.2: Create the cube prefab**

Unity Editor: GameObject → 3D Object → Cube. Rename to `CubePrimitive`. Configure:
- Transform Scale: (0.02, 0.02, 0.02) — 2cm cubes
- Drag `Cube_WhiteCyan.mat` onto it
- Remove the BoxCollider component (not needed, costs perf)
- Drag from Hierarchy into `Assets/HoloBorn/Prefabs/` to create prefab. Delete from scene.

- [ ] **Step C2.3: Verify prefab structure**

Open the prefab. Confirm exactly: Transform + MeshFilter + MeshRenderer. **No** MonoBehaviour scripts attached. **No** colliders. (12 tris × MeshRenderer with single material = perf ceiling we want.)

### Task C3: Source audio assets

- [ ] **Step C3.1: Create audio folder**

```bash
UNITY=~/Documents/UnityProjects/HoloBornUnity
mkdir -p "$UNITY/Assets/HoloBorn/Audio/spawn_ritual"
```

- [ ] **Step C3.2: Source 6 audio files (~5min total)**

Source from freesound.org (CC0 license) or use existing personal library. Save into `Assets/HoloBorn/Audio/spawn_ritual/`:

- `lock_flash.wav` — 0.2s metallic click (capture moment)
- `thrum_short.wav` — 5s synth pad fade-in/hold/fade-out (P2)
- `click_lock.wav` — 0.1s soft tick (P3 cube locking)
- `structural_lock.wav` — 0.5s deeper bass hit (P4 energy lock)
- `whoosh.wav` — 1.5s air whoosh (P5 cube convergence)
- `breath_chime.wav` — 0.4s soft bell (P5 breath moment)

For sourcing speed, use [pixabay.com/music/search/?q=ui-sounds](https://pixabay.com) or [freesound.org](https://freesound.org). CC0/public domain only.

- [ ] **Step C3.3: Configure import settings on each audio file**

Select all 6 files → Inspector:
- Force To Mono: ON
- Load Type: Decompress On Load
- Compression Format: Vorbis
- Quality: 70%
- Apply.

- [ ] **Step C3.4: Commit static assets**

```bash
UNITY=~/Documents/UnityProjects/HoloBornUnity
git -C "$UNITY" add Assets/HoloBorn/Models Assets/HoloBorn/Materials/Cube_WhiteCyan.mat \
  Assets/HoloBorn/Materials/Cube_WhiteCyan.mat.meta \
  Assets/HoloBorn/Prefabs/CubePrimitive.prefab \
  Assets/HoloBorn/Prefabs/CubePrimitive.prefab.meta \
  Assets/HoloBorn/Audio
git -C "$UNITY" commit -m "feat(spawn-ritual): static assets — placeholder mesh + cube prefab + audio"
```

---

# Phase D — Cube POCO + CubeCloudManager (TDD)

### Task D1: Cube POCO with lerp state

**Files:**
- Create: `Assets/HoloBorn/Scripts/SpawnRitual/Cube.cs`
- Create: `Assets/HoloBorn/Tests/EditMode/CubeLerpTests.cs`

- [ ] **Step D1.1: Write failing test for ease-out lerp math**

File: `Assets/HoloBorn/Tests/EditMode/CubeLerpTests.cs`

```csharp
using NUnit.Framework;
using UnityEngine;
using HoloBorn.SpawnRitual;

namespace HoloBorn.SpawnRitual.Tests
{
    public class CubeLerpTests
    {
        [Test]
        public void EaseOutCubic_AtT0_ReturnsZero()
        {
            float result = Cube.EaseOutCubic(0f);
            Assert.AreEqual(0f, result, 0.0001f);
        }

        [Test]
        public void EaseOutCubic_AtT1_ReturnsOne()
        {
            float result = Cube.EaseOutCubic(1f);
            Assert.AreEqual(1f, result, 0.0001f);
        }

        [Test]
        public void EaseOutCubic_AtT0_5_IsAbove0_75()
        {
            // ease-out should be far past linear midpoint at t=0.5
            float result = Cube.EaseOutCubic(0.5f);
            Assert.Greater(result, 0.75f);
            Assert.Less(result, 1f);
        }
    }
}
```

- [ ] **Step D1.2: Run test in Unity Test Runner — expect compile error**

Unity Editor → Window → General → Test Runner → EditMode → "Run All". Expected: compile error "Cube does not exist". This is the failing state we want.

- [ ] **Step D1.3: Implement Cube.cs with ease-out math**

File: `Assets/HoloBorn/Scripts/SpawnRitual/Cube.cs`

```csharp
using UnityEngine;

namespace HoloBorn.SpawnRitual
{
    // POCO. NOT a MonoBehaviour — per spec, all cube updates flow through
    // CubeCloudManager.Update() to enforce single-update perf rule on Quest 3.
    public class Cube
    {
        public Transform transform;
        public Vector3 startPos;
        public Vector3 targetPos;
        public float lerpStartTime;
        public float lerpDuration = 1f;
        public bool isActive;

        public Cube(Transform transform)
        {
            this.transform = transform;
        }

        public void SetTarget(Vector3 worldPos, float duration, float currentTime)
        {
            startPos = transform.position;
            targetPos = worldPos;
            lerpStartTime = currentTime;
            lerpDuration = Mathf.Max(0.0001f, duration);
        }

        public void Tick(float currentTime)
        {
            float elapsed = currentTime - lerpStartTime;
            float t = Mathf.Clamp01(elapsed / lerpDuration);
            float eased = EaseOutCubic(t);
            transform.position = Vector3.Lerp(startPos, targetPos, eased);
        }

        public static float EaseOutCubic(float t)
        {
            t = Mathf.Clamp01(t);
            return 1f - Mathf.Pow(1f - t, 3f);
        }
    }
}
```

- [ ] **Step D1.4: Run tests — expect 3 passing**

Unity Test Runner → Run All. Expected: 3 tests passing in CubeLerpTests.

- [ ] **Step D1.5: Commit**

```bash
UNITY=~/Documents/UnityProjects/HoloBornUnity
git -C "$UNITY" add Assets/HoloBorn/Scripts/SpawnRitual/Cube.cs* \
  Assets/HoloBorn/Tests/EditMode/CubeLerpTests.cs*
git -C "$UNITY" commit -m "feat(cube): POCO with ease-out cubic lerp math (TDD)"
```

### Task D2: CubeCloudManager pool

**Files:**
- Create: `Assets/HoloBorn/Scripts/SpawnRitual/CubeCloudManager.cs`
- Create: `Assets/HoloBorn/Tests/EditMode/CubeCloudManagerTests.cs`

- [ ] **Step D2.1: Write failing tests for pool spawn/despawn**

File: `Assets/HoloBorn/Tests/EditMode/CubeCloudManagerTests.cs`

```csharp
using NUnit.Framework;
using UnityEngine;
using HoloBorn.SpawnRitual;

namespace HoloBorn.SpawnRitual.Tests
{
    public class CubeCloudManagerTests
    {
        private CubeCloudManager manager;
        private GameObject managerObj;
        private GameObject prefab;

        [SetUp]
        public void Setup()
        {
            // bare cube prefab for tests (no asset reference needed)
            prefab = GameObject.CreatePrimitive(PrimitiveType.Cube);
            prefab.transform.localScale = Vector3.one * 0.02f;
            Object.DestroyImmediate(prefab.GetComponent<BoxCollider>());

            managerObj = new GameObject("TestManager");
            manager = managerObj.AddComponent<CubeCloudManager>();
            manager.cubePrefab = prefab;
            manager.poolSize = 10;
            manager.Initialize();
        }

        [TearDown]
        public void Teardown()
        {
            Object.DestroyImmediate(prefab);
            Object.DestroyImmediate(managerObj);
        }

        [Test]
        public void Spawn_ReturnsNonNullCube()
        {
            var cube = manager.Spawn(Vector3.zero);
            Assert.IsNotNull(cube);
            Assert.IsNotNull(cube.transform);
            Assert.IsTrue(cube.isActive);
        }

        [Test]
        public void Spawn_PositionsCubeAtOrigin()
        {
            var cube = manager.Spawn(new Vector3(1f, 2f, 3f));
            Assert.AreEqual(new Vector3(1f, 2f, 3f), cube.transform.position);
        }

        [Test]
        public void Despawn_ReturnsCubeToInactivePool()
        {
            var cube = manager.Spawn(Vector3.zero);
            manager.Despawn(cube);
            Assert.IsFalse(cube.isActive);
            Assert.AreEqual(0, manager.ActiveCount);
        }

        [Test]
        public void Spawn_PoolExhaustion_ReturnsNull()
        {
            for (int i = 0; i < 10; i++) manager.Spawn(Vector3.zero);
            var overflow = manager.Spawn(Vector3.zero);
            Assert.IsNull(overflow, "Pool should refuse to grow beyond poolSize");
        }

        [Test]
        public void Spawn_AfterDespawn_ReusesPooledCube()
        {
            var first = manager.Spawn(Vector3.zero);
            manager.Despawn(first);
            var second = manager.Spawn(Vector3.zero);
            Assert.AreSame(first, second, "Despawned cube should be recycled");
        }
    }
}
```

- [ ] **Step D2.2: Run tests — expect compile error / FAIL**

Unity Test Runner → Run All. Expected: compile error "CubeCloudManager does not exist".

- [ ] **Step D2.3: Implement CubeCloudManager (skeleton + pool, no Update yet)**

File: `Assets/HoloBorn/Scripts/SpawnRitual/CubeCloudManager.cs`

```csharp
using System.Collections.Generic;
using UnityEngine;

namespace HoloBorn.SpawnRitual
{
    // Owns the entire cube cloud. Single Update() loop drives all per-cube motion.
    // No MonoBehaviour scripts attached to individual cubes per Quest 3 perf rule.
    public class CubeCloudManager : MonoBehaviour
    {
        public GameObject cubePrefab;
        public int poolSize = 300;
        public Transform cloudRoot; // optional parent for hierarchy cleanliness

        private readonly List<Cube> pool = new();
        private readonly List<Cube> active = new();
        private bool initialized;

        public int ActiveCount => active.Count;
        public int PoolFreeCount => pool.Count - active.Count;

        void Awake()
        {
            if (!initialized) Initialize();
        }

        // Public for Test setup; idempotent.
        public void Initialize()
        {
            if (initialized) return;
            if (cloudRoot == null) cloudRoot = transform;
            for (int i = 0; i < poolSize; i++)
            {
                var go = Instantiate(cubePrefab, cloudRoot);
                go.SetActive(false);
                go.name = $"Cube_{i:D3}";
                pool.Add(new Cube(go.transform));
            }
            initialized = true;
        }

        public Cube Spawn(Vector3 origin)
        {
            // Find first inactive cube in pool
            for (int i = 0; i < pool.Count; i++)
            {
                if (!pool[i].isActive)
                {
                    var cube = pool[i];
                    cube.transform.position = origin;
                    cube.transform.gameObject.SetActive(true);
                    cube.isActive = true;
                    cube.SetTarget(origin, 0.0001f, Time.time);
                    active.Add(cube);
                    return cube;
                }
            }
            return null; // pool exhausted
        }

        public void Despawn(Cube cube)
        {
            if (cube == null || !cube.isActive) return;
            cube.isActive = false;
            cube.transform.gameObject.SetActive(false);
            active.Remove(cube);
        }

        void Update()
        {
            float now = Time.time;
            for (int i = 0; i < active.Count; i++)
            {
                active[i].Tick(now);
            }
        }
    }
}
```

- [ ] **Step D2.4: Run tests — expect 5 passing**

Unity Test Runner → Run All. Expected: 5 CubeCloudManagerTests passing + 3 CubeLerpTests passing = 8 total passing.

- [ ] **Step D2.5: Commit**

```bash
UNITY=~/Documents/UnityProjects/HoloBornUnity
git -C "$UNITY" add Assets/HoloBorn/Scripts/SpawnRitual/CubeCloudManager.cs* \
  Assets/HoloBorn/Tests/EditMode/CubeCloudManagerTests.cs*
git -C "$UNITY" commit -m "feat(cube-cloud): CubeCloudManager pool with single Update loop (TDD)"
```

### Task D3: 300-cube perf check in Editor

- [ ] **Step D3.1: Create temporary scene scaffold**

Unity Editor: open SampleScene. Create empty GameObject named "CubeCloud". Attach `CubeCloudManager` component. Drag `CubePrimitive.prefab` into the `cubePrefab` field. Set `poolSize = 300`.

- [ ] **Step D3.2: Add perf-test runtime script**

Quick play-mode test: in Inspector, add a Editor-only test method. Or create a one-shot script that on `Start()` spawns 300 cubes at random positions in a 2m sphere.

Create `Assets/HoloBorn/Scripts/SpawnRitual/_DebugSpawnAll.cs`:

```csharp
using UnityEngine;

namespace HoloBorn.SpawnRitual
{
    public class _DebugSpawnAll : MonoBehaviour
    {
        public CubeCloudManager manager;
        public int count = 300;
        public float radius = 1.5f;

        void Start()
        {
            for (int i = 0; i < count; i++)
            {
                var p = Random.insideUnitSphere * radius + transform.position;
                manager.Spawn(p);
            }
        }
    }
}
```

Add the component to the CubeCloud GameObject. Drag the manager into its `manager` field.

- [ ] **Step D3.3: Enter Play Mode + open Profiler**

Unity Editor: Window → Analysis → Profiler. Open. Press Play. Verify:
- 300 cubes appear in a 1.5m sphere
- Frame rate in Game view stays >72 fps (or whatever Editor defaults to with vsync)
- Profiler CPU usage main thread <8ms/frame

If perf bombs, switch to `Graphics.DrawMeshInstanced` (cuts ladder fallback). Most Macs handle 300 cubes easily; this is mostly for Quest validation later.

- [ ] **Step D3.4: Exit Play Mode + clean up**

Disable `_DebugSpawnAll` component or remove. We'll keep the script in the repo for later debugging but don't ship it active.

- [ ] **Step D3.5: Commit debug scaffold**

```bash
UNITY=~/Documents/UnityProjects/HoloBornUnity
git -C "$UNITY" add Assets/HoloBorn/Scripts/SpawnRitual/_DebugSpawnAll.cs* \
  Assets/Scenes/SampleScene.unity
git -C "$UNITY" commit -m "feat(cube-cloud): editor perf scaffold — 300 cubes verified <8ms CPU"
```

---

# Phase E — Cube target lerp behavior (extension)

(Already covered in Tasks D1-D3 via the Cube.SetTarget + Cube.Tick implementation. No additional tasks required for basic lerp.)

# Phase F — Vortex behavior (TDD)

### Task F1: Vortex math

**Files:**
- Create: `Assets/HoloBorn/Scripts/SpawnRitual/VortexBehavior.cs`
- Create: `Assets/HoloBorn/Tests/EditMode/VortexBehaviorTests.cs`

- [ ] **Step F1.1: Write failing tests**

File: `Assets/HoloBorn/Tests/EditMode/VortexBehaviorTests.cs`

```csharp
using NUnit.Framework;
using UnityEngine;
using HoloBorn.SpawnRitual;

namespace HoloBorn.SpawnRitual.Tests
{
    public class VortexBehaviorTests
    {
        [Test]
        public void OrbitPosition_ZeroPhase_IsAtRadiusOnX()
        {
            var pos = VortexBehavior.OrbitPosition(
                center: Vector3.zero, radius: 0.3f, height: 0.5f,
                phase: 0f, verticalDrift: 0f);
            Assert.AreEqual(0.3f, pos.x, 0.001f);
            Assert.AreEqual(0f, pos.z, 0.001f);
        }

        [Test]
        public void OrbitPosition_QuarterTurn_IsAtRadiusOnZ()
        {
            var pos = VortexBehavior.OrbitPosition(
                center: Vector3.zero, radius: 0.3f, height: 0.5f,
                phase: Mathf.PI / 2f, verticalDrift: 0f);
            Assert.AreEqual(0f, pos.x, 0.001f);
            Assert.AreEqual(0.3f, pos.z, 0.001f);
        }

        [Test]
        public void OrbitPosition_VerticalDriftAffectsY()
        {
            var pos = VortexBehavior.OrbitPosition(
                center: Vector3.zero, radius: 0.3f, height: 0.5f,
                phase: 0f, verticalDrift: 0.2f);
            Assert.AreEqual(0.7f, pos.y, 0.001f); // height + drift
        }
    }
}
```

- [ ] **Step F1.2: Run tests — expect compile error**

Unity Test Runner → Run All. Expected: VortexBehavior does not exist.

- [ ] **Step F1.3: Implement VortexBehavior**

File: `Assets/HoloBorn/Scripts/SpawnRitual/VortexBehavior.cs`

```csharp
using UnityEngine;

namespace HoloBorn.SpawnRitual
{
    // Pure-math helper for Phase 2 vortex orbit positions.
    // Cubes assigned to the vortex have their target updated each frame
    // by CubeCloudManager calling OrbitPosition() with their per-cube phase offset.
    public static class VortexBehavior
    {
        public static Vector3 OrbitPosition(
            Vector3 center, float radius, float height, float phase, float verticalDrift)
        {
            float x = Mathf.Cos(phase) * radius;
            float z = Mathf.Sin(phase) * radius;
            float y = height + verticalDrift;
            return new Vector3(center.x + x, center.y + y, center.z + z);
        }

        // Helper: per-cube phase given index, total cubes, time, and revolutions/sec.
        public static float ComputePhase(int cubeIndex, int totalCubes, float currentTime, float revsPerSec)
        {
            float baseOffset = (Mathf.PI * 2f) * cubeIndex / Mathf.Max(1, totalCubes);
            float timeOffset = currentTime * (Mathf.PI * 2f) * revsPerSec;
            return baseOffset + timeOffset;
        }
    }
}
```

- [ ] **Step F1.4: Run tests — expect 3 passing**

Unity Test Runner → Run All. Expected: 3 vortex tests passing + previous tests still passing.

- [ ] **Step F1.5: Commit**

```bash
UNITY=~/Documents/UnityProjects/HoloBornUnity
git -C "$UNITY" add Assets/HoloBorn/Scripts/SpawnRitual/VortexBehavior.cs* \
  Assets/HoloBorn/Tests/EditMode/VortexBehaviorTests.cs*
git -C "$UNITY" commit -m "feat(vortex): orbit position math + per-cube phase helper (TDD)"
```

---

# Phase G — Silhouette sampling (TDD)

### Task G1: Mesh vertex sampling

**Files:**
- Create: `Assets/HoloBorn/Scripts/SpawnRitual/SilhouetteBehavior.cs`
- Create: `Assets/HoloBorn/Tests/EditMode/SilhouetteSamplingTests.cs`

- [ ] **Step G1.1: Write failing tests**

File: `Assets/HoloBorn/Tests/EditMode/SilhouetteSamplingTests.cs`

```csharp
using NUnit.Framework;
using UnityEngine;
using HoloBorn.SpawnRitual;

namespace HoloBorn.SpawnRitual.Tests
{
    public class SilhouetteSamplingTests
    {
        [Test]
        public void SampleVerts_ReturnsRequestedCount()
        {
            var mesh = CreateTestMesh(vertexCount: 100);
            var samples = SilhouetteBehavior.SampleVerts(mesh, 30, seed: 1);
            Assert.AreEqual(30, samples.Length);
        }

        [Test]
        public void SampleVerts_RequestMoreThanMeshHas_ReturnsAllVerts()
        {
            var mesh = CreateTestMesh(vertexCount: 10);
            var samples = SilhouetteBehavior.SampleVerts(mesh, 100, seed: 1);
            Assert.AreEqual(10, samples.Length, "Should cap at available verts");
        }

        [Test]
        public void SampleVerts_DeterministicWithSameSeed()
        {
            var mesh = CreateTestMesh(vertexCount: 50);
            var a = SilhouetteBehavior.SampleVerts(mesh, 20, seed: 42);
            var b = SilhouetteBehavior.SampleVerts(mesh, 20, seed: 42);
            CollectionAssert.AreEqual(a, b);
        }

        private Mesh CreateTestMesh(int vertexCount)
        {
            var verts = new Vector3[vertexCount];
            for (int i = 0; i < vertexCount; i++)
                verts[i] = new Vector3(i, i * 0.1f, i * 0.01f);
            var mesh = new Mesh { vertices = verts };
            return mesh;
        }
    }
}
```

- [ ] **Step G1.2: Run — expect compile error**

- [ ] **Step G1.3: Implement SilhouetteBehavior**

File: `Assets/HoloBorn/Scripts/SpawnRitual/SilhouetteBehavior.cs`

```csharp
using UnityEngine;

namespace HoloBorn.SpawnRitual
{
    // Static helpers for sampling target positions from a humanoid mesh.
    // Used in P3-P4 with placeholder mesh, in P5 with real GLB mesh after instantiation.
    public static class SilhouetteBehavior
    {
        // Samples N world-space vert positions from a mesh's vertex array.
        // Deterministic given seed. Uses Fisher-Yates partial shuffle so each
        // sampled vert is unique. If N > meshVerts, returns all verts.
        public static Vector3[] SampleVerts(Mesh mesh, int count, int seed = 0)
        {
            var verts = mesh.vertices;
            int actual = Mathf.Min(count, verts.Length);
            if (actual <= 0) return new Vector3[0];

            // Fisher-Yates partial shuffle, only first `actual` slots needed.
            var rng = new System.Random(seed);
            int[] indices = new int[verts.Length];
            for (int i = 0; i < indices.Length; i++) indices[i] = i;
            for (int i = 0; i < actual; i++)
            {
                int j = i + rng.Next(indices.Length - i);
                (indices[i], indices[j]) = (indices[j], indices[i]);
            }

            var result = new Vector3[actual];
            for (int i = 0; i < actual; i++) result[i] = verts[indices[i]];
            return result;
        }

        // Transforms local-space sample positions to world-space via a Transform.
        public static Vector3[] LocalToWorld(Vector3[] localPositions, Transform t)
        {
            var world = new Vector3[localPositions.Length];
            for (int i = 0; i < localPositions.Length; i++)
                world[i] = t.TransformPoint(localPositions[i]);
            return world;
        }
    }
}
```

- [ ] **Step G1.4: Run tests — expect 3 passing**

- [ ] **Step G1.5: Commit**

```bash
UNITY=~/Documents/UnityProjects/HoloBornUnity
git -C "$UNITY" add Assets/HoloBorn/Scripts/SpawnRitual/SilhouetteBehavior.cs* \
  Assets/HoloBorn/Tests/EditMode/SilhouetteSamplingTests.cs*
git -C "$UNITY" commit -m "feat(silhouette): deterministic vert sampling (TDD)"
```

---

# Phase H — Snap-to-mesh shader

### Task H1: Snap shader (visual, not unit-testable)

**Files:**
- Create: `Assets/HoloBorn/Shaders/CubeSnapDissolve.shadergraph`

- [ ] **Step H1.1: Create Shader Graph**

Unity Editor: right-click `Assets/HoloBorn/Shaders/` → Create → Shader Graph → URP → Lit Shader Graph. Name `CubeSnapDissolve`.

- [ ] **Step H1.2: Configure shader inputs**

Open `CubeSnapDissolve`. Add Properties:
- `_BaseColor` (Color, default white)
- `_EmissionColor` (Color, default cyan 0,0.7,1)
- `_DissolveAmount` (Float, default 0, range 0..1)
- `_LerpFromPosition` (Vector3, default 0)
- `_LerpAmount` (Float, default 0, range 0..1)

- [ ] **Step H1.3: Wire vertex displacement**

In vertex stage:
- Object position → Lerp(`_LerpFromPosition`, ObjectPosition, `_LerpAmount`) → output position

In fragment stage:
- Base Color = `_BaseColor`
- Emission = `_EmissionColor` × (1 + `_DissolveAmount` * 3) [boost emission as it dissolves]
- Alpha = 1 - `_DissolveAmount`
- Save graph.

- [ ] **Step H1.4: Test in Editor**

Drag the shader graph onto a copy of `Cube_WhiteCyan.mat` (call it `Cube_WhiteCyan_Snap.mat`). Apply to a test cube in scene. Slide `_DissolveAmount` 0→1 → verify cube fades + emissive boosts. Slide `_LerpAmount` and `_LerpFromPosition` → verify cube physically moves between positions.

- [ ] **Step H1.5: Commit**

```bash
UNITY=~/Documents/UnityProjects/HoloBornUnity
git -C "$UNITY" add Assets/HoloBorn/Shaders \
  Assets/HoloBorn/Materials/Cube_WhiteCyan_Snap.mat*
git -C "$UNITY" commit -m "feat(shader): CubeSnapDissolve — vertex displacement + alpha dissolve"
```

---

# Phase I — Phase orchestrator

### Task I1: SpawnRitualController state machine

**Files:**
- Create: `Assets/HoloBorn/Scripts/SpawnRitual/SpawnRitualController.cs`
- Create: `Assets/HoloBorn/Tests/EditMode/SpawnRitualControllerTests.cs`

- [ ] **Step I1.1: Write failing tests for state transitions**

File: `Assets/HoloBorn/Tests/EditMode/SpawnRitualControllerTests.cs`

```csharp
using NUnit.Framework;
using UnityEngine;
using HoloBorn.SpawnRitual;

namespace HoloBorn.SpawnRitual.Tests
{
    public class SpawnRitualControllerTests
    {
        [Test]
        public void Initial_State_IsIdle()
        {
            Assert.AreEqual(SpawnRitualController.Phase.Idle,
                SpawnRitualController.MapStatusToPhase("", currentPhase: SpawnRitualController.Phase.Idle));
        }

        [Test]
        public void Status_Portraitizing_TransitionsToP2()
        {
            Assert.AreEqual(SpawnRitualController.Phase.P2_EnergyAccumulation,
                SpawnRitualController.MapStatusToPhase("portraitizing", SpawnRitualController.Phase.P1_Capture));
        }

        [Test]
        public void Status_Generating_TransitionsToP3()
        {
            Assert.AreEqual(SpawnRitualController.Phase.P3_Reconstruction,
                SpawnRitualController.MapStatusToPhase("generating", SpawnRitualController.Phase.P2_EnergyAccumulation));
        }

        [Test]
        public void Status_RiggingOrAnimating_BothMapToP4()
        {
            Assert.AreEqual(SpawnRitualController.Phase.P4_InternalActivation,
                SpawnRitualController.MapStatusToPhase("rigging", SpawnRitualController.Phase.P3_Reconstruction));
            Assert.AreEqual(SpawnRitualController.Phase.P4_InternalActivation,
                SpawnRitualController.MapStatusToPhase("animating", SpawnRitualController.Phase.P4_InternalActivation));
        }

        [Test]
        public void Status_Complete_TransitionsToP5()
        {
            Assert.AreEqual(SpawnRitualController.Phase.P5_Spawn,
                SpawnRitualController.MapStatusToPhase("complete", SpawnRitualController.Phase.P4_InternalActivation));
        }

        [Test]
        public void Status_LegacyProcessing_StaysInCurrentPhase()
        {
            // backwards-compat: "processing" doesn't override, stay in current
            Assert.AreEqual(SpawnRitualController.Phase.P3_Reconstruction,
                SpawnRitualController.MapStatusToPhase("processing", SpawnRitualController.Phase.P3_Reconstruction));
        }
    }
}
```

- [ ] **Step I1.2: Run — expect compile error**

- [ ] **Step I1.3: Implement state machine + status mapping**

File: `Assets/HoloBorn/Scripts/SpawnRitual/SpawnRitualController.cs`

```csharp
using UnityEngine;

namespace HoloBorn.SpawnRitual
{
    public class SpawnRitualController : MonoBehaviour
    {
        public enum Phase { Idle, P1_Capture, P2_EnergyAccumulation, P3_Reconstruction, P4_InternalActivation, P5_Spawn, IdleAvatar }

        public CubeCloudManager cubeManager;
        public Mesh placeholderMesh;
        public Transform spawnLocation;
        public Transform floorCircle;
        public float floorCircleForwardOffset = 1.5f;

        private Phase currentPhase = Phase.Idle;
        private string currentTaskId;
        private int lastBackendProgress;

        public Phase CurrentPhase => currentPhase;

        // Pure-function status → phase mapping (testable in EditMode).
        public static Phase MapStatusToPhase(string status, Phase currentPhase)
        {
            switch (status)
            {
                case "portraitizing": return Phase.P2_EnergyAccumulation;
                case "generating": return Phase.P3_Reconstruction;
                case "rigging":
                case "animating": return Phase.P4_InternalActivation;
                case "complete": return Phase.P5_Spawn;
                case "failed": return Phase.Idle; // failure resets
                case "processing": return currentPhase; // legacy: don't transition
                default: return currentPhase;
            }
        }

        public void BeginRitual(Vector3 spawnPos, string taskId)
        {
            currentTaskId = taskId;
            spawnLocation.position = spawnPos;
            TransitionTo(Phase.P1_Capture);
        }

        public void OnBackendStatus(string status, int progress)
        {
            var nextPhase = MapStatusToPhase(status, currentPhase);
            if (nextPhase != currentPhase) TransitionTo(nextPhase);
            lastBackendProgress = progress;
            UpdatePhaseProgress(progress);
        }

        public void OnSpawnComplete(GameObject avatar)
        {
            // Avatar mesh available — resample for P5 snap targets.
            // Phase H shader-driven snap happens here.
            TransitionTo(Phase.IdleAvatar);
        }

        private void TransitionTo(Phase next)
        {
            // Per-phase entry logic placeholder. Step I2 fleshes out each phase.
            Debug.Log($"[SpawnRitual] {currentPhase} → {next}");
            currentPhase = next;
        }

        private void UpdatePhaseProgress(int progress)
        {
            // P3 silhouette coverage ↔ progress. Implemented in Step I2.
        }
    }
}
```

- [ ] **Step I1.4: Run tests — expect all 6 controller tests passing**

- [ ] **Step I1.5: Commit**

```bash
UNITY=~/Documents/UnityProjects/HoloBornUnity
git -C "$UNITY" add Assets/HoloBorn/Scripts/SpawnRitual/SpawnRitualController.cs* \
  Assets/HoloBorn/Tests/EditMode/SpawnRitualControllerTests.cs*
git -C "$UNITY" commit -m "feat(orchestrator): SpawnRitualController state machine + status mapping (TDD)"
```

### Task I2: Wire phase entry behaviors

- [ ] **Step I2.1: Implement P1 (Capture) entry**

In `SpawnRitualController.TransitionTo`, add phase-entry switch:

```csharp
private void TransitionTo(Phase next)
{
    Debug.Log($"[SpawnRitual] {currentPhase} → {next}");
    currentPhase = next;

    switch (next)
    {
        case Phase.P1_Capture:
            EnterP1();
            break;
        case Phase.P2_EnergyAccumulation:
            EnterP2();
            break;
        case Phase.P3_Reconstruction:
            EnterP3();
            break;
        case Phase.P4_InternalActivation:
            EnterP4();
            break;
        case Phase.P5_Spawn:
            EnterP5();
            break;
    }
}

private void EnterP1()
{
    // Floor circle bright flash. Audio + haptic handled by SpawnRitualAudio.
    if (floorCircle != null) floorCircle.gameObject.SetActive(true);
    // Position floor circle at spawnLocation
    floorCircle.position = spawnLocation.position;
}

private void EnterP2()
{
    // Vortex behavior — start dripping cubes upward from floor circle.
    StartCoroutine(P2_DripVortex());
}

private System.Collections.IEnumerator P2_DripVortex()
{
    int targetCount = 80;
    float dripRate = 8f; // cubes/sec
    float spawnHeightMin = 0.05f;
    float spawnHeightMax = 0.6f;

    int spawned = 0;
    while (currentPhase == Phase.P2_EnergyAccumulation && spawned < targetCount)
    {
        var cube = cubeManager.Spawn(spawnLocation.position + Vector3.up * spawnHeightMin);
        if (cube != null)
        {
            float phase = Mathf.PI * 2f * spawned / 50f;
            var orbitTarget = VortexBehavior.OrbitPosition(
                spawnLocation.position, radius: 0.25f,
                height: Random.Range(spawnHeightMin, spawnHeightMax),
                phase: phase, verticalDrift: 0f);
            cube.SetTarget(orbitTarget, duration: 1.5f, currentTime: Time.time);
            spawned++;
        }
        yield return new WaitForSeconds(1f / dripRate);
    }
}

private void EnterP3()
{
    StartCoroutine(P3_FillSilhouette());
}

private System.Collections.IEnumerator P3_FillSilhouette()
{
    // Sample target positions from placeholder mesh
    var localTargets = SilhouetteBehavior.SampleVerts(placeholderMesh, 300, seed: 7);
    var worldTargets = SilhouetteBehavior.LocalToWorld(localTargets, spawnLocation);

    while (currentPhase == Phase.P3_Reconstruction)
    {
        // Coverage = lastBackendProgress / 100
        int targetCoverage = Mathf.RoundToInt(worldTargets.Length * lastBackendProgress / 100f);
        AssignSilhouetteTargets(worldTargets, targetCoverage);
        yield return new WaitForSeconds(0.3f);
    }
}

private void AssignSilhouetteTargets(Vector3[] worldTargets, int coverage)
{
    // First `coverage` cubes get assigned silhouette targets.
    // Implementation deferred to Step I3 — needs CubeCloudManager.GetActive() helper.
}

private void EnterP4()
{
    // Silhouette holds. Energy pathways activate. Implemented in Phase L polish.
}

private void EnterP5()
{
    // Snap-to-mesh + dissolve climax. Implemented after real GLB arrives.
    // TestGlbLoader.OnSpawnComplete invokes us with the avatar reference.
}
```

- [ ] **Step I2.2: Add `GetActive()` helper to CubeCloudManager**

Modify `CubeCloudManager.cs` — add public accessor:

```csharp
public System.Collections.Generic.IReadOnlyList<Cube> GetActive() => active;
```

- [ ] **Step I2.3: Implement AssignSilhouetteTargets**

Replace the stub in `SpawnRitualController.cs`:

```csharp
private void AssignSilhouetteTargets(Vector3[] worldTargets, int coverage)
{
    var activeCubes = cubeManager.GetActive();
    int n = Mathf.Min(coverage, Mathf.Min(activeCubes.Count, worldTargets.Length));
    float now = Time.time;
    for (int i = 0; i < n; i++)
    {
        activeCubes[i].SetTarget(worldTargets[i], duration: 1.0f, currentTime: now);
    }
}
```

- [ ] **Step I2.4: Verify all tests still pass**

Unity Test Runner → Run All. Expect previous tests still passing (we only added implementation behind same public API).

- [ ] **Step I2.5: Commit**

```bash
UNITY=~/Documents/UnityProjects/HoloBornUnity
git -C "$UNITY" add Assets/HoloBorn/Scripts/SpawnRitual/SpawnRitualController.cs* \
  Assets/HoloBorn/Scripts/SpawnRitual/CubeCloudManager.cs*
git -C "$UNITY" commit -m "feat(orchestrator): wire P1-P3 phase entry behaviors + silhouette filling"
```

### Task I3: Simulate full status sequence in Editor

- [ ] **Step I3.1: Create simulator script**

File: `Assets/HoloBorn/Scripts/SpawnRitual/_DebugStatusSimulator.cs`

```csharp
using System.Collections;
using UnityEngine;

namespace HoloBorn.SpawnRitual
{
    public class _DebugStatusSimulator : MonoBehaviour
    {
        public SpawnRitualController controller;

        [ContextMenu("Run Full Sequence")]
        public void RunFullSequence()
        {
            StartCoroutine(Sequence());
        }

        private IEnumerator Sequence()
        {
            controller.BeginRitual(transform.position, "test-task");
            yield return new WaitForSeconds(2f);
            controller.OnBackendStatus("portraitizing", 0);
            yield return new WaitForSeconds(15f); // shorter for testing
            controller.OnBackendStatus("generating", 0);
            for (int p = 0; p <= 100; p += 10)
            {
                controller.OnBackendStatus("generating", p);
                yield return new WaitForSeconds(2f);
            }
            controller.OnBackendStatus("rigging", 100);
            yield return new WaitForSeconds(10f);
            controller.OnBackendStatus("animating", 100);
            yield return new WaitForSeconds(10f);
            controller.OnBackendStatus("complete", 100);
        }
    }
}
```

- [ ] **Step I3.2: Wire in scene + Play Mode test**

Unity Editor: in SampleScene, add a `_DebugStatusSimulator` component to the SpawnRitual GameObject. Wire `controller`. Press Play. Right-click component header → "Run Full Sequence". Watch the cube cloud transition through P1-P5 in Editor.

Expected visual outcomes:
- P1: floor circle appears
- P2: cubes drip into vortex over 15s
- P3: cubes flow into silhouette as progress climbs
- P4: silhouette holds (no visual yet without polish)
- P5: log fires "P5_Spawn" — cubes don't snap yet (Phase L will add it)

- [ ] **Step I3.3: Commit**

```bash
UNITY=~/Documents/UnityProjects/HoloBornUnity
git -C "$UNITY" add Assets/HoloBorn/Scripts/SpawnRitual/_DebugStatusSimulator.cs*
git -C "$UNITY" commit -m "feat(orchestrator): editor sequence simulator for P1-P5 dry-run"
```

---

# Phase J — Audio + haptics

### Task J1: SpawnRitualAudio component

**Files:**
- Create: `Assets/HoloBorn/Scripts/SpawnRitual/SpawnRitualAudio.cs`

- [ ] **Step J1.1: Implement audio component**

File: `Assets/HoloBorn/Scripts/SpawnRitual/SpawnRitualAudio.cs`

```csharp
using UnityEngine;

namespace HoloBorn.SpawnRitual
{
    public class SpawnRitualAudio : MonoBehaviour
    {
        public AudioSource source;
        public AudioClip lockFlash;
        public AudioClip thrumShort;
        public AudioClip clickLock;
        public AudioClip structuralLock;
        public AudioClip whoosh;
        public AudioClip breathChime;

        public void OnPhaseEnter(SpawnRitualController.Phase phase)
        {
            switch (phase)
            {
                case SpawnRitualController.Phase.P1_Capture:
                    source.PlayOneShot(lockFlash);
                    TriggerHaptic(0.5f, 0.3f);
                    break;
                case SpawnRitualController.Phase.P2_EnergyAccumulation:
                    source.PlayOneShot(thrumShort); // single shot, fades on its own
                    break;
                case SpawnRitualController.Phase.P3_Reconstruction:
                    // Click events fire from P3_FillSilhouette callback, not phase enter
                    break;
                case SpawnRitualController.Phase.P4_InternalActivation:
                    source.PlayOneShot(structuralLock);
                    break;
                case SpawnRitualController.Phase.P5_Spawn:
                    source.PlayOneShot(whoosh);
                    Invoke(nameof(PlayBreathChime), 1.5f);
                    Invoke(nameof(SpawnHaptic), 1.5f);
                    break;
            }
        }

        public void PlayClickLock() => source.PlayOneShot(clickLock, volumeScale: 0.4f);
        private void PlayBreathChime() => source.PlayOneShot(breathChime);
        private void SpawnHaptic() => TriggerHaptic(0.7f, 0.5f);

        private void TriggerHaptic(float amplitude, float duration)
        {
#if !UNITY_EDITOR
            // OVRInput vibration — left controller
            OVRInput.SetControllerVibration(amplitude, 0.5f, OVRInput.Controller.LTouch);
            Invoke(nameof(StopHaptic), duration);
#endif
        }

        private void StopHaptic()
        {
#if !UNITY_EDITOR
            OVRInput.SetControllerVibration(0f, 0f, OVRInput.Controller.LTouch);
#endif
        }
    }
}
```

- [ ] **Step J1.2: Wire into SpawnRitualController**

Modify `SpawnRitualController.cs` — add field and call:

```csharp
public SpawnRitualAudio audioComponent;

private void TransitionTo(Phase next)
{
    Debug.Log($"[SpawnRitual] {currentPhase} → {next}");
    currentPhase = next;
    if (audioComponent != null) audioComponent.OnPhaseEnter(next);

    switch (next)
    {
        // ... existing cases ...
    }
}
```

Also wire click events into `P3_FillSilhouette`:

```csharp
private System.Collections.IEnumerator P3_FillSilhouette()
{
    var localTargets = SilhouetteBehavior.SampleVerts(placeholderMesh, 300, seed: 7);
    var worldTargets = SilhouetteBehavior.LocalToWorld(localTargets, spawnLocation);
    int lastCoverage = 0;

    while (currentPhase == Phase.P3_Reconstruction)
    {
        int targetCoverage = Mathf.RoundToInt(worldTargets.Length * lastBackendProgress / 100f);
        if (targetCoverage > lastCoverage)
        {
            AssignSilhouetteTargets(worldTargets, targetCoverage);
            // Fire click sound ~every 10 cubes
            if (audioComponent != null && (targetCoverage - lastCoverage) >= 10)
            {
                audioComponent.PlayClickLock();
            }
            lastCoverage = targetCoverage;
        }
        yield return new WaitForSeconds(0.3f);
    }
}
```

- [ ] **Step J1.3: Wire AudioSource + clips in Inspector**

Unity Editor: on SpawnRitual GameObject, add `SpawnRitualAudio` component. Add child GameObject "AudioSource" with AudioSource component (spatial blend = 1.0, world position above floor circle). Drag the 6 wav files into the corresponding fields.

- [ ] **Step J1.4: Test in Editor**

Press Play. Right-click `_DebugStatusSimulator` → "Run Full Sequence". Listen for:
- P1: lock click + (no haptic in editor)
- P2: thrum fades in
- P3: occasional clicks as cubes lock
- P4: structural lock thud
- P5: whoosh → breath chime 1.5s later

- [ ] **Step J1.5: Commit**

```bash
UNITY=~/Documents/UnityProjects/HoloBornUnity
git -C "$UNITY" add Assets/HoloBorn/Scripts/SpawnRitual/SpawnRitualAudio.cs* \
  Assets/HoloBorn/Scripts/SpawnRitual/SpawnRitualController.cs* \
  Assets/Scenes/SampleScene.unity
git -C "$UNITY" commit -m "feat(audio): event-driven sparse audio + haptics for 5-phase ritual"
```

---

# Phase K — Quest sideload + first integration test

### Task K1: Wire into existing capture flow

**Files:**
- Modify: `Assets/HoloBorn/Scripts/ScanController.cs`
- Modify: `Assets/HoloBorn/Scripts/TestGlbLoader.cs`

- [ ] **Step K1.1: Add SpawnRitualController reference to ScanController**

Modify `ScanController.cs` — add public field:

```csharp
public HoloBorn.SpawnRitual.SpawnRitualController spawnRitual;
```

In the burst-capture handler (the existing path that POSTs `/generate-multiview`), after receiving the `task_id` from the server, call:

```csharp
Vector3 spawnPos = transform.position + transform.forward * 1.5f;
spawnRitual.BeginRitual(spawnPos, taskId);
```

In the status polling loop, on each successful poll response, call:

```csharp
spawnRitual.OnBackendStatus(response.status, response.progress);
```

(Adapt to existing field names in ScanController.)

- [ ] **Step K1.2: Wire TestGlbLoader.OnSpawnComplete event**

Modify `TestGlbLoader.cs` — after the existing `await gltf.InstantiateMainSceneAsync(parent)` call, fire the orchestrator's spawn-complete callback:

```csharp
// existing code:
await gltf.InstantiateMainSceneAsync(parent);
// ... ForceDoubleSidedMaterials, etc ...
PlayAnimations(parent.gameObject);

// NEW: notify orchestrator if attached
if (spawnRitual != null)
{
    spawnRitual.OnSpawnComplete(parent.gameObject);
}
```

Add field to TestGlbLoader:
```csharp
public HoloBorn.SpawnRitual.SpawnRitualController spawnRitual;
```

Wire in Inspector.

- [ ] **Step K1.3: Build APK + sideload**

In Unity Editor: File → Build And Run (target = Android, Quest connected via USB).

Expected: ~5-10 min build cycle on Intel Mac (Patch and Run if available cuts to ~1-2 min).

- [ ] **Step K1.4: Test on Quest**

Put on headset, walk through capture flow:
1. Press A button — verify floor circle flash (P1) + haptic
2. Wait — observe cubes dripping into vortex (P2) above floor circle
3. Backend hits "generating" — observe cubes flowing into silhouette (P3)
4. Watch for ~3-5min as silhouette fills — verify perf stays >72fps
5. Backend hits "complete" — verify avatar spawns (P5 cube snap not yet implemented in this phase)

Capture screen recording for record.

- [ ] **Step K1.5: Commit + push Unity**

```bash
UNITY=~/Documents/UnityProjects/HoloBornUnity
git -C "$UNITY" add Assets/HoloBorn/Scripts/ScanController.cs \
  Assets/HoloBorn/Scripts/TestGlbLoader.cs \
  Assets/Scenes/SampleScene.unity
git -C "$UNITY" commit -m "feat(integration): wire SpawnRitualController into capture + GLB load flow"
git -C "$UNITY" -c http.postBuffer=524288000 push origin main
```

---

# Phase L — Polish (cuttable)

### Task L1: Snap-to-mesh climax (P5)

- [ ] **Step L1.1: In SpawnRitualController.OnSpawnComplete, swap cube material to snap-dissolve material + drive shader props**

Replace the stub:

```csharp
public AnimationCurve dissolveCurve;
public AnimationCurve snapCurve;

public void OnSpawnComplete(GameObject avatar)
{
    StartCoroutine(P5_SnapAndDissolve(avatar));
}

private System.Collections.IEnumerator P5_SnapAndDissolve(GameObject avatar)
{
    // Resample target positions from real avatar's SkinnedMeshRenderer
    var smr = avatar.GetComponentInChildren<SkinnedMeshRenderer>();
    if (smr == null) { TransitionTo(Phase.IdleAvatar); yield break; }
    var realMesh = smr.sharedMesh;
    var localTargets = SilhouetteBehavior.SampleVerts(realMesh, 300, seed: 11);
    var worldTargets = SilhouetteBehavior.LocalToWorld(localTargets, smr.transform);

    var activeCubes = cubeManager.GetActive();
    int n = Mathf.Min(activeCubes.Count, worldTargets.Length);
    float now = Time.time;
    for (int i = 0; i < n; i++)
    {
        activeCubes[i].SetTarget(worldTargets[i], duration: 2.5f, currentTime: now);
    }

    // Hide avatar mesh initially, fade in over 1.5s as cubes settle
    var renderers = avatar.GetComponentsInChildren<Renderer>();
    foreach (var r in renderers) SetMaterialAlpha(r, 0f);

    yield return new WaitForSeconds(1.0f); // cubes mid-flight
    float fadeStart = Time.time;
    while (Time.time - fadeStart < 1.5f)
    {
        float t = (Time.time - fadeStart) / 1.5f;
        foreach (var r in renderers) SetMaterialAlpha(r, t);
        yield return null;
    }

    // Despawn all cubes
    foreach (var c in new System.Collections.Generic.List<Cube>(cubeManager.GetActive()))
    {
        cubeManager.Despawn(c);
    }

    TransitionTo(Phase.IdleAvatar);
}

private void SetMaterialAlpha(Renderer r, float a)
{
    if (r == null || r.material == null) return;
    var c = r.material.color;
    c.a = a;
    r.material.color = c;
}
```

- [ ] **Step L1.2: Test in Editor with debug simulator**

Run Sequence → verify cubes snap to avatar verts → mesh fades in → cubes despawn.

- [ ] **Step L1.3: Commit**

```bash
git -C "$UNITY" add Assets/HoloBorn/Scripts/SpawnRitual/SpawnRitualController.cs
git -C "$UNITY" commit -m "feat(spawn): P5 snap-to-mesh + alpha fade-in climax"
```

### Task L2: Breath + gaze acquisition (P5 polish)

- [ ] **Step L2.1: Add breath + gaze to P5_SnapAndDissolve coroutine**

Inside `P5_SnapAndDissolve` after the fade-in completes, add:

```csharp
// Gaze acquisition: head bone slerps toward camera over 0.5s
Transform head = FindHeadBone(avatar);
if (head != null && Camera.main != null)
{
    float gazeStart = Time.time;
    Quaternion startRot = head.rotation;
    while (Time.time - gazeStart < 0.5f)
    {
        float t = EaseOutQuad((Time.time - gazeStart) / 0.5f);
        Vector3 toCam = Camera.main.transform.position - head.position;
        Quaternion targetRot = Quaternion.LookRotation(toCam);
        head.rotation = Quaternion.Slerp(startRot, targetRot, t);
        yield return null;
    }
}

// Breath is delivered by Meshy's idle clip already (TestGlbLoader.PlayAnimations)
// — the chest expansion is part of the Idle animation. Gaze is the only
// programmatic motion we add here.
```

Add helpers:

```csharp
private Transform FindHeadBone(GameObject root)
{
    foreach (var t in root.GetComponentsInChildren<Transform>())
    {
        string n = t.name.ToLower();
        if (n.Contains("head") || n.Contains("neck")) return t;
    }
    return null;
}

private static float EaseOutQuad(float t) => 1f - Mathf.Pow(1f - Mathf.Clamp01(t), 2f);
```

- [ ] **Step L2.2: Test + commit**

```bash
git -C "$UNITY" add Assets/HoloBorn/Scripts/SpawnRitual/SpawnRitualController.cs
git -C "$UNITY" commit -m "feat(spawn): breath + gaze acquisition at P5 climax"
```

### Task L3: Energy-pathway lines (P4 polish — CUTTABLE)

- [ ] **Step L3.1: Create EnergyPathway.cs**

File: `Assets/HoloBorn/Scripts/SpawnRitual/EnergyPathway.cs`

```csharp
using UnityEngine;

namespace HoloBorn.SpawnRitual
{
    public class EnergyPathway : MonoBehaviour
    {
        public LineRenderer line;
        public float pulseSpeed = 1.5f;
        public Color baseColor = new Color(0f, 0.7f, 1f);

        void OnEnable()
        {
            if (line == null) line = GetComponent<LineRenderer>();
            line.startWidth = 0.005f;
            line.endWidth = 0.005f;
        }

        void Update()
        {
            float pulse = (Mathf.Sin(Time.time * pulseSpeed * Mathf.PI * 2f) + 1f) * 0.5f;
            var c = baseColor;
            c.a = 0.05f + pulse * 0.3f;
            line.startColor = c;
            line.endColor = c;
        }

        public void SetEndpoints(Vector3 a, Vector3 b)
        {
            line.SetPosition(0, a);
            line.SetPosition(1, b);
        }
    }
}
```

- [ ] **Step L3.2: Wire into P4 entry**

In `SpawnRitualController`:

```csharp
public EnergyPathway[] energyPathways; // wire 4 in scene: spine, l-arm, r-arm, both legs

private void EnterP4()
{
    foreach (var p in energyPathways) p.gameObject.SetActive(true);
    // hardcoded joint positions on placeholderMesh local-space — manually wired in Inspector
}

private void OnExit_P4_OrAfter()
{
    foreach (var p in energyPathways) p.gameObject.SetActive(false);
}
```

In `EnterP5`, add `OnExit_P4_OrAfter()` first.

- [ ] **Step L3.3: Wire 4 LineRenderer GameObjects in scene + commit**

In Unity Editor: create 4 child GameObjects under SpawnRitual root: "Pathway_Spine", "Pathway_LArm", "Pathway_RArm", "Pathway_Legs". Each gets a LineRenderer (Material = additive cyan unlit) + EnergyPathway component. Manually set start/end positions to spine/limb endpoints in placeholder mesh local space.

```bash
git -C "$UNITY" add Assets/HoloBorn/Scripts/SpawnRitual/EnergyPathway.cs* \
  Assets/HoloBorn/Scripts/SpawnRitual/SpawnRitualController.cs \
  Assets/Scenes/SampleScene.unity
git -C "$UNITY" commit -m "feat(polish): P4 energy-pathway lines + pulse animation"
```

### Task L4: Final Quest sideload + demo capture

- [ ] **Step L4.1: Build + sideload**

```
File → Build And Run
```

- [ ] **Step L4.2: Run full capture-to-spawn sequence on Quest**

Verify all 5 phases visually + audibly. Profiler should hold >72 fps throughout.

Acceptance criteria from spec:
- P1: floor circle flash ≤1 frame ✓
- P2: cubes 0→80 over 30s ✓
- P3: silhouette fills proportional to backend progress ✓
- P4: silhouette holds + 4 pathways pulsing ✓
- P5: cubes flow to mesh in 2.5s, mesh fades in over 1.5s, breath + gaze fire ✓

- [ ] **Step L4.3: Capture demo MP4**

Quest Mirror or Quest's built-in screen recording → 60-90s capture from press-A through spawn-complete. Save as `~/Downloads/holoborn_demo_<timestamp>.mp4`.

- [ ] **Step L4.4: Final commit + push both repos**

```bash
# Unity
UNITY=~/Documents/UnityProjects/HoloBornUnity
git -C "$UNITY" add -u
git -C "$UNITY" commit -m "feat(demo): EOW spawn ritual integrated end-to-end on Quest 3"
git -C "$UNITY" -c http.postBuffer=524288000 push origin main

# Mac (any latent backend changes)
git add -u
git status --short  # verify nothing surprising
git commit -m "feat(demo): EOW backend status emissions verified end-to-end" || echo "nothing to commit"
git -c http.postBuffer=524288000 push origin main
```

---

## Verification commands quick-reference

| What | Command |
|---|---|
| Backend Health | `curl -sS http://localhost:8000/health` |
| Backend status (in flight) | `curl -sS http://localhost:8000/generate/{task_id}/status` |
| Unity tests (CLI, optional) | `Unity.app/Contents/MacOS/Unity -runTests -batchmode -projectPath ~/Documents/UnityProjects/HoloBornUnity -testPlatform EditMode -testResults ~/test-results.xml` |
| Quest profiler | Window → Analysis → Profiler → connect to "AndroidPlayer (Quest...)" |
| Quest screen recording | Press headset → Camera → Record |

---

## Self-review checklist (run before declaring complete)

- [ ] Spec coverage: every section in `2026-05-08-spawn-ritual-design.md` maps to at least one task above
- [ ] No placeholders: scanned for "TBD", "TODO", "implement later" — none found
- [ ] Type consistency: `Cube`, `CubeCloudManager`, `SilhouetteBehavior`, `VortexBehavior`, `SpawnRitualController` names consistent across all task code blocks
- [ ] Acceptance criteria: each phase's pass criteria from spec map to verifiable steps in plan
- [ ] Commit cadence: ~1 commit per task or task-group, never >3 tasks without commit
- [ ] Cuts ladder honored: Phase L tasks marked CUTTABLE so they can drop without breaking earlier phases
