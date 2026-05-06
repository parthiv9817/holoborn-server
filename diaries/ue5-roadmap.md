# HoloBorn — UE5 Migration Roadmap

**Date:** 2026-04-28
**Decision:** Migrate Quest client from Unity to Unreal Engine 5. Founder-aligned. Code is already lost.
**Operating principle:** Minimal scene first. If UE5 → Quest 3 → GLB load works, the rest is just rebuilding what we already built in Unity.
**Backend:** Already rebuilt and tested in this repo (`holoborn-server`). Engine-agnostic. Not blocked on this.

---

## North Star

A Quest 3 standalone build, made in UE5, that:

1. Boots on the headset.
2. Receives a `.glb` file from this Mac backend over HTTP.
3. Loads it at runtime via glTFRuntime.
4. Spawns it in front of the user with PBR materials intact.

That is the entire MVP. Nothing else. If this works, everything else is wiring known patterns into a new engine — same problems we already solved in Unity, just with a different IDE.

If this does NOT work, we fall back to Unity in <1 day of pivoting. No sunk-cost spiral.

---

## Phase 0 — Tooling Install (Day 0, ~3-4 hours)

Pure setup. No engine learning yet. Goal: be able to compile *anything* to Quest 3 from UE5.

**Pre-flight verification (do these first, ~30 min, save an 80GB wasted download):**
- [ ] Quest 3 firmware updated to latest (avoids `INSTALL_FAILED_OLDER_SDK`)
- [ ] Confirm glTFRuntime status on Fab (paid plugin) — decide pay or build from source (`github.com/rdeioris/glTFRuntime`, last release 2026-01-13)
- [ ] At least 100GB free disk for UE + Android target + build cache
- [ ] Apple ID signed in on Mac

