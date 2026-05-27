"""Normalize a GLB to TRELLIS convention: feet-at-origin, 1.7m tall.

Background: Hunyuan3D-2 (Replicate) outputs GLBs in a normalized-cube convention
(Y range [-1, +1], unit-cube bounds) where the model is centered on the origin.
TRELLIS production GLBs use a feet-at-origin convention with real-world meter
units (Y range [0, ~1.7], head up). Unity spawn logic assumes TRELLIS convention,
so dropping a raw Hunyuan GLB into the Y-test slot puts the avatar's pelvis at
floor height — feet clip 1m below floor, head juts 1m above expected.

This tool rewrites positions in-place so:
  1. min_y becomes exactly 0.0 (feet on origin)
  2. uniform scale applied so max_y becomes target_height (default 1.7m)
  3. X / Z stay centered around origin (Hunyuan already centers them)
  4. POSITION accessor min/max metadata updated to match

Assumptions (asserted at runtime):
  - GLB has exactly 1 mesh with 1 primitive (matches Hunyuan + TRELLIS output)
  - POSITION accessor uses float32 VEC3
  - Position bufferView is either tightly packed or has explicit byteStride

Run:
    .venv/bin/python tools/normalize_glb_for_quest.py \\
        --in  ~/Downloads/real_human_textured.glb \\
        --out results/avatars/test.glb \\
        --height 1.7
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


def parse_glb(data: bytes) -> tuple[dict, bytes, int]:
    """Return (json_dict, bin_chunk_bytes, json_chunk_byte_length)."""
    assert data[:4] == b"glTF", "not a GLB file"
    json_len = struct.unpack("<I", data[12:16])[0]
    json_type = data[16:20]
    assert json_type == b"JSON", f"expected JSON chunk, got {json_type!r}"
    json_str = data[20 : 20 + json_len].decode("utf-8").rstrip("\x00 ")
    gltf = json.loads(json_str)
    bin_off = 20 + json_len
    bin_len = struct.unpack("<I", data[bin_off : bin_off + 4])[0]
    bin_type = data[bin_off + 4 : bin_off + 8]
    assert bin_type == b"BIN\x00", f"expected BIN chunk, got {bin_type!r}"
    bin_bytes = data[bin_off + 8 : bin_off + 8 + bin_len]
    return gltf, bin_bytes, json_len


def write_glb(gltf: dict, bin_bytes: bytes) -> bytes:
    """Repack GLB. Pads JSON chunk to 4-byte boundary with spaces (glTF spec)."""
    json_str = json.dumps(gltf, separators=(",", ":"))
    json_bytes = json_str.encode("utf-8")
    pad = (4 - len(json_bytes) % 4) % 4
    json_bytes = json_bytes + b" " * pad
    bin_pad = (4 - len(bin_bytes) % 4) % 4
    bin_padded = bin_bytes + b"\x00" * bin_pad

    total = 12 + 8 + len(json_bytes) + 8 + len(bin_padded)
    out = bytearray()
    out += b"glTF"
    out += struct.pack("<I", 2)
    out += struct.pack("<I", total)
    out += struct.pack("<I", len(json_bytes))
    out += b"JSON"
    out += json_bytes
    out += struct.pack("<I", len(bin_padded))
    out += b"BIN\x00"
    out += bin_padded
    return bytes(out)


def normalize(in_path: Path, out_path: Path, target_height: float) -> None:
    data = in_path.read_bytes()
    gltf, bin_bytes, _ = parse_glb(data)

    meshes = gltf.get("meshes", [])
    assert len(meshes) == 1, f"expected 1 mesh, got {len(meshes)}"
    prims = meshes[0]["primitives"]
    assert len(prims) == 1, f"expected 1 primitive, got {len(prims)}"

    pos_acc_idx = prims[0]["attributes"]["POSITION"]
    pos_acc = gltf["accessors"][pos_acc_idx]
    assert pos_acc["componentType"] == 5126, "POSITION must be float32 (5126)"
    assert pos_acc["type"] == "VEC3", "POSITION must be VEC3"
    count = pos_acc["count"]
    bv = gltf["bufferViews"][pos_acc["bufferView"]]
    bv_offset = bv.get("byteOffset", 0)
    acc_offset = pos_acc.get("byteOffset", 0)
    stride = bv.get("byteStride", 12)  # 12 = 3 floats, tightly packed default
    assert stride == 12, (
        f"interleaved positions not supported (byteStride={stride}); "
        "tool currently only handles non-interleaved float32 VEC3"
    )

    base = bv_offset + acc_offset
    # Read positions
    positions: list[list[float]] = []
    for i in range(count):
        off = base + i * stride
        x, y, z = struct.unpack_from("<fff", bin_bytes, off)
        positions.append([x, y, z])

    # Compute current bbox
    min_x = min(p[0] for p in positions)
    max_x = max(p[0] for p in positions)
    min_y = min(p[1] for p in positions)
    max_y = max(p[1] for p in positions)
    min_z = min(p[2] for p in positions)
    max_z = max(p[2] for p in positions)
    current_h = max_y - min_y
    assert current_h > 0, "degenerate mesh (zero height)"
    scale = target_height / current_h

    print(
        f"[in ] bbox X[{min_x:.3f},{max_x:.3f}] "
        f"Y[{min_y:.3f},{max_y:.3f}] Z[{min_z:.3f},{max_z:.3f}] "
        f"H={current_h:.3f}"
    )
    print(f"[op ] translate Y by {-min_y:+.3f} (feet to origin), scale uniform x{scale:.4f}")

    # Rewrite positions: translate Y to feet=0, then uniform scale
    bin_mut = bytearray(bin_bytes)
    new_positions = []
    for i, (x, y, z) in enumerate(positions):
        nx = x * scale
        ny = (y - min_y) * scale
        nz = z * scale
        new_positions.append([nx, ny, nz])
        struct.pack_into("<fff", bin_mut, base + i * stride, nx, ny, nz)

    # Update accessor min/max metadata
    pos_acc["min"] = [
        min(p[0] for p in new_positions),
        min(p[1] for p in new_positions),
        min(p[2] for p in new_positions),
    ]
    pos_acc["max"] = [
        max(p[0] for p in new_positions),
        max(p[1] for p in new_positions),
        max(p[2] for p in new_positions),
    ]
    print(
        f"[out] bbox X[{pos_acc['min'][0]:.3f},{pos_acc['max'][0]:.3f}] "
        f"Y[{pos_acc['min'][1]:.3f},{pos_acc['max'][1]:.3f}] "
        f"Z[{pos_acc['min'][2]:.3f},{pos_acc['max'][2]:.3f}] "
        f"H={pos_acc['max'][1] - pos_acc['min'][1]:.3f}"
    )

    out_bytes = write_glb(gltf, bytes(bin_mut))
    out_path.write_bytes(out_bytes)
    print(f"[ok ] wrote {out_path} ({len(out_bytes)/1e6:.2f} MB)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--in", dest="input", required=True, type=Path, help="source GLB")
    ap.add_argument("--out", dest="output", required=True, type=Path, help="dest GLB")
    ap.add_argument("--height", type=float, default=1.7, help="target height in meters (default 1.7)")
    args = ap.parse_args()
    normalize(args.input, args.output, args.height)


if __name__ == "__main__":
    main()
