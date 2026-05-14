# HoloBorn — Mac Backend (AGENTS.md)

## What Is This Project

HoloBorn is a Meta Quest 3 mixed reality app that generates 3D avatars from photos.
User presses a button on Quest → captures photo → Mac server processes it → sends to
RunPod GPU → gets back a GLB 3D model → Quest displays it as a hologram in the room.

This repo is the Mac FastAPI server — the middleware between Quest and RunPod GPU.

## Architecture

```
Quest 3 (VR headset)
  │  Burst captures 5 JPEG frames at same angle
  │  POST /generate-multiview (multipart: 5 JPEGs + metadata JSON)
  ▼
THIS SERVER (Mac, FastAPI, CPU only)
  │  1. Validate framing (MediaPipe BlazePose — knees+ankles visible)
  │  2. Average 5 burst frames → 1 clean frame (numpy mean, noise reduction)
  │  3. Portraitize: send to GPT Image 1.5 → studio portrait with white bg
  │  4. Base64 encode the portrait
  │  5. POST to RunPod serverless endpoint
  │  6. Poll for completion, download GLB
  │  7. Serve GLB to Quest
  ▼
RunPod Serverless GPU (RTX 4090)
  │  Preprocessing: CLAHE + white balance + upscale
  │  Enhancement: GFPGAN + RealESRGAN
  │  Background removal: rembg (BiRefNet)
  │  3D generation: TRELLIS.2-4B (1536_cascade mode)
  │  Returns: GLB file
  ▼
Quest 3 downloads GLB → loads via glTFast → spawns hologram in room
```

## RunPod Serverless Endpoint

- Endpoint ID: `pz2c4wvo2rcdw9`
- URL (async): `https://api.runpod.ai/v2/pz2c4wvo2rcdw9/run`
- URL (sync): `https://api.runpod.ai/v2/pz2c4wvo2rcdw9/runsync`
- URL (status): `https://api.runpod.ai/v2/pz2c4wvo2rcdw9/status/{job_id}`
- Docker image: `parthiv8421/holoborn-gpu:latest`
- Network volume: `holoborn-weights`
- Auth: `Authorization: Bearer {RUNPOD_API_KEY}`
- Input: `{"input": {"image_b64": "<base64 encoded image>"}}`
- Optional input params: `seed`, `decimation`, `texture_size`, `pipeline_type`, `skip_enhance`, `skip_preprocess`
- Output: `{"output": {"glb_volume_path": "...", "glb_size_bytes": int, "elapsed_seconds": float}}`
- Execution time: ~3-5 minutes per job
- The GLB is saved on the network volume. We need to download it or have the handler return it as base64.

## Quest API Contract (what the Quest VR app expects)

The Quest build is already deployed on the headset. We MUST match these exact endpoints and response shapes.

### Two capture modes on Quest:

**A button (left controller) — burst capture (CURRENT PRIMARY MODE):**
- Captures 5 frames rapidly from same position
- Sends all 5 as multipart to /generate-multiview
- Metadata: all angles = 0.0 (same position)

**X button (left controller) — single frame + revolve (FUTURE, for multi-image models):**
- Validates frame first via /validate-frame
- If good: captures 1 frame, sends to /generate-multiview with 1 frame
- OR: user revolves around subject, captures 30 frames at 12° intervals

### Endpoints:

**POST /validate-frame**
```
Request: raw JPEG bytes, Content-Type: image/jpeg
Response: {
    "framing": "good" | "bad",
    "message": "",
    "landmarks_detected": 0,
    "subject_center_x": 0.0,
    "subject_center_z": 0.0,
    "processing_time_ms": 0.0
}
```
Runs MediaPipe BlazePose. Checks both knees AND both ankles visible (visibility > 0.5).

**POST /generate-multiview**
```
Request: multipart/form-data
  - frame_0: JPEG file
  - frame_1: JPEG file (if burst)
  - frame_2: JPEG file (if burst)
  - frame_3: JPEG file (if burst)
  - frame_4: JPEG file (if burst)
  - metadata: JSON string "[{\"index\":0,\"angle\":0.0}, ...]"

Response: {
    "status": "processing",
    "task_id": "uuid-string",
    "frames_received": 5,
    "message": ""
}
```

**GET /generate/{task_id}/status**
```
Response: {
    "status": "processing" | "complete" | "failed",
    "progress": 0-100,
    "glb_url": "/avatars/{task_id}.glb",
    "message": ""
}
```
Quest polls this every 3 seconds.

**GET /avatars/{task_id}.glb**
Static file serve. Quest downloads the GLB binary from here.

**GET /health**
```
Response: {
    "status": "alive",
    "frames_processed": 0,
    "uptime_seconds": 0.0
}
```

