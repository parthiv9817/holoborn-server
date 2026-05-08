# Meshy API Research — Rigging + Animation Pipeline for HoloBorn

Researched 2026-05-07 in support of locking in Meshy as the auto-rigging + animation step in the HoloBorn pipeline.

## TL;DR

- **API plumbing fully exists.** Public, documented Auto-Rigging & Animation API at `https://api.meshy.ai/openapi/v1/...`, launched 2025-05-15. Async-poll/SSE-stream endpoints with Bearer auth.
- **API access requires a paid plan.** Free tier is web-UI only. Cheapest API tier is **Pro at $20/mo (1,000 credits)**; Studio is $60/mo (4,000 credits). A free `msy_dummy_api_key_for_test_mode_12345678` exists for development against mock responses, no real generation.
- **Cost per HoloBorn avatar (rig + 1 animation) = 8 credits.** Auto-rigging is 5 credits, each animation bake is 3 credits. On Pro that's ~125 avatars/mo. Per-avatar dollar cost ≈ **$0.16 on Pro / $0.12 on Studio**.
- **Built-in animation library is API-accessible** via integer `action_id` on `POST /openapi/v1/animations`. Catalog has ~588 entries (IDs 0–587) covering DailyActions, WalkAndRun, Fighting, BodyMovements, Dancing.
- **3-day asset retention.** All output URLs auto-expire after 3 days for non-Enterprise. We MUST mirror to our own S3 immediately on `SUCCEEDED`.
- **Critical constraints.** Humanoid only, max 300k faces, character must face +Z axis. T-pose OR A-pose accepted (matches our V3 portraitizer output).
- **Animation ≠ rigging.** Two sequential calls. Rigging produces a `rig_task_id`, which is required input to the animation call. Bonus: rigging response includes free `walking_*` and `running_*` URLs — useful for cheap demos without spending the 3 animation credits.
- **Webhooks supported** (max 5/account, HTTPS-only). SSE streaming also available at `/:id/stream`.

---

## 1. Rigging API

### Endpoint
- **Create:** `POST https://api.meshy.ai/openapi/v1/rigging`
- **Get:** `GET https://api.meshy.ai/openapi/v1/rigging/:id`
- **Delete:** `DELETE https://api.meshy.ai/openapi/v1/rigging/:id`
- **Stream (SSE):** `GET https://api.meshy.ai/openapi/v1/rigging/:id/stream`

### Request

Headers:
```
Authorization: Bearer ${MESHY_API_KEY}
Content-Type: application/json
```

Body:
| Param | Type | Required | Notes |
|---|---|---|---|
| `input_task_id` | string | one of these two | "The input task that needs to be rigged. We currently support textured humanoid models." Refers to a prior Meshy-generated task. Takes priority if both provided. |
| `model_url` | string | one of these two | "3D model for Meshy to rig via a publicly accessible URL or Data URI...support textured humanoid GLB files (.glb format)." **This is the path we'll use** — we feed RunPod's GLB via a public URL or data-URI. |
| `height_meters` | number | optional | Default 1.7. Approximate character height. |
| `texture_image_url` | string | optional | UV-unwrapped base color texture (.png). |

### Response (Create)
```json
{ "result": "task_id_string" }
```

### Task Object (on retrieve)
| Property | Type |
|---|---|
| `id` | string |
| `type` | string |
| `status` | `PENDING` \| `IN_PROGRESS` \| `SUCCEEDED` \| `FAILED` \| `CANCELED` |
| `progress` | int 0-100 |
| `created_at` / `started_at` / `finished_at` / `expires_at` | ms epoch |
| `task_error` | object |
| `consumed_credits` | int |
| `preceding_tasks` | int (queue position) |
| `result` | object (on `SUCCEEDED`) |

`result` contains:
- `rigged_character_glb_url` — added 2025-10-20, this is what we want for Quest/glTFast
- `rigged_character_fbx_url`
- `basic_animations` — sub-object with `walking_glb_url`, `walking_fbx_url`, `walking_armature_glb_url`, `running_glb_url`, `running_fbx_url`, `running_armature_glb_url`. **Free with rigging — no extra credits.**

### Constraints
- **Polygon limit:** "models with more than 300,000 faces are not supported for rigging" — use Remesh API to reduce first if exceeded.
- **Orientation:** "character's face must point toward the +Z axis (the standard glTF forward direction)."
- **Mesh:** must be textured; untextured meshes fail.
- **Topology:** "humanoid assets with unclear limb and body structure" rejected. Programmatic rigging "currently only works well with standard humanoid (bipedal) assets" — quadrupeds are UI-only despite marketing claims.
- **Pose:** T-pose or A-pose accepted.

