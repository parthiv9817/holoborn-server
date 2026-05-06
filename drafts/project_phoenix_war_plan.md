# Project Phoenix — War Plan

**Date:** 2026-05-05 (Tuesday)
**North Star:** Reach feature-parity with the deployed APK on Quest (`com.UnityTechnologies.com.unity.template.urpblank`, label "HoloBorn9817") **by end of today.**
**Why today:** Tomorrow we start UI rework + animations on top of a working baseline. Today is for the baseline. EOW deadline (2026-05-08 to 10) covers the flashy layer.

## What "feature-parity with shipped APK" actually means

Five behaviors must work:

1. **Quest 3 boots the new APK in immersive mode** — passthrough on, hands tracked, comfortable HUD
2. **HUD shows live passthrough camera feed** + tag-alongs the head
3. **A-button revolve scan** — `/validate-frame` first; if good, AR floor guides spawn (ring + 30 dots + arrow), user revolves around subject capturing 30 frames at 12° intervals → multipart POST to `/generate-multiview` → poll → download GLB → spawn at floor level facing user
4. **X-button burst capture** — 5 JPEG frames same position → multipart POST to `/generate-multiview` (all angles=0.0) → poll → download GLB → spawn 1.5m in front of user, facing user
5. **Status text on HUD** — current state visible to user during the whole flow

If those 5 work end-to-end on Quest, we matched the shipped APK. UI flashy + animations are tomorrow's problem.

## Stack (locked from APK forensics — do not deviate)

| Component | Version |
|---|---|
| Unity | **6000.4.0f1** (Unity 6.4 LTS) |
| Renderer | URP (Universal Render Pipeline) |
| Scripting backend | IL2CPP |
| Graphics API | Vulkan, ARM64 only |
| XR backend | OpenXR + Meta Quest Support feature |
| Meta XR SDK | Meta XR All-in-One bundle (Building Blocks + MRUK + DepthAPI + Environment Depth) |
| GLB loader | glTFast |
| Input | New Input System (not legacy) |
| UI | TextMeshPro |
| JSON | Newtonsoft.Json |
| Min SDK | 32 |
| Target SDK | 34 |
| Permissions | `horizonos.permission.HEADSET_CAMERA`, `INTERNET`, `com.oculus.permission.USE_ANCHOR_API`, `com.oculus.permission.USE_SCENE` |

## Recovered assets we start from (saved to `drafts/recovered_csharp/`)

- ✅ `CameraFeedDisplay.cs` — full verbatim, ship as-is
- ✅ `TagAlongCanvas.cs` — full verbatim, ship as-is
- ✅ `CanvasPositioner.cs` — full verbatim, optional but useful during dev
- ⚠️ `ScanController_PARTIAL.cs` — ~60% scaffold. **Use as architecture reference, NOT verbatim.** Critical: input mapping is inverted, must rebuild per shipped (A=burst, X=validate).
- ⚠️ `AvatarSpawner_LEGACY.cs` — pre-burst version. Use only for `LoadAndInstantiateGLB` glTFast pattern.

## Locked HTTP contract (don't touch)

`POST /generate-multiview` multipart:
- `frame_0`…`frame_N` — each `MultipartFormFileSection(name, jpegBytes, "frame_N.jpg", "image/jpeg")`
- `metadata` — `MultipartFormDataSection`, value = JSON `[{"index":0,"angle":0.0}, ...]`
- Burst: N=4, all angles = 0.0
- Revolve: N=29, angles cumulative ~12° apart

Mac backend receives in `holoborn-server/app/routes/generation.py`. Already verified working 2026-05-04.

---

## Phases

### Phase 0 — Toolchain Bring-up (T+0 → T+45 min, mostly walk-away)

- [ ] Install **Unity Hub** from https://unity.com/download (`.dmg` → Applications)
- [ ] In Unity Hub → Installs → Install Editor → **Unity 6000.4.0f1** with these modules ticked:
  - Android Build Support
  - Android SDK & NDK Tools
  - OpenJDK