**POST /detect** (legacy, keep for compatibility)
```
Request: raw JPEG bytes or multipart with "file" field
Response: {
    "detected": true/false,
    "face_count": 0,
    "faces": [{"bbox": {"x": 0, "y": 0, "width": 0, "height": 0}, "confidence": 0.0}],
    "frame_number": 0,
    "processing_time_ms": 0.0
}
```

### HTTPS / Networking:
- Quest connects to Mac via ngrok (WiFi client isolation prevents direct local IP)
- Quest uses BypassCertificate handler (accepts all TLS certs)
- ngrok URL goes in Quest build config or is discovered at runtime

## GPT Image 1.5 Portraitizer

Converts dark Quest capture into studio-quality portrait. Preserves identity, clothing, pose.

```python
from openai import OpenAI

client = OpenAI()  # uses OPENAI_API_KEY from env

response = client.images.edit(
    model="gpt-image-1.5",
    image=image_bytes,  # raw JPEG/PNG bytes
    prompt=(
        "Transform this photo into a clean professional portrait. "
        "Studio lighting with soft diffused front light. "
        "Plain white background, no other objects or environment visible. "
        "Preserve the person's exact face, facial hair, skin tone, "
        "hairstyle, clothing, accessories, body pose, and proportions. "
        "Full body visible from head to feet. "
        "Do not change, stylize, or idealize any facial features. "
        "Photorealistic output, not illustrated or painted."
    ),
    size="1024x1536",
    quality="high",
    response_format="b64_json",
)
portrait_bytes = base64.b64decode(response.data[0].b64_json)
```

## Project Structure to Build

```
holoborn-server/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, lifespan, route registration
│   ├── config.py             # Settings from .env via pydantic-settings
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── detection.py      # POST /detect
│   │   ├── generation.py     # POST /validate-frame, /generate-multiview, GET /generate/{id}/status
│   │   └── health.py         # GET /health
│   ├── services/
│   │   ├── __init__.py
│   │   ├── face_detector.py  # MediaPipe face detection wrapper
│   │   ├── pose_validator.py # MediaPipe BlazePose framing check
│   │   ├── preprocessing.py  # Burst averaging (numpy)
│   │   ├── portraitizer.py   # GPT Image 1.5 API call
│   │   ├── runpod_client.py  # RunPod serverless API (submit job, poll status, download GLB)
│   │   └── frame_decoder.py  # JPEG bytes → numpy array
│   └── models/
│       ├── __init__.py
│       ├── schemas.py        # Detection schemas (BBox, FaceDetection, DetectionResponse)
│       └── generation_schemas.py  # FramingResponse, GenerateResponse, TaskStatusResponse, MultiviewResponse
├── results/
│   ├── avatars/              # Downloaded GLBs served to Quest
│   ├── originals/            # Saved validation frames
│   └── scans/                # Saved scan frames + metadata
├── .env                      # API keys and config
├── .gitignore
├── requirements.txt
└── README.md
```

## .env File

```
OPENAI_API_KEY=<key>
RUNPOD_API_KEY=<key>
RUNPOD_ENDPOINT_ID=pz2c4wvo2rcdw9
GPU_SERVER_URL=https://api.runpod.ai/v2/pz2c4wvo2rcdw9
```

## Key Technical Notes

- ALL heavy processing (GFPGAN, ESRGAN, rembg, TRELLIS) runs on GPU. Mac does NO ML inference except MediaPipe.
- Burst averaging is pure numpy — pixel-wise mean of decoded frames. No alignment needed (headset barely moves in 200ms).
- The portraitizer (GPT Image 1.5) is the key preprocessing step. It transforms dark Quest captures into studio portraits.
- Quest sends raw JPEG at quality 75 from passthrough camera (1280x960 or 1280x1280).
- Unity/Quest uses Content-Type: image/jpeg for /validate-frame (raw body, not multipart).
- Unity/Quest may add BOM and null bytes to metadata strings — strip them.
- glTF magic bytes for GLB validation: first 4 bytes = b'glTF'

## RunPod Job Flow

1. Submit: POST /run with {"input": {"image_b64": "..."}} → returns {"id": "job-id", "status": "IN_QUEUE"}
2. Poll: GET /status/{job_id} → returns {"status": "IN_QUEUE|IN_PROGRESS|COMPLETED|FAILED", "output": {...}}
3. When COMPLETED: output contains GLB data or volume path
4. Download GLB and save to results/avatars/{task_id}.glb

## Rules for This Build

1. Git commit after every working feature. No exceptions.
2. Test each endpoint with curl before moving to the next.
3. Keep it simple. This is a thin proxy server, not a ML pipeline.
4. Every file under 200 lines. If it's longer, split it.
5. Save intermediate files (raw frames, averaged frame, portrait, GLB) for debugging.
6. Print timing for every step (burst avg, portraitize, runpod submit, runpod poll, glb download).
7. Handle errors gracefully — Quest is polling, so return proper error status codes.
8. CORS is not needed (Quest uses raw HTTP, not browser fetch).