**Pinned versions (DO NOT free-hand — NDK mismatch is the #1 reason Android builds fail):**
- UE **5.6.1**
- NDK **27.2.12479018**
- JDK **OpenJDK 21.0.3**
- Android Studio **Koala 2024.1.2**
- SDK platform **android-34**
- build-tools **35.0.1**
- MetaXR plugin **v78** (matches 5.6.1)
- Min SDK **29**, Target SDK **34** (Quest store rules)

**Install order:**
- [ ] Install Epic Games Launcher
- [ ] Install Unreal Engine 5.6.1 (Library tab → tick "Target Platforms: Android" — ~70GB)
- [ ] Install Xcode + Command Line Tools (`xcode-select --install`)
- [ ] Install Android Studio Koala 2024.1.2
- [ ] Run `UE_5.6/Engine/Extras/Android/SetupAndroid.command` — installs pinned NDK 27.2.12479018, SDK android-34, build-tools 35.0.1, JDK 21.0.3
- [ ] Set env vars in `~/.zshrc`:
  - `ANDROID_HOME=$HOME/Library/Android/sdk`
  - `JAVA_HOME=<Android Studio>/Contents/jbr/Contents/Home`
  - `NDKROOT=$ANDROID_HOME/ndk/27.2.12479018`
- [ ] Enable Developer Mode on Quest 3 via Meta Horizon mobile app
- [ ] Install Meta Quest Developer Hub (macOS)
- [ ] Accept ADB authorization on the headset
- [ ] Install MetaXR plugin v78 from Fab (listing `24fc0e7b-56d2-4421-a794-500fd51985c8`) — install to `Engine/Plugins/Marketplace/`, NEVER `Engine/Plugins/`
- [ ] Verify `adb devices` sees the headset

**Fallback:** If 5.6.1 trips on something specific, drop to UE 5.5.x with the same MetaXR v78 pairing. Both are Meta-tested.

**Exit gate:** `adb devices` shows the Quest 3 unlocked.

---

## Phase 1 — Hello Cube on Quest 3 (Day 1, ~6-8 hours — first APK package alone is 45-90 min)

NO HoloBorn code yet. Just prove UE5 → Quest 3 toolchain works.

- [ ] New UE5 project: **Blank C++ template** (or VR Template), Mobile/Tablet target, Scalable, no starter content
- [ ] Disable legacy OculusVR plugin in Edit → Plugins (if present)
- [ ] Verify MetaXR v78 enabled
- [ ] Project Settings → Rendering → **Mobile Forward Renderer**, **Mobile HDR OFF**, MSAA 4x
- [ ] Project Settings → Platforms → Android → Min SDK 29, Target SDK 34
- [ ] Mac-specific: add to `Config/Mac/MacEngine.ini` to prevent VR Preview Metal RHI crash:
  - `r.ForwardShading=False`
  - `vr.InstancedStereo=False`
  - `vr.MobileMultiView=False`
  - (These only affect editor preview; Android build still uses Mobile Forward + Multi-View)
- [ ] **Don't develop in PIE on Mac.** Deploy to device.
- [ ] Drop one cube + a directional light. That's it.
- [ ] Set VR Default Pawn or MetaXR Pawn as GameMode default
- [ ] Build: Platforms → Android → Package Project (ASTC texture format)
- [ ] **First package: 45-90 minutes on this Mac. Start it and walk away.** Don't sit watching the bar.
- [ ] Sideload via `adb install` or Meta Quest Developer Hub

**Exit gate:** Wear the headset, launch, see the cube. If we see a cube, the rest is a software problem.

**If this fails:** STOP. Diagnose. This is the cheapest possible failure point. If it's still failing after 2 days, re-evaluate the Mac (not stubbornness, evidence).

---

## Phase 2 — glTFRuntime GLB Load (Days 2-3) — THE LOAD-BEARING SPIKE

This is the entire reason we're allowed to migrate. Every UE5-vs-Unity debate agent flagged this as the go/no-go. We test it in isolation, with no other moving parts, before we commit any further weeks.

- [ ] Add **glTFRuntime** plugin (Roberto De Ioris's repo on GitHub or Marketplace)
- [ ] Confirm plugin is enabled for the Android build target
- [ ] Pick a real GLB to test with. Three sources:
  - The MP4-evidence avatar — re-run a portraitize+TRELLIS pass against a saved frame once OpenAI credits land
  - Any of the 25-35MB GLBs from previous testing (check `results/avatars/` in this repo if they survived; otherwise generate one)
  - In the meantime: Khronos sample GLBs (DamagedHelmet etc.) just to prove the plugin path
- [ ] Place the GLB locally in the project's `Content/GLBs/` for the spike (network loading comes in Phase 3)
- [ ] Blueprint or C++: on BeginPlay, load the GLB via `glTFRuntimeAsset::LoadFromFilename`, spawn the resulting actor 2 meters in front of the camera at floor height
- [ ] Build to Quest, sideload, verify

**Exit gate — ALL must pass:**

1. **Loads without crash on Quest 3 device build** (not editor — device only counts).
2. **PBR materials survive** — base color, metallic/roughness, normal map all visible. The avatar isn't grey or pink-checkerboard.
3. **No OOM on a real ~30MB GLB.** Use Meta Quest Developer Hub to watch peak heap during load. Quest gives ~3GB to the app; load must stay well under.
4. **Reload 3 times in one session without leak.** Spawn → destroy → spawn → destroy → spawn → destroy. If memory climbs monotonically, the plugin leaks and Phase 3+ is dangerous.

**If all 4 pass:** UE5 migration is officially go. Continue.
**If any fail:** Stop the migration. Open `diaries/2026-04-XX.md` with the exact failure mode, fall back to Unity rebuild. ~1 day lost, not 3 weeks.

---

## Phase 3 — HTTP Download from Mac Backend (Day 4)

GLB is now coming from the network, not local content. This proves the integration path with this repo.

- [ ] Start `holoborn-server` locally + ngrok tunnel
- [ ] In UE5, use `FHttpModule` (C++) or HTTP Blueprint nodes to GET `https://<ngrok>/avatars/<known-task-id>.glb`
- [ ] Save bytes to a temp file in `FPaths::ProjectSavedDir()`
- [ ] Pass the temp file path into the Phase 2 glTFRuntime loader
- [ ] Verify `glTF` magic bytes on the downloaded file before loading (defensive)
- [ ] Add HTTPS bypass for ngrok's self-signed-ish tunnel (UE5 equivalent of Unity's `BypassCertificate`) — usually `bUseHttps=true` is enough since ngrok serves valid certs, but document the fallback if cert pinning trips

**Exit gate:** Press a button on the Quest controller → app downloads a hardcoded GLB from ngrok → renders in front of user. Same UX as Phase 2 but the asset comes from this Mac.

---

## Phase 4 — Passthrough + Spatial Anchoring (Days 5-6)

Now we make it actually MR, not just VR.

- [ ] Enable Meta XR passthrough in project settings (passthrough layer)
- [ ] Verify scene background is the room, not a skybox
- [ ] Spawn the GLB at floor level using the Quest's floor estimate (Meta XR Floor or scene-mesh API)
- [ ] Avatar faces the user on spawn (orient toward HMD forward vector at spawn time)
- [ ] Optional: spatial anchor so the avatar stays put as the user walks around (Meta XR Anchors)

**Exit gate:** Avatar appears in your passthrough view, anchored to the floor, and stays there as you walk around it. Reproduces the "10s mark" from the MP4 evidence.

---

## Phase 5 — Capture & Backend Round-Trip (Days 7-9)

This is the real product loop. Up to here, GLBs have been pre-generated. Now the headset captures and triggers generation.

**PCA decision (resolved):** Meta's Passthrough Camera API is shippable but UE5 support is via tark146's `UnrealAndroidCamera2Plugin` (MIT, locked at 320×240 in v1.0, slight orange tint). **For our MVP, PCA is NOT needed** — Quest captures JPEGs via system camera capture / render targets, uploads to this Mac backend over HTTP. Keep PCA out of v1 entirely. Phase 7+ territory if ever.

- [ ] **A button burst capture** — capture 5 JPEG frames rapidly from same position (render target / screen capture, not PCA)
- [ ] **HTTP multipart POST** to `/generate-multiview` — frame_0..frame_4 + metadata JSON
- [ ] Architecture: **one small C++ class** for the multipart POST (~50 lines, lift Epic's "upload image via HTTP POST C++" tutorial verbatim). Expose to Blueprint via `UFUNCTION(BlueprintCallable)`. Everything else stays in Blueprint.
- [ ] Receive `task_id` back, store it
- [ ] **Polling loop** in Blueprint — every 3 seconds GET `/generate/{task_id}/status` until `status == "complete"`
- [ ] On complete: GET the `glb_url`, save, spawn via Phase 3 path

**Exit gate:** Press A on the Quest controller → captures 5 frames → uploads → polls → 3-5 minutes later → avatar appears in front of user. Real end-to-end loop, real RunPod call, real GLB. This is the demo.

---

## Phase 6 — HUD, Debug Overlay, Floor Reticle (Days 10-11)

The polish pass that matches what the MP4 evidence shows.

- [ ] Floating HUD canvas with passthrough camera feed (TagAlong behavior — follows head with smooth lerp)
- [ ] Debug overlay text ("Avatar spawned!", task_id, status messages) — match the green debug text from the Unity build
- [ ] Floor reticle ring (the white concentric ring visible in MP4 frame_02)
- [ ] State machine: idle → capturing → uploading → polling → spawning → done
- [ ] Placeholder mascot avatar during generation (matches the cartoon mascot from the MP4)

**Exit gate:** Visual parity with the April 11 MP4 evidence. Same affordances, same debug surface, same UX.

---

## Phase 7 — Revolve Capture, X Button (Days 12-14, optional for MVP)

The 30-frame revolve capture for future multi-image TRELLIS modes. Backend already supports this. Skip if MVP demo doesn't need it.

- [ ] X button → frame validation via `/validate-frame`
- [ ] If good: AR scan guide ring on the floor with 30 dots at 12° intervals
- [ ] Direction arrow guides the user's revolution
- [ ] Capture frame at each dot as user crosses it
- [ ] Upload all 30 + metadata JSON with angles

**Exit gate:** Revolve capture works. Optional — skip if A-button burst is sufficient for the demo.

---

## Phase 8 — Demo Hardening (Days 15-16)

Everything that makes the difference between "works on my machine" and "works in front of Vipin / an investor."

- [ ] Reserved ngrok domain (so the headset doesn't need a config push every restart)
- [ ] App icon + splash screen
- [ ] Error states surfaced visibly (RunPod failed, OpenAI billing hit, network down)
- [ ] APK signed for distribution
- [ ] Sideload-and-go on a fresh headset in <2 minutes
- [ ] Re-record the Phase-1 MP4 evidence with the UE5 build

**Exit gate:** Hand the headset to someone who's never seen it, give them 30 seconds of context, they run the loop end-to-end without you touching a keyboard.

---

## Total Budget

| Phase | Days | Cumulative |
|-------|------|-----------:|
| 0 — Tooling | 0.5 | 0.5 |
| 1 — Hello Cube | 0.5-1 | 1.5 |
| 2 — **glTFRuntime spike (GO/NO-GO)** | 1-2 | 3.5 |
| 3 — HTTP download | 1 | 4.5 |
| 4 — Passthrough + anchoring | 1-2 | 6.5 |
| 5 — Capture + round-trip | 2-3 | 9.5 |
| 6 — HUD + polish | 1-2 | 11.5 |
| 7 — Revolve (optional) | 2-3 | 14.5 |
| 8 — Demo hardening | 1-2 | 16.5 |

**Realistic total: 2.5 to 3.5 weeks of solo work** assuming Phase 2 passes. If Phase 2 fails, ~3 days lost to Phases 0-2 → fall back to Unity.

---

## Rules for This Build (carried from Phase-1 backend)

1. Git commit after every working feature. **Push to remote same session.** No exceptions. Lesson written in blood last week.
2. Test each phase on the Quest device before moving to the next. Editor success ≠ device success.
3. Keep the project hierarchy obvious. C++ for systems, Blueprint for orchestration. Don't fight the engine.
4. After every phase, write 5 lines into `diaries/YYYY-MM-DD.md`: what worked, what broke, what's next. Same diary discipline that saved us last week.
5. **Do not touch this `holoborn-server` repo for UE5 work.** UE5 lives in its own repo (`holoborn-quest-ue5` or similar). Backend stays stable.
6. **If Phase 2 fails, the migration is over.** No "let me try one more thing." Fall back to Unity, lose 3 days, ship.

---

## What's Different from the Unity Week We Already Crushed

We learned Unity in a week and spent the rest of the time on serverless. This is the same shape:

- Phase 0-1 = "install the thing, hello world" (we did this in Unity in ~half a day)
- Phase 2 = the one critical unknown (Unity equivalent: glTFast worked first try; UE5 equivalent: needs the spike)
- Phase 3-6 = just translation work (we already know what to build, we're typing it in a new language)

The only genuine unknown is Phase 2. Everything else is execution.

---

## Things That Will Bite Us (Predictions, ranked by probability × cost)

Writing these down so when they happen we don't panic — we just open this file. Sourced from the 2026-04-28 research pass.

1. **Intel Mac Android packaging will eat days.** ~90% probability, 1-3 days. The single migration-killer if it cascades. Mitigation: pin versions exactly (Phase 0 list). If still broken after 3 days → re-evaluate hardware (Apple Silicon / Windows).
2. **Editor on Iris Plus 1536MB will run at 8-20 fps.** 100%, accept it. `t.maxfps 20`, scalability "Low," develop on device not in PIE.
3. **First-APK `INSTALL_FAILED_OLDER_SDK` or instant crash.** ~70%, 0.5-2 days. Update Quest firmware first; pin Min SDK 29 / Target 34 / NDK 27.2.
4. **Mac VR Preview crashes (Metal RHI).** ~80%, hours. `Config/Mac/MacEngine.ini` overrides (Phase 1 list). Don't develop in PIE on Mac.
5. **glTFRuntime texture memory on a 25-35MB GLB.** ~40%, 1 day. Runtime-loaded textures bypass UE's compression and arrive raw RGBA. Mitigation: downscale textures to 1K on RunPod before encoding GLB; verify empirically in Phase 2.
6. **C++ HTTP client write.** 100%, 1-2 days. Lift Epic's "upload image via HTTP POST C++" tutorial verbatim. ~50 lines.
7. **MetaXR plugin install location confusion.** ~40%, hours. Always `Engine/Plugins/Marketplace/`, never `Engine/Plugins/`.
8. **UE 5.6.1 Quest 3 quirks (specific known regressions):** Mobile HDR + TonemapSubpass = black screen on 5.5 (we disable Mobile HDR anyway). Manifest duplicate-line errors after toggling plugins (full clean rebuild fixes).
9. **First C++ cold compile** 60-120s, incremental 15-40s on this i7. Live coding will be slow but usable.
10. **Cumulative iteration speed loss.** Hours per day. Borrow a Windows / Apple Silicon machine for packaging-heavy days if anyone has one.

---

## Open Questions for Vipin

Park these for next sync, don't block on them:

1. Is Vision Pro on the 6-12 month roadmap or 18+? (Determines how hard we lean into UE5-specific features vs keeping it portable.)
2. Is "built on Unreal Engine" a fundraising angle he's actively using? (Tells us how much polish/branding to put on the UE5 build vs the Unity one.)
3. Hard demo dates? Today's plan assumes none — if one shows up, MVP is Phase 4 (download a pre-cooked GLB and put it in passthrough), not Phase 5+.

---

## Closing

We learned Unity in a week. We can learn UE5 in a week. The serverless side is already solved — backend is stable, RunPod is wired, OpenAI just needs credits. UE5 is the last unknown, and Phase 2 either retires it in 2 days or sends us back to Unity in 3.

Either way, we ship.