### Pricing
- **5 credits** per task.

### Failure modes / error codes
| Code | Scenario |
|---|---|
| 400 | Missing required params or invalid references |
| 401 | Auth failure |
| 402 | Insufficient credits |
| 404 | Task not found |
| 429 | Rate limit (`RateLimitExceeded`) or concurrency limit (`NoMoreConcurrentTasks`) |

Task-level failures populate `task_error.message` and set `status = FAILED`.

---

## 2. Animation API

### Endpoint(s)
- **Create:** `POST https://api.meshy.ai/openapi/v1/animations`
- **Get:** `GET https://api.meshy.ai/openapi/v1/animations/:id`
- **Delete:** `DELETE https://api.meshy.ai/openapi/v1/animations/:id`
- **Stream (SSE):** `GET https://api.meshy.ai/openapi/v1/animations/:id/stream`

### Request

Headers: same as rigging.

Body:
| Param | Type | Required | Notes |
|---|---|---|---|
| `rig_task_id` | string | yes | "The id of a successfully completed rigging task" |
| `action_id` | integer | yes | Animation library entry — see below |
| `post_process` | object | no | Optional post-bake mutation |

`post_process` sub-fields:
| Field | Type | Default | Allowed |
|---|---|---|---|
| `operation_type` | string | — | `change_fps` \| `fbx2usdz` \| `extract_armature` |
| `fps` | int | 30 | 24 / 25 / 30 / 60 (only when `operation_type = change_fps`) |

### Response (Create)
```json
{ "result": "018c425b-b2c6-727e-d333-3c1887i9h791" }
```

### Animation Task Object — `result` URLs on `SUCCEEDED`
- `animation_glb_url` ← **what HoloBorn needs**, glTF-standard animation tracks
- `animation_fbx_url`
- `processed_usdz_url` (if post_process = fbx2usdz)
- `processed_armature_fbx_url` (if extract_armature)
- `processed_animation_fps_fbx_url` (if change_fps)

### Built-in animation library — full list available via API
- **Quantity:** ~588 animations (action_ids 0–587, with some gaps). Categories: DailyActions, WalkAndRun, Fighting, BodyMovements, Dancing, plus subcategories.
- **API-callable:** All catalog entries are callable via `action_id`. Same library shown in Meshy's web Animate panel.
- **Sample IDs (from doc fetch):**
  - 0 = `Idle` (DailyActions)
  - 1 = `Walking_Woman` (WalkAndRun)
  - 2 = `Alert` (DailyActions)
  - 3 = `Arise` (DailyActions)
  - 4 = `Attack` (Fighting)
  - 8 = `Dead` (Fighting)
  - 16 = `RunFast` (WalkAndRun)
  - 92 = `Reaping_Swing`
- **Catalog endpoint:** none (no programmatic catalog query). The full table lives only at `https://docs.meshy.ai/en/api/animation-library`. **Action item: pull the page directly with `curl` and parse to a local JSON enum** so action_id constants live in our codebase.

### Can rigging + animation be combined?
**No.** Two sequential API calls. Animation call REQUIRES `rig_task_id` from a prior `SUCCEEDED` rigging task. No unified endpoint.

**However** the rigging endpoint returns `basic_animations.walking_glb_url` and `basic_animations.running_glb_url` as bonus output (no animation credits spent). For a minimum-viable demo we could use those without ever calling the animation endpoint.

### Multiple animations per GLB
Not supported in one call. Each `POST /openapi/v1/animations` bakes ONE `action_id` into the output GLB. To deliver an avatar with `idle + walk + dance` baked into a single Animator, we'd need to either:
1. Make N separate API calls (N × 3 credits), download N GLBs, and merge animation tracks client-side in Unity.
2. Or play one animation per GLB and switch GLBs at runtime (not what we want).

The docs do not mention multi-clip output.

### Custom animation upload?
**Not documented.** No endpoint for uploading a custom FBX animation and having Meshy retarget it to a rigged GLB. The 588-entry library is the only animation source. The "alive avatars" path is constrained to whatever's in their library — no custom mocap retargeting via API.

### Output GLB format
Standard glTF 2.0 with embedded skeletal animation tracks. Compatible with Unity glTFast (validated empirically today via web UI). Default 30 FPS, modifiable via `post_process.change_fps`.

