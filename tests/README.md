# tests/ — HoloBorn Mac backend testing

Ad-hoc test scripts and their input/output artifacts. Separate from the live server's
runtime data in `results/`.

## Layout

```
tests/
├── scripts/                        # test runners (Python, run from repo root)
│   ├── test_burst_average.py       # offline test: burst-average 5 frames into 1
│   └── test_runpod_manual.py       # end-to-end: send image to RunPod, download GLB
├── inputs/                         # frozen reference fixtures (committed, ~MB-scale)
│   ├── burst_5frames_quest_20260504/
│   │   ├── frame_0..4.jpg          # real Quest burst, 1280x960 each
│   │   └── metadata.json
│   └── validate_samples/
│       ├── validate_*_bad.jpg      # known bad-framing cases (feet not visible)
│       └── validate_*.jpg          # raw frames sent through /validate-frame
├── outputs/                        # GITIGNORED — test scripts write here
│   ├── burst_average/              # latest run of test_burst_average.py
│   │   ├── averaged.jpg
│   │   ├── diff_vs_frame0.jpg      # 4x amplified, makes noise visible
│   │   └── frame_0_copy.jpg
│   └── runpod_glbs/                # GLBs from test_runpod_manual.py
│       └── manual_test_YYYYMMDD_HHMMSS.glb
└── captures/                       # GITIGNORED — on-device test session artifacts
    ├── 2026-05-06-brick2/          # one folder per session, named by date+brick
    │   ├── originals/              # /validate-frame _good/_bad tagged
    │   └── quest_test_uploads/     # raw uploads when QUEST_TEST_MODE=True
    └── archive/                    # older runtime captures worth keeping
```

## What lives where — quick rule

| | Where it goes | Gitignored? |
|---|---|---|
| Test input fixtures (frozen, reused across runs) | `tests/inputs/` | NO — committed |
| Test script outputs (per-run, can be cleared) | `tests/outputs/` | YES |
| On-device session captures (organized by date/brick) | `tests/captures/` | YES |
| Live server outputs (when uvicorn is running) | `results/` | YES |

`results/` is owned by the FastAPI app — `/validate-frame` saves to `results/originals/`,
`/generate-multiview` saves frames to `results/scans/` and GLBs to `results/avatars/`.
**Do not put test artifacts in `results/`.** The server might overwrite or expect a specific layout.

## Running the tests

From repo root:

```bash
source .venv/bin/activate

# Offline burst-average sanity check (no network, no GPU)
python tests/scripts/test_burst_average.py

# RunPod end-to-end with the burst-averaged fixture as input (~5-9 min cold start, ~$0.55)
python tests/scripts/test_runpod_manual.py
# OR with a custom input
python tests/scripts/test_runpod_manual.py path/to/portrait.png
```

Both scripts resolve their paths against repo root (via `Path(__file__).resolve().parents[2]`),
so the CWD doesn't matter.

## Where new test data goes

When the live server runs and Quest hits an endpoint, the server saves:

| Endpoint | Saved to |
|---|---|
| `POST /validate-frame` | `results/originals/<timestamp>.jpg` |
| `POST /generate-multiview` (scan, N=30) | `results/scans/<task_id>/` (frames + metadata) |
| `POST /generate-multiview` (burst, N=5) | `results/quest_test_uploads/multiview_<timestamp>/` |
| GLB downloaded from RunPod | `results/avatars/<task_id>.glb` |

These are **runtime artifacts**, not test fixtures. Inspect them in place to see what
the live pipeline received and produced. If a particular sample is worth keeping as a
permanent test input, copy it into `tests/inputs/<descriptive_name>/`.

## Promoting a runtime sample to a fixture

```bash
# Example: promote a freshly-captured Quest burst as a new fixture
cp -r results/quest_test_uploads/multiview_20260506_xxxxxx_xxxxxxxx \
      tests/inputs/burst_5frames_quest_20260506/
git add tests/inputs/burst_5frames_quest_20260506/
git commit -m "test(fixture): add Quest burst sample from 2026-05-06"
```

That moves the sample from "thing the server happened to save" to "frozen reference data
this test depends on" — versioned, durable, doesn't get cleaned up when `results/` is wiped.