- [ ] Quest already detected via ADB (verified earlier — device `2G0YC5ZG0D01D7`)

**Exit gate:** `Unity Hub.app` opens, Unity 6000.4.0f1 listed under Installs, Android module present.

**Walk-away time during this phase:** ~30 min download. Use it to paste in Phase 1 scoping.

---

### Phase 1 — Project Skeleton (T+45 → T+75 min)

- [ ] Create new Unity 6 project at `~/Documents/UnityProjects/HoloBornUnity/` (already initialized as git repo with README + .gitignore)
- [ ] Template: **Universal 3D** (URP, NOT VR template — VR template defaults to OpenXR config that may need overrides)
- [ ] Open Project Settings:
  - **Player → Other Settings**: Scripting Backend = IL2CPP, ARM64 only (untick ARMv7)
  - **Player → Resolution and Presentation**: Default Orientation = Landscape Left
  - **Player → Identification**: Package Name = `com.holoborn.quest` (rename from default), Min SDK = 32, Target SDK = 34
  - **Player → Publishing Settings**: Custom Main Manifest = ON
  - **Graphics**: ensure URP asset wired, add `Sprites/Default` to Always Included Shaders (recovered code references it)
  - **Quality**: set Default Quality Level to a single low/medium tier for Android (delete others)
  - **XR Plug-in Management**: Install if not present, tick OpenXR for Android tab
  - **OpenXR (Android tab)**: enable Meta Quest Support feature, set render mode to Multi-View
- [ ] Package Manager → install:
  - **Meta XR All-in-One SDK** (Window → Asset Store / Package Manager → search Meta XR)
  - **glTFast** (search "glTFast" in Package Manager → installed Unity registry)
  - **Newtonsoft Json** (com.unity.nuget.newtonsoft-json)
  - **Input System** (likely already there with Unity 6 default)
  - **TextMeshPro** (already there with Unity 6 default)
- [ ] Configure AndroidManifest.xml (`Assets/Plugins/Android/AndroidManifest.xml`) with the 4 required permissions

**Exit gate:** Empty scene compiles + builds an APK with no errors. APK doesn't need to do anything yet — just validates toolchain.

**Smoke test (~15 min walk-away):** File → Build Settings → Android → Build APK. If it produces an APK, toolchain is good.

---

### Phase 2 — Drop in Recovered Files (T+75 → T+105 min)

- [ ] Create folder structure: `Assets/HoloBorn/Scripts/`, `Assets/HoloBorn/Prefabs/`, `Assets/HoloBorn/Materials/`
- [ ] Copy recovered files from `drafts/recovered_csharp/`:
  - `CameraFeedDisplay.cs` → `Assets/HoloBorn/Scripts/`
  - `TagAlongCanvas.cs` → `Assets/HoloBorn/Scripts/`
  - `CanvasPositioner.cs` → `Assets/HoloBorn/Scripts/`
  - `BypassCertificate.cs` (extract from bottom of `ScanController_PARTIAL.cs`) → `Assets/HoloBorn/Scripts/`
- [ ] Build the scene:
  - OVRCameraRig prefab (from Meta XR Building Blocks)
  - World-Space Canvas with TagAlongCanvas + CanvasPositioner components
  - RawImage child of Canvas for camera feed (wired to CameraFeedDisplay.displayImage)
  - Camera Manager GameObject with PassthroughCameraAccess component (Building Blocks block)
- [ ] First sideload test: build APK, sideload via `adb install -r`, put on headset → confirm passthrough works + HUD appears + camera feed visible

**Exit gate:** HUD visible in headset showing live passthrough feed. No code interaction yet, just rendering.

**This is the cheapest possible "is the toolchain working end-to-end" check. Don't skip it.**

---

### Phase 3 — ScanController Spine (T+105 → T+240 min, the meat of the day)

This is where the real work is. ~2-3 hours focused coding. Use `ScanController_PARTIAL.cs` as scaffold, write missing pieces from spec.