### Pricing
- **3 credits** per animation task.

### Failure modes
Same error code table as rigging (400/401/402/404/429).

---

## 3. Pricing tiers / API access matrix

| Tier | USD/mo | USD/yr | Credits/mo | API Access | Rate Limit | Concurrency / Queue |
|---|---|---|---|---|---|---|
| Free | $0 | — | 100 | **No** | — | 1 task |
| Pro | $20 | $192 | 1,000 | Yes | 20 req/sec | 10 queued |
| Studio | $60 | $720 | 4,000 | Yes | 20 req/sec | 20 queued |
| Enterprise | Custom | Custom | Custom | Yes | 100 req/sec | 50+ |

### Per-call credit costs

| Operation | Credits |
|---|---|
| Auto-Rigging | **5** |
| Animation | **3** |
| Remesh | 5 |
| Retexture | 10 |
| Image-to-3D (Meshy-6, no texture) | 20 |
| Image-to-3D (Meshy-6, with texture) | 30 |
| Multi Image to 3D (no texture) | 5 |
| Multi Image to 3D (with texture) | 15 |
| Text-to-3D Preview (Meshy-6) | 20 |
| Text-to-3D Refine | 10 |

### Per-credit dollar value (derived; not officially disclosed)
- Pro: $20 / 1,000 credits = **$0.020/credit**
- Studio: $60 / 4,000 credits = **$0.015/credit**
- Per-credit topup pricing **not publicly disclosed** — open question to ask Meshy support.

### Per-HoloBorn-avatar cost (rig + 1 baked animation = 8 credits)
- On Pro: **$0.16/avatar**, 125 avatars before topup
- On Studio: **$0.12/avatar**, 500 avatars before topup
- For demo (~10 avatars at EOW): Pro plan covers it 12× over

### API key flow
- Generated at `meshy.ai/settings/api`, format `msy-<random-string>`.
- Pro tier and above — paid plan REQUIRED for real API key.
- Test-mode key `msy_dummy_api_key_for_test_mode_12345678` works against all endpoints with mock responses (no credits consumed). **Useful for wiring the integration before paying.**

---

## 4. Recommended HoloBorn integration pattern

### Architecture: async + poll (v1) → async + webhook (v2)

The HoloBorn pipeline is already async on the Quest side — Quest polls `/generate/{task_id}/status` every 3 seconds. Meshy fits naturally:

```
RunPod GLB ready
  │
  ▼
[1] POST /openapi/v1/rigging  with model_url=<our presigned S3 URL of RunPod GLB>
       → returns rig_task_id, status=PENDING
  │
  ▼
[2] Poll /openapi/v1/rigging/{rig_task_id} every 3-5s
       → wait for status=SUCCEEDED, capture rigged_character_glb_url
  │
  ▼  (cheap path: skip step 3-4, use basic_animations.walking_glb_url for free)
  │
  ▼
[3] POST /openapi/v1/animations  with rig_task_id + action_id (e.g. 0 for Idle)
       → returns anim_task_id
  │
  ▼
[4] Poll /openapi/v1/animations/{anim_task_id}
       → wait for status=SUCCEEDED, capture animation_glb_url
  │
  ▼
[5] Download animation_glb_url, mirror to our S3/local results/avatars/{task_id}.glb
       → MUST happen within 3 days; do it immediately on SUCCEEDED
  │
  ▼
[6] Update HoloBorn task status to "complete", Quest polls and downloads
```

### Polling vs webhook tradeoff
- **Polling** (recommended for v1): zero infra change. Loop every 3-5s on each Meshy task. Simple to debug.
- **Webhooks**: register at API settings, max 5 active per account, HTTPS only, must respond <400 to avoid auto-disable. Cleaner long-term but requires a public endpoint — we already have ngrok, so feasible. Defer to v2.
- **SSE streaming**: nice for log observability but adds connection management. Skip for now.

