# Recovered C# Inventory — 2026-05-05

Web chat retrieval delivered partial-but-useful state. Saving here so it survives independently of the chat.

## Files in this folder

| File | Status | Use in rebuild |
|---|---|---|
| `CameraFeedDisplay.cs` | ✅ FULL verbatim | Drop directly into `Assets/HoloBorn/Scripts/`. Likely zero changes needed. |
| `TagAlongCanvas.cs` | ✅ FULL verbatim | Drop directly. Tunable via Inspector (`offset`, `followSpeed`). |
| `CanvasPositioner.cs` | ✅ FULL verbatim | Drop directly. Optional during dev for HUD placement. |
| `ScanController_PARTIAL.cs` | ⚠️ ~60% architectural | Use as scaffold. INVERT input mapping (A=burst, X=validate per shipped). Write missing method bodies from spec. |
| `AvatarSpawner_LEGACY.cs` | ⚠️ Pre-burst single-shot | Use ONLY for the `LoadAndInstantiateGLB` glTFast pattern. Endpoint is wrong (`/generate` not `/generate-multiview`). Don't ship. |

## Critical divergences from shipped APK (verified by user 2026-05-05)

1. **Input mapping** — keep recovered code's A button, add new X button path:
   - **A** (right controller, `primaryButton`) = 30-frame revolve scan ✅ recovered code is correct, ship it
   - **X** (left controller, `primaryButton`) = burst 5-frame same-position capture ⚠️ NOT in recovered code, must write fresh
   - **CLAUDE.md was wrong** about both buttons — disregard its input mapping section.

2. **Burst capture path doesn't exist** in recovered code. Must be added on X button:
   - On X press: capture frame, wait ~40ms, capture frame, repeat ×5
   - Build multipart with `frame_0..frame_4` + metadata `[{"index":0,"angle":0.0}, {"index":1,"angle":0.0}, ...]`
   - All angles = 0.0 (same position)
   - POST to `/generate-multiview` (same endpoint as 30-frame revolve, just N=5)
   - No `/validate-frame` call before burst (per user's memory of shipped behavior)

3. **AvatarSpawner is disabled at runtime** by ScanController.Start (button conflict).
   The shipped flow funnels everything through ScanController.

## Locked HTTP contract (multipart format — DO NOT change)

`POST /generate-multiview`:
- `frame_0` ... `frame_N` — each as `MultipartFormFileSection(name, jpegBytes, "frame_N.jpg", "image/jpeg")`
- `metadata` — `MultipartFormDataSection`, value = JSON string of `[{"index":0,"angle":0.0}, ...]`
- For burst: N=4, all angles = 0.0
- For revolve: N=29, angles cumulative ~12° apart

Mac backend receives this in `app/routes/generation.py` → `collect_frames` (which now correctly handles `starlette.UploadFile` after the 04-27 fix).

## Files that could not be recovered (must write fresh from spec)

- `BypassCertificate.cs` as standalone — it's nested at the bottom of recovered ScanController, just move it out
- `ScanController` method bodies: `Update`, `UpdateIdle`, `ValidateAndStartScan`, `StartScanAt`, `CaptureFrame`, `MarkNearestDot`, `DestroyScanGuides`, `PollAndDownloadGLB`, `SpawnPlaceholder`, `LoadAndInstantiateGLB`, `TestLoadGLB`, `SpawnGLBFromBytes`, the burst-capture coroutine
- `FrameSender.cs` final (post-six-bugs-fixed) — likely not needed since it was disabled in shipped scene anyway
- `AvatarSpawner` final post-rewrite — fold its features into ScanController