**Sub-bricks (write in this order so you can test incrementally):**

#### 3a — Skeleton (T+105 → T+125 min)
- [ ] Create `Assets/HoloBorn/Scripts/ScanController.cs`
- [ ] Copy class declaration, fields, enums, response classes from recovered partial
- [ ] Write `Start()` from scratch with **shipped input mapping** (user-verified 2026-05-05):
  ```
  revolveAction (A button — RightHand/primaryButton) → triggers 30-frame revolve scan
  burstAction   (X button — LeftHand/primaryButton)  → triggers 5-frame burst capture
  ```
- [ ] Write `Update()` state dispatcher: switch on `state` → call UpdateIdle / UpdateScanning

#### 3b — X-button burst capture path (T+125 → T+165 min) — THE NEW THING
- [ ] Write `IEnumerator BurstCapture()`:
  - Loop 5 times: capture frame → store in capturedFrames with angle=0.0 → wait ~40ms (`yield return new WaitForSeconds(0.04f)`)
  - Total burst duration ~200ms (matches noise vs motion analysis from earlier today — short enough to avoid motion blur)
  - When done, `StartCoroutine(UploadAndSpawn())` — reuse the recovered method
- [ ] Wire `burstAction.performed` → `StartCoroutine(BurstCapture())`
- [ ] Test: press X in headset, watch logcat — should see "5 frames captured, uploading…"

#### 3c — A-button revolve path with /validate-frame gate (T+165 → T+200 min)
- [ ] Write `IEnumerator ValidateAndStartScan()`:
  - Capture single frame
  - POST raw bytes to `/validate-frame` with Content-Type: image/jpeg, BypassCertificate, useHttpContinue=false
  - Parse `FramingResponse`
  - If `framing == "good"`: subject pos = head position + 2m forward, call `StartScanAt(subjectPos, initialFrame)`
  - If bad: red status, return to IDLE
- [ ] Reuse recovered `StartScanAt`, `UpdateScanning`, `SpawnScanGuides`, `UpdateArrowPosition`, `MarkNearestDot`, `DestroyScanGuides` (write missing bodies)
- [ ] Reuse recovered `UploadAndSpawn`

#### 3d — Polling + GLB load + spawn (T+200 → T+240 min)
- [ ] Write `IEnumerator PollAndDownloadGLB(string taskId)`:
  - Loop: GET `/generate/{taskId}/status`, parse, if complete → download GLB bytes → call SpawnGLBFromBytes
  - Backoff: 3s between polls, max 200 attempts (10 min cap matches Mac backend timeout)
  - Status updates to HUD on each poll
- [ ] Write `async void SpawnGLBFromBytes(byte[] glbData, string taskId)`:
  - GltfImport, LoadGltfBinary
  - Spawn at `subjectWorldPos` (revolve mode) or `headForward * 1.5m` (burst mode), floor-aligned
  - Auto-scale to 1.7m via bounds.size.y
  - Face the user (LookAt head, flatten Y)
  - Shader fallback for any null-shader materials (swap to URP/Lit)
- [ ] Write `void SpawnPlaceholder()` — instantiate `placeholderAvatarPrefab` at spawn position. Use any free Unity Asset Store mascot for now; flashy upgrade is tomorrow.

**Exit gate Phase 3:** Both A-button and X-button paths execute end-to-end on Quest, talking to the live Mac backend, spawning a GLB.

---

### Phase 4 — APK + On-Device Test (T+240 → T+300 min)

- [ ] Set Build Settings: scene added, Android target, Texture Compression = ASTC
- [ ] Build APK to `~/Documents/UnityProjects/HoloBornUnity/Builds/`
- [ ] `adb install -r` to Quest
- [ ] Run end-to-end with backend live:
  1. Mac backend up: `uvicorn app.main:app --reload`, Quest test mode = OFF in `.env`
  2. ngrok tunnel up: `ngrok http 8000`
  3. Set `serverUrl` in ScanController Inspector to ngrok URL, rebuild APK
  4. Sideload, run, press A button → wait ~7-9 min (cold start) → see avatar spawn
  5. Press X button → validate frame → revolve → see avatar spawn