### Code shape (sketch — `app/services/meshy_client.py`)
```python
import asyncio
import time

import httpx

from app.config import settings


BASE = "https://api.meshy.ai/openapi/v1"


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.meshy_api_key}"}


async def rig_and_animate(glb_url: str, action_id: int = 0) -> bytes:
    async with httpx.AsyncClient(timeout=60) as c:
        # 1. submit rigging
        r = await c.post(f"{BASE}/rigging", headers=_headers(),
                         json={"model_url": glb_url, "height_meters": 1.7})
        rig_id = r.json()["result"]

        # 2. poll
        rig_task = await _poll(c, f"{BASE}/rigging/{rig_id}")

        # 3. submit animation
        r = await c.post(f"{BASE}/animations", headers=_headers(),
                         json={"rig_task_id": rig_id, "action_id": action_id})
        anim_id = r.json()["result"]

        # 4. poll
        anim_task = await _poll(c, f"{BASE}/animations/{anim_id}")

        # 5. download (do this immediately — 3-day expiry)
        glb = await c.get(anim_task["result"]["animation_glb_url"])
        return glb.content


async def _poll(c, url, interval=3, timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        r = await c.get(url, headers=_headers())
        task = r.json()
        if task["status"] == "SUCCEEDED":
            return task
        if task["status"] in ("FAILED", "CANCELED"):
            raise RuntimeError(task.get("task_error", {}).get("message"))
        await asyncio.sleep(interval)
    raise TimeoutError()
```

### Cost estimate per HoloBorn user-generation
- TRELLIS (RunPod): existing cost
- Meshy rig: 5 credits ≈ $0.10 (Pro)
- Meshy 1 animation: 3 credits ≈ $0.06 (Pro)
- **Marginal Meshy cost per avatar: ~$0.16 on Pro, ~$0.12 on Studio**
- For EOW demo: $20 Pro plan covers 125 avatars; massive headroom

### What to ask the founder for
- **Cheapest viable buy: Meshy Pro at $20/mo or $192/yr** (1,000 credits = 125 rigged+animated avatars). Enough through demo + buffer.
- If team will be testing in parallel: bump to Studio ($60/mo, 4,000 credits, 20 concurrent vs 10).
- Free dev-mode key works for wiring code BEFORE the founder approves paid plan — wire/test against `msy_dummy_api_key_for_test_mode_12345678` first.

---

## 5. Risks / gotchas

1. **3-day URL expiry.** All download URLs auto-expire (`expires_at` in task object). MUST `httpx.GET` the GLB and mirror it the moment the task hits `SUCCEEDED`. Quest must never be handed the raw Meshy URL — only our local `/avatars/{task_id}.glb`.
2. **300k face cap on rigging input.** TRELLIS-2-4B at 1536_cascade may emit denser meshes. If Meshy 400s us with a polycount error, insert Meshy's Remesh API (5 credits, +1 sequential call) BEFORE rigging. Validate face count in our backend pre-submit.
3. **+Z forward orientation requirement.** TRELLIS GLB output orientation must be checked. If wrong, rigging fails or rigs incorrectly. May need numpy/trimesh axis swap before submitting.
4. **A-pose conditioning still required.** Empirically validated today. Our portraitizer prompt should explicitly request A-pose to prefilter rigging failures. Community confirms input pose drift IS a known failure mode.
5. **No multi-clip output.** Meshy bakes ONE animation per GLB. To ship an avatar that idles AND walks, we either pay 2× and merge tracks client-side, or accept single-state for v1.
6. **No custom animation upload via API.** If founder wants HoloBorn-specific custom mocap clips, this path is blocked at the API level. Web UI may support it but API does not.
7. **Rate limits are per-account, not per-key.** All keys under one account share 20 req/s + 10 queue (Pro). For multi-dev parallel testing, Studio gives breathing room.
8. **Webhook auto-disable risk.** Multiple consecutive failures auto-disable the webhook. If we go webhook route, Mac server must be reliably reachable via ngrok. Laptop sleep mid-job → silent webhook disable.
9. **Quadruped support is UI-only.** Marketing pages claim quadruped rigging; docs explicitly say programmatic rigging "currently only works well with standard humanoid (bipedal) assets."
10. **Asset retention not differentiated.** All outputs (rigging, animation, basic_animations URLs) share the same 3-day window. Mirror everything we want to keep.
11. **Test-mode API key returns mock data.** Useful for plumbing but does NOT generate a real GLB. Don't accidentally ship to demo with the test key.
12. **Per-credit topup pricing is opaque.** Plan credits are clear ($0.020/credit Pro, $0.015/credit Studio) but pay-as-you-go topup rate is undisclosed.

---

## 6. Open questions to ask Meshy support

