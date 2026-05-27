"""Inspect a GLB: tri count, materials, texture inventory + resolution, PBR maps.

Pure-Python, no deps. Optionally dumps the largest (base-color) texture to disk
so it can be eyeballed.

Run:
    .venv/bin/python tools/inspect_glb.py <file.glb> [--dump-tex OUTDIR]
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


def parse_glb(data: bytes):
    assert data[:4] == b"glTF", "not a GLB file"
    json_len = struct.unpack("<I", data[12:16])[0]
    json_str = data[20 : 20 + json_len].decode("utf-8").rstrip("\x00 ")
    gltf = json.loads(json_str)
    bin_off = 20 + json_len
    bin_len = struct.unpack("<I", data[bin_off : bin_off + 4])[0]
    bin_bytes = data[bin_off + 8 : bin_off + 8 + bin_len]
    return gltf, bin_bytes


def img_dims(b: bytes):
    """Return (fmt, w, h) for PNG/JPEG bytes, else (fmt, None, None)."""
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", b[16:24])
        return "png", w, h
    if b[:2] == b"\xff\xd8":  # JPEG: scan SOF markers
        i = 2
        while i < len(b) - 9:
            if b[i] != 0xFF:
                i += 1
                continue
            marker = b[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3):
                h, w = struct.unpack(">HH", b[i + 5 : i + 9])
                return "jpeg", w, h
            seg = struct.unpack(">H", b[i + 2 : i + 4])[0]
            i += 2 + seg
        return "jpeg", None, None
    return "?", None, None


def bv_bytes(gltf, bin_bytes, bv_idx):
    bv = gltf["bufferViews"][bv_idx]
    off = bv.get("byteOffset", 0)
    return bin_bytes[off : off + bv["byteLength"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("glb", type=Path)
    ap.add_argument("--dump-tex", type=Path, default=None)
    args = ap.parse_args()

    gltf, bin_bytes = parse_glb(args.glb.read_bytes())
    print(f"== {args.glb.name} ({len(args.glb.read_bytes())/1e6:.1f} MB) ==")

    # geometry
    total_tris = 0
    total_verts = 0
    for m in gltf.get("meshes", []):
        for p in m["primitives"]:
            idx = gltf["accessors"][p["indices"]]["count"]
            total_tris += idx // 3
            total_verts += gltf["accessors"][p["attributes"]["POSITION"]]["count"]
    print(f"meshes={len(gltf.get('meshes', []))} "
          f"prims={sum(len(m['primitives']) for m in gltf.get('meshes', []))} "
          f"verts={total_verts:,} tris={total_tris:,}")

    # skin / animation
    print(f"skins={len(gltf.get('skins', []))} "
          f"animations={len(gltf.get('animations', []))} "
          f"nodes={len(gltf.get('nodes', []))}")

    # materials + which maps
    for mi, mat in enumerate(gltf.get("materials", [])):
        pbr = mat.get("pbrMetallicRoughness", {})
        maps = []
        if "baseColorTexture" in pbr:
            maps.append("baseColor")
        if "metallicRoughnessTexture" in pbr:
            maps.append("metalRough")
        if "normalTexture" in mat:
            maps.append("normal")
        if "occlusionTexture" in mat:
            maps.append("occlusion")
        if "emissiveTexture" in mat:
            maps.append("emissive")
        mf = pbr.get("metallicFactor", "?")
        rf = pbr.get("roughnessFactor", "?")
        bcf = pbr.get("baseColorFactor", "?")
        print(f"material[{mi}] '{mat.get('name','')}' maps={maps} "
              f"metallic={mf} roughness={rf} baseColorFactor={bcf}")

    # textures + dims
    images = gltf.get("images", [])
    print(f"images={len(images)} textures={len(gltf.get('textures', []))}")
    if args.dump_tex:
        args.dump_tex.mkdir(parents=True, exist_ok=True)
    for ii, img in enumerate(images):
        if "bufferView" in img:
            b = bv_bytes(gltf, bin_bytes, img["bufferView"])
        else:
            b = b""
        fmt, w, h = img_dims(b)
        print(f"  image[{ii}] '{img.get('name','')}' {fmt} {w}x{h} "
              f"({len(b)/1e6:.2f} MB)")
        if args.dump_tex and b:
            ext = "png" if fmt == "png" else "jpg"
            out = args.dump_tex / f"{args.glb.stem}_img{ii}.{ext}"
            out.write_bytes(b)


if __name__ == "__main__":
    main()
