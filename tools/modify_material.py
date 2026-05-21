"""Targeted PBR material modifications for diagnostic A/B testing on Quest.

Use to produce variants of a grafted GLB that isolate specific material
elements (normal map, emissive routing, KHR_materials_specular) so we
can identify which one drives founder's perceived "gloss."

Variants:
  --strip-normal              remove normalTexture from the material
  --normal-scale X            set normalTexture.scale to X (e.g. 0.3)
  --rough-factor X            set roughnessFactor scalar to X (e.g. 0.41)
  --emissive-as-basecolor     point emissive at baseColor image (May-13 trick)
  --spec-factor R,G,B         add KHR_materials_specular.specularColorFactor
  --ior X                     add KHR_materials_ior.ior
"""
from __future__ import annotations

import argparse
import copy
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
    j = json.loads(data[20:20+json_len])
    off = 20 + json_len
    bin_data = b""
    while off < len(data):
        clen, ctype = struct.unpack_from("<I4s", data, off)
        if ctype == b"BIN\x00":
            bin_data = data[off+8:off+8+clen]
            break
        off += 8 + clen
    return j, bin_data


def write_glb(path: Path, gltf: dict[str, Any], bin_data: bytes) -> int:
    j_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    j_bytes += b" " * ((4 - len(j_bytes) % 4) % 4)
    b_padded = bin_data + b"\x00" * ((4 - len(bin_data) % 4) % 4)
    total = 12 + 8 + len(j_bytes) + 8 + len(b_padded)
    out = bytearray()
    out += struct.pack("<4sII", GLB_MAGIC, 2, total)
    out += struct.pack("<I4s", len(j_bytes), b"JSON")
    out += j_bytes
    out += struct.pack("<I4s", len(b_padded), b"BIN\x00")
    out += b_padded
    path.write_bytes(out)
    return total


def modify(in_path: Path, out_path: Path, args) -> dict:
    j, bin_data = parse_glb(in_path)
    mat = j["materials"][0]
    pbr = mat.setdefault("pbrMetallicRoughness", {})
    changes = []

    if args.strip_normal:
        if "normalTexture" in mat:
            del mat["normalTexture"]
            changes.append("stripped normalTexture")

    if args.normal_scale is not None:
        if "normalTexture" in mat:
            mat["normalTexture"]["scale"] = args.normal_scale
            changes.append(f"set normalTexture.scale={args.normal_scale}")

    if args.rough_factor is not None:
        pbr["roughnessFactor"] = args.rough_factor
        changes.append(f"set roughnessFactor={args.rough_factor}")

    if args.metal_factor is not None:
        pbr["metallicFactor"] = args.metal_factor
        changes.append(f"set metallicFactor={args.metal_factor}")

    if args.emissive_as_basecolor:
        # Point emissive at the baseColor image (May-13 style)
        if "baseColorTexture" in pbr:
            bct_tex_idx = pbr["baseColorTexture"]["index"]
            bct_src_img = j["textures"][bct_tex_idx]["source"]
            if "emissiveTexture" in mat:
                em_tex_idx = mat["emissiveTexture"]["index"]
                j["textures"][em_tex_idx]["source"] = bct_src_img
            else:
                # add a new texture pointing at baseColor's image
                new_tex = {"source": bct_src_img}
                if "sampler" in j["textures"][bct_tex_idx]:
                    new_tex["sampler"] = j["textures"][bct_tex_idx]["sampler"]
                j["textures"].append(new_tex)
                mat["emissiveTexture"] = {"index": len(j["textures"]) - 1}
            changes.append("emissive routed to baseColor image (May-13 style)")

    if args.emissive_factor is not None:
        mat["emissiveFactor"] = list(args.emissive_factor)
        changes.append(f"set emissiveFactor={args.emissive_factor}")

    if args.spec_factor is not None:
        ext = mat.setdefault("extensions", {})
        ext["KHR_materials_specular"] = {
            "specularColorFactor": list(args.spec_factor)
        }
        used = j.setdefault("extensionsUsed", [])
        if "KHR_materials_specular" not in used:
            used.append("KHR_materials_specular")
        changes.append(f"added KHR_materials_specular {args.spec_factor}")

    if args.ior is not None:
        ext = mat.setdefault("extensions", {})
        ext["KHR_materials_ior"] = {"ior": args.ior}
        used = j.setdefault("extensionsUsed", [])
        if "KHR_materials_ior" not in used:
            used.append("KHR_materials_ior")
        changes.append(f"added KHR_materials_ior {args.ior}")

    out_size = write_glb(out_path, j, bin_data)
    return {"out_size": out_size, "changes": changes}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--in", dest="src", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--strip-normal", action="store_true")
    ap.add_argument("--normal-scale", type=float)
    ap.add_argument("--rough-factor", type=float)
    ap.add_argument("--metal-factor", type=float)
    ap.add_argument("--emissive-as-basecolor", action="store_true")
    ap.add_argument("--emissive-factor", type=lambda s: [float(x) for x in s.split(",")])
    ap.add_argument("--spec-factor", type=lambda s: [float(x) for x in s.split(",")])
    ap.add_argument("--ior", type=float)
    args = ap.parse_args()

    if not args.src.exists():
        sys.exit(f"input not found: {args.src}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    s = modify(args.src, args.out, args)
    print(f"  in  : {args.src.stat().st_size/1024/1024:.2f} MB ({args.src})")
    print(f"  out : {s['out_size']/1024/1024:.2f} MB ({args.out})")
    for c in s["changes"]:
        print(f"    • {c}")
    if not s["changes"]:
        print("    (no changes applied)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