1. **Per-credit topup cost** — what does an additional credit pack cost on Pro and Studio plans?
2. **Custom animation retargeting via API** — is there any path to upload an FBX clip and have Meshy retarget it onto a `rig_task_id`?
3. **Multi-clip output** — can a single animation task bake multiple `action_ids` into one GLB with separate clip names? Or is there a "compose" / "merge" endpoint?
4. **Bone naming convention** — does the rigged GLB use Mixamo-style names (`mixamorig:Hips`, `mixamorig:LeftArm`) or Mecanim-friendly names? Affects Unity Humanoid avatar auto-mapping.
5. **Root motion** — do output animations include root motion translation, or only in-place skeleton motion? Affects locomotion behavior in Unity.
6. **GLB animation loop flag** — is `Loop` set on glTF animation channels, or do we set Loop Time in Unity AnimationClip after import?
7. **Idempotency keys** — how to handle retry on transient 5xx without duplicate credit charges?
8. **Webhook signing/secret** — docs don't mention HMAC verification. Is there a signing secret to validate incoming payloads?
9. **Texture resolution preservation** — TRELLIS outputs come with PBR textures. Does Meshy preserve full-res textures through rigging, or downsample?
10. **Action ID stability** — if Meshy adds new animations to the library, do existing IDs remain stable (so our hardcoded `action_id=0` for Idle never breaks)?
11. **Animation library catalog endpoint** — is there a programmatic way to fetch the full catalog (ID + name + category + preview URL), or is the markdown doc the only source of truth?
12. **Free-tier API access for OSS/educational** — any path for early-stage startup discount or hackathon credits?

---

## Sources cited

- [Meshy Docs — Rigging API](https://docs.meshy.ai/en/api/rigging) — primary spec for `/openapi/v1/rigging`
- [Meshy Docs — Animation API](https://docs.meshy.ai/en/api/animation) — primary spec for `/openapi/v1/animations`
- [Meshy Docs — Auto-Rigging & Animation Intro](https://docs.meshy.ai/en/api/rigging-and-animation) — workflow overview, basic_animations bonus output
- [Meshy Docs — Animation Library Reference](https://docs.meshy.ai/en/api/animation-library) — full action_id catalog (~588 entries)
- [Meshy Docs — Pricing](https://docs.meshy.ai/en/api/pricing) — credit costs per operation
- [Meshy Docs — Quickstart](https://docs.meshy.ai/en/api/quick-start) — base URL, auth, dummy test key
- [Meshy Docs — Rate Limits](https://docs.meshy.ai/en/api/rate-limits) — RPS / concurrency per tier, 429 semantics
- [Meshy Docs — Asset Retention](https://docs.meshy.ai/en/api/asset-retention) — 3-day expiry policy
- [Meshy Docs — Webhooks](https://docs.meshy.ai/en/api/webhooks) — HTTPS-only, max 5/account, auto-disable on failure
- [Meshy Docs — Changelog](https://docs.meshy.ai/en/api/changelog) — 2025-05-15 API launch, 2025-10-20 added `rigged_character_glb_url`
- [Meshy.ai — API Platform](https://www.meshy.ai/api) — credit costs, rate limits, feature list
- [Meshy.ai — Pricing](https://www.meshy.ai/pricing) — tier comparison
- [Meshy Help — Plans and Pricing](https://help.meshy.ai/en/articles/12062933) — verified $20 Pro / $60 Studio
- [Meshy Blog — How to Animate a Character](https://www.meshy.ai/blog/how-to-animate-a-character) — T-pose vs A-pose guidance
- [Meshy Blog — 500+ Animation Presets](https://www.meshy.ai/blog/free-3d-animation) — library marketing
- [Product Hunt — Meshy Reviews](https://www.producthunt.com/products/meshy/reviews) — community quality reports

---

## Action items before integration (NOT to be wired into pipeline yet)

1. `curl https://docs.meshy.ai/en/api/animation-library` and parse the action_id table into a Python `IntEnum` so the catalog lives in our codebase.
2. Wire the integration against the `msy_dummy_api_key_for_test_mode_12345678` test key BEFORE the founder approves the $20/mo Pro plan — proves the plumbing without spending money.
3. Pre-submit validation: face count check (must be ≤300k) + orientation check (face must point +Z). Add to backend before calling rigging endpoint.
4. Decide on initial `action_id` — proposal: **0 (Idle)** as the default for HoloBorn v1. Matches founder's "alive but not running around like a duck" intent.
5. Founder ask: Pro plan ($20/mo) for the demo, with Studio ($60/mo) as an upgrade path if multiple devs need parallel testing.
