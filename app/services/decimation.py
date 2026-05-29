"""Server-side GLB decimation via gltfpack — Quest poly-budget fix.

Hunyuan/TRELLIS geometry is ~450-500k tris, which stutters when the user walks
around the avatar on Quest 3 (hardware poly-budget ceiling, not a bug). gltfpack
simplification (`-si`) drops it to ~80k tris, killing the stutter. Inserted
**before Meshy rigging** so the skeleton is built on the low-poly mesh and skin
weights stay clean (decimating a *rigged* mesh resamples/breaks weights).

CRITICAL: `-noq` is mandatory. gltfpack's default quantization
(KHR_mesh_quantization + auto-injected KHR_texture_transform) scrambles UVs on
glTFast 6.18 → textures render as random patches. `-noq` keeps UVs as plain
FLOAT. The `-si` does the triangle reduction regardless of quantization, so
there is no downside to `-noq`. (Validated on Quest 2026-05-29.)

KTX2 (`-tc`) / meshopt (`-c`) are intentionally NOT used — the Unity project's
glTFast 6.18 has no KtxUnity / meshopt-decompress packages, so those would
silently fail to load. Geometry-only simplification is what's supported today.
"""
from __future__ import annotations

import logging
import shutil
import struct
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


class DecimationError(Exception):
    """gltfpack failed or produced an invalid GLB."""


def _tri_count(glb_path: Path) -> int | None:
    """Best-effort triangle count from the GLB JSON chunk (for logging only)."""
    try:
        import json

        data = glb_path.read_bytes()
        if data[:4] != b"glTF":
            return None
        json_len = struct.unpack("<I", data[12:16])[0]
        gltf = json.loads(data[20 : 20 + json_len].decode("utf-8").rstrip("\x00 "))
        tris = 0
        for m in gltf.get("meshes", []):
            for p in m["primitives"]:
                if "indices" in p:
                    tris += gltf["accessors"][p["indices"]]["count"] // 3
        return tris
    except Exception:
        return None


def decimate_glb(
    in_path: Path,
    out_path: Path,
    ratio: float = 0.18,
    *,
    gltfpack_bin: str = "gltfpack",
    timeout_s: float = 120.0,
) -> bool:
    """Simplify `in_path` to ~`ratio` of its triangles, writing `out_path`.

    Runs `gltfpack -i <in> -o <out> -si <ratio> -noq`. Returns True on success.
    On any failure (gltfpack missing, non-zero exit, invalid output) returns
    False WITHOUT raising — the caller is expected to fall back to the
    un-decimated GLB so a decimation hiccup never breaks the avatar pipeline.
    """
    in_path = Path(in_path)
    out_path = Path(out_path)
    if not in_path.exists():
        log.warning("decimate_glb: input missing %s — skipping", in_path)
        return False

    cmd = [
        gltfpack_bin,
        "-i", str(in_path),
        "-o", str(out_path),
        "-si", f"{ratio:g}",
        "-noq",  # MANDATORY — see module docstring (UV-scramble fix)
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_s
        )
    except FileNotFoundError:
        log.warning("decimate_glb: gltfpack not found on PATH (%r) — skipping", gltfpack_bin)
        return False
    except subprocess.TimeoutExpired:
        log.warning("decimate_glb: gltfpack timed out after %.0fs — skipping", timeout_s)
        return False

    if proc.returncode != 0:
        log.warning(
            "decimate_glb: gltfpack exit=%d — skipping. stderr=%s",
            proc.returncode, (proc.stderr or "").strip()[:300],
        )
        return False

    # Validate the output is a real GLB before trusting it.
    if not out_path.exists() or out_path.stat().st_size < 12:
        log.warning("decimate_glb: output missing/empty %s — skipping", out_path)
        return False
    with out_path.open("rb") as f:
        if f.read(4) != b"glTF":
            log.warning("decimate_glb: output not a glTF (bad magic) — skipping")
            return False

    before, after = _tri_count(in_path), _tri_count(out_path)
    log.info(
        "decimate_glb: %s -> %s  tris %s->%s  size %.1f->%.1f MB",
        in_path.name, out_path.name, before, after,
        in_path.stat().st_size / 1e6, out_path.stat().st_size / 1e6,
    )
    return True
