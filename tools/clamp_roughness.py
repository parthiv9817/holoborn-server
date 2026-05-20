"""Clamp metalRoughness texture's G (roughness) channel to a minimum floor.

Background: Meshy's retex pipeline started outputting roughness maps with mean
~138 (mid-gloss) around 2026-05-19. Pre-regression GLBs had mean ~252 (matte).
This tool clamps the roughness channel to a configurable floor so production
GLBs read matte again until Meshy ships a fix (or we change vendor).

How it works:
  - Locates the material's metallicRoughnessTexture → its image → its bufferView
  - Decodes the JPEG (glTF spec: R=ignored, G=roughness, B=metallic)
  - Clamps G channel to >= floor; optionally zeroes B channel
  - Re-encodes as JPEG, appends to bin chunk, points image at new bufferView
  - Leaves original bytes orphaned (~1MB waste, valid GLB)

Run:
    .venv/bin/python tools/clamp_roughness.py \\
        --in  results/avatars/<src>.glb \\
        --out results/avatars/<src>_clamped.glb \\
        --floor 220
"""
from __future__ import annotations

import argparse
import io
import json
import struct
import sys
from pathlib import Path
from typing import Any

GLB_MAGIC = b"glTF"


def parse_glb(path: Path) -> tuple[dict[str, Any], bytes]:
    data = path.read_bytes()
    magic, version, total_len = struct.unpack_from("<4sII", data, 0)
    assert magic == GLB_MAGIC
    json_len, json_type = struct.unpack_from("<I4s", data, 12)
    assert json_type == b"JSON"
    gltf = json.loads(data[20 : 20 + json_len])
    bin_start = 20 + json_len
    bin_len, bin_type = struct.unpack_from("<I4s", data, bin_start)
    assert bin_type == b"BIN\x00"
    bin_data = data[bin_start + 8 : bin_start + 8 + bin_len]
    return gltf, bin_data


def write_glb(path: Path, gltf: dict[str, Any], bin_data: bytes) -> int:
    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_bytes += b" " * ((4 - len(json_bytes) % 4) % 4)
    bin_padded = bin_data + b"\x00" * ((4 - len(bin_data) % 4) % 4)
    total = 12 + 8 + len(json_bytes) + 8 + len(bin_padded)
    out = bytearray()
    out += struct.pack("<4sII", GLB_MAGIC, 2, total)
    out += struct.pack("<I4s", len(json_bytes), b"JSON")
    out += json_bytes
    out += struct.pack("<I4s", len(bin_padded), b"BIN\x00")
    out += bin_padded
    path.write_bytes(out)
    return total


def find_metalrough_image(gltf: dict[str, Any]) -> int:
    for m in gltf.get("materials", []):
        pbr = m.get("pbrMetallicRoughness", {})
        mrt = pbr.get("metallicRoughnessTexture")
        if mrt is None:
            continue
        t_idx = mrt["index"]
        src = gltf["textures"][t_idx].get("source")
        if src is not None:
            return src
    raise ValueError("no metallicRoughnessTexture found")


def clamp(in_path: Path, out_path: Path, floor: int, zero_metallic: bool,
          jpeg_quality: int) -> dict[str, Any]:
    from PIL import Image

    gltf, bin_data = parse_glb(in_path)
    img_idx = find_metalrough_image(gltf)
    img_entry = gltf["images"][img_idx]
    bv_idx = img_entry["bufferView"]
    bv = gltf["bufferViews"][bv_idx]
    off, length = bv.get("byteOffset", 0), bv["byteLength"]

    jpeg_in = bin_data[off : off + length]
    pil = Image.open(io.BytesIO(jpeg_in)).convert("RGB")
    w, h = pil.size

    r_band, g_band, b_band = pil.split()
    g_in = list(g_band.getdata())
    b_in = list(b_band.getdata())
    g_mean_before = sum(g_in) / len(g_in)
    b_mean_before = sum(b_in) / len(b_in)

    g_clamped = bytes(max(v, floor) for v in g_in)
    b_clamped = bytes(0 for _ in b_in) if zero_metallic else b_band.tobytes()

    new_g = Image.frombytes("L", (w, h), g_clamped)
    new_b = Image.frombytes("L", (w, h), b_clamped)
    out_img = Image.merge("RGB", (r_band, new_g, new_b))

    buf = io.BytesIO()
    out_img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
    jpeg_out = buf.getvalue()

    g_mean_after = sum(g_clamped) / len(g_clamped)
    b_mean_after = sum(b_clamped) / len(b_clamped)

    new_bin = bytearray(bin_data)
    while len(new_bin) % 4 != 0:
        new_bin.append(0)
    new_offset = len(new_bin)
    new_bin.extend(jpeg_out)

    gltf["bufferViews"].append({
        "buffer": 0,
        "byteOffset": new_offset,
        "byteLength": len(jpeg_out),
    })
    new_bv_idx = len(gltf["bufferViews"]) - 1
    img_entry["bufferView"] = new_bv_idx

    if gltf.get("buffers"):
        gltf["buffers"][0]["byteLength"] = len(new_bin)

    out_size = write_glb(out_path, gltf, bytes(new_bin))

    return {
        "in_size": in_path.stat().st_size,
        "out_size": out_size,
        "dimensions": f"{w}x{h}",
        "jpeg_in_bytes": len(jpeg_in),
        "jpeg_out_bytes": len(jpeg_out),
        "g_mean_before": g_mean_before,
        "g_mean_after": g_mean_after,
        "b_mean_before": b_mean_before,
        "b_mean_after": b_mean_after,
        "floor": floor,
        "zero_metallic": zero_metallic,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--in", dest="src", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--floor", type=int, default=220,
                    help="min G value (0..255). 220 = ~0.86 roughness, very matte")
    ap.add_argument("--zero-metallic", action="store_true", default=True,
                    help="force B channel to 0 (kill spurious metallic). Default on.")
    ap.add_argument("--keep-metallic", action="store_true",
                    help="preserve B channel (override --zero-metallic)")
    ap.add_argument("--jpeg-quality", type=int, default=92)
    args = ap.parse_args()

    zero_metallic = args.zero_metallic and not args.keep_metallic

    if not args.src.exists():
        sys.exit(f"input not found: {args.src}")
    args.out.parent.mkdir(parents=True, exist_ok=True)

    s = clamp(args.src, args.out, args.floor, zero_metallic, args.jpeg_quality)
    mb = lambda n: f"{n/1024/1024:.2f} MB"
    print(f"  in  : {mb(s['in_size'])}   ({args.src})")
    print(f"  out : {mb(s['out_size'])}   ({args.out})")
    print(f"  metalRough texture: {s['dimensions']}  "
          f"jpeg {s['jpeg_in_bytes']:,} → {s['jpeg_out_bytes']:,} bytes")
    print(f"  roughness G : mean {s['g_mean_before']:6.1f} → {s['g_mean_after']:6.1f}  "
          f"(floor={s['floor']})")
    print(f"  metallic  B : mean {s['b_mean_before']:6.1f} → {s['b_mean_after']:6.1f}  "
          f"(zero_metallic={s['zero_metallic']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