- [ ] Capture screen recording from Quest while flow runs end-to-end (this is the demo MP4 for Vipin)

**Exit gate Phase 4:** Both buttons work on Quest with live backend. Screen recording captured.

---

### Phase 5 — Bug fixes from device test (T+300 → T+360 min, contingency)

Realistically things will break on first APK. Common issues to expect:

- **HEADSET_CAMERA permission missing** — add to AndroidManifest.xml manually (Unity sometimes drops it)
- **ngrok HTTPS rejected** — verify BypassCertificate is wired to all UnityWebRequests
- **Multipart upload timing out** — check `useHttpContinue=false` is set (this was a fix lost in the rewrite)
- **GPU pipeline stall on capture** — add `yield return null` after Graphics.Blit before ReadPixels
- **GLB renders pink/white** — Sprites/Default and URP/Lit shaders need to be in Always Included Shaders
- **Input dies after first press** — must use `InputAction` (New Input System), not `Input.GetButtonDown`
- **TextMeshPro essentials missing** — first-time prompt to import TMP essentials, accept it

Each fix is small and known. Budget 1 hour; cap at 1.5 hours.

---

## Stop / abort triggers

If at any phase exit gate we're 30+ min behind plan, stop and reassess. Specific triggers:

- **Phase 0 fails (Unity Hub install issue)** — log it, fall back to "tomorrow we install fresh"
- **Phase 1 fails (Android build settings)** — high signal. Check NDK + JDK paths. If still fails after 30 min, this Mac may have the same toolchain rot UE5 hit.
- **Phase 2 fails (HUD/passthrough doesn't render)** — likely XR Plug-in Management or OpenXR config. Stop and screenshot Project Settings, debug.
- **Phase 3c fails (multipart upload error)** — backend received frames before (verified 05-04), so issue is Quest-side. Diff against `holoborn-server/app/routes/generation.py` field name expectations.
- **Phase 4 fails (GLB doesn't spawn)** — most likely glTFast version mismatch or shader stripping. Both have known fixes.

## Today's success measure

- ✅ Lower bound: APK boots immersive on Quest, HUD shows passthrough, A button captures and shows status (even if backend pipeline isn't wired yet) — that's "Phase 2 done, the rest is software."
- 🎯 Target: A button burst → backend → GLB spawns, X button validate → revolve → backend → GLB spawns. Recorded clip sent to Vipin.
- 🚀 Stretch: Both work AND status text is clean AND placeholder mascot shows during gen.

## Tomorrow's preview (Wed)

UI flashy pass — TextMeshPro fonts, particle effects, controller-tracked button highlights, sound on capture/spawn, animated state transitions on the HUD. Touches assets, not architecture. Should be 4-6 hours focused.

## Thursday's preview

GLB animations — Unity Animator, idle + 1-2 expressive animations, can come from Mixamo (free) or any premade humanoid rig. Maps to glTFast spawn flow.

## Friday's preview

Polish + recorded demo MP4 + send to Vipin = ship.

## Lock-in to remember while building

- **Push to remote at EOD** (per user directive — discipline gesture cadence is daily not per-commit on this sprint)
- **Brick by brick** — when blocked on any sub-brick > 30 min, name it explicitly and decide stop vs continue
- **Web search EXACT errors before AI second-opinions** (mistakes-file lesson, twice-learned)
- **Founder updates every evening** with concrete progress not "I worked hard"
- **Use shipped APK input mapping** (A=revolve, X=burst — user-verified 2026-05-05). CLAUDE.md was wrong; disregard its mapping.
- **The HTTP contract is the only thing that's non-negotiable** — `frame_0..frame_N` field names, `metadata` JSON shape, both sides must agree byte-for-byte
