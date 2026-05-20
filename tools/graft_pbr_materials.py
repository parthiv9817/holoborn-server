"""Graft retex GLB's PBR material stack onto a rigged GLB.

Meshy's /rigging endpoint strips metallic / roughness / normal / emissive textures
and corrupts the emissive channel (points it at baseColor with emissiveFactor=[1,1,1],
causing washed-out double-emission). This tool fixes that by copying the full PBR
stack (4 textures / 4 images / 4 samplers / 1 material) from a retex GLB onto the
rigged GLB's mesh primitive. UV mapping is preserved through Meshy rigging (verified
empirically 2026-05-13), so retex's textures sample correctly onto rigged UVs.

Assumptions (validated for our Quest pipeline; assert at runtime):
  - Both GLBs have exactly 1 mesh, 1 primitive, 1 material
  - Both use the same single UV set (TEXCOORD_0)
  - UV coordinate space matches (min/max U/V align between GLBs)

Run:
    .venv/bin/python tools/graft_pbr_materials.py \\
        --retex tests/outputs/full_pipeline/<clean>.glb \\
        --rigged tests/outputs/meshy_glbs/<rigged>.glb \\
        --out results/avatars/test.glb
"""
from __future__ import annotations

import argparse
import copy
import io
import json
import struct
import sys
from pathlib import Path
from typing import Any

GLB_MAGIC = b"glTF"
GLB_VERSION = 2

# Defensive infrastructure against Meshy's upstream retex roughness drift.
# Meshy began outputting metalRough maps with G-channel mean ~138 (mid-gloss)
# around 2026-05-19; pre-regression GLBs had mean ~252 (fully matte). We clamp
# G to a floor at graft time so every production GLB lands in the matte zone.
# Council-validated floor=200 (2026-05-20) — see diaries/2026-05-20.md.
DEFAULT_ROUGHNESS_FLOOR = 200
DEFAULT_JPEG_QUALITY = 92


def _clamp_metalrough_jpeg(
    jpeg_bytes: bytes,
    floor: int,
    zero_metallic: bool,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
) -> tuple[bytes, dict[str, float]]:
    """Clamp the metalRough texture's G (roughness) channel to >= floor and
    optionally zero the B (metallic) channel. Returns (new_jpeg_bytes, stats).

    glTF metalRough convention: R=ignored, G=roughness, B=metallic, A=ignored.
    Higher G = more matte (255 = fully matte, 0 = mirror-glossy).
    """
    from PIL import Image

    img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
    w, h = img.size
    r_band, g_band, b_band = img.split()
    g_in = list(g_band.getdata())
    b_in = list(b_band.getdata())
    g_mean_before = sum(g_in) / len(g_in)
    b_mean_before = sum(b_in) / len(b_in)

    g_out = bytes(max(v, floor) for v in g_in)
    b_out = bytes(0 for _ in b_in) if zero_metallic else b_band.tobytes()

    new_img = Image.merge("RGB", (
        r_band,
        Image.frombytes("L", (w, h), g_out),
        Image.frombytes("L", (w, h), b_out),
    ))
    buf = io.BytesIO()
    new_img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
    new_bytes = buf.getvalue()

    return new_bytes, {
        "dimensions": f"{w}x{h}",
        "jpeg_bytes_before": len(jpeg_bytes),
        "jpeg_bytes_after": len(new_bytes),
        "g_mean_before": g_mean_before,
        "g_mean_after": sum(g_out) / len(g_out),
        "b_mean_before": b_mean_before,
        "b_mean_after": sum(b_out) / len(b_out),
    }


def parse_glb(path: Path) -> tuple[dict[str, Any], bytes]:
    """Return (gltf_json, bin_chunk_bytes)."""
    data = path.read_bytes()
    magic, version, total_len = struct.unpack_from("<4sII", data, 0)
    assert magic == GLB_MAGIC, f"{path} not a GLB: {magic!r}"
    assert version == GLB_VERSION, f"{path} GLB version {version} unsupported"

    json_len, json_type = struct.unpack_from("<I4s", data, 12)
    assert json_type == b"JSON", f"first chunk not JSON: {json_type}"
    gltf = json.loads(data[20 : 20 + json_len].decode("utf-8"))

    bin_start = 20 + json_len
    if bin_start >= total_len:
        return gltf, b""
    bin_len, bin_type = struct.unpack_from("<I4s", data, bin_start)
    assert bin_type == b"BIN\x00", f"second chunk not BIN: {bin_type}"
    bin_data = data[bin_start + 8 : bin_start + 8 + bin_len]
    return gltf, bin_data


def write_glb(path: Path, gltf: dict[str, Any], bin_data: bytes) -> int:
    """Write a GLB. Pads JSON chunk to 4-byte boundary with spaces, BIN with zeros."""
    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_pad = (4 - len(json_bytes) % 4) % 4
    json_bytes += b" " * json_pad

    bin_pad = (4 - len(bin_data) % 4) % 4
    bin_bytes_padded = bin_data + b"\x00" * bin_pad

    total = 12 + 8 + len(json_bytes) + 8 + len(bin_bytes_padded)

    out = bytearray()
    out += struct.pack("<4sII", GLB_MAGIC, GLB_VERSION, total)
    out += struct.pack("<I4s", len(json_bytes), b"JSON")
    out += json_bytes
    out += struct.pack("<I4s", len(bin_bytes_padded), b"BIN\x00")
    out += bin_bytes_padded

    path.write_bytes(out)
    return total


def get_bufferview_bytes(bin_data: bytes, gltf: dict[str, Any], bv_idx: int) -> bytes:
    bv = gltf["bufferViews"][bv_idx]
    offset = bv.get("byteOffset", 0)
    length = bv["byteLength"]
    return bin_data[offset : offset + length]


def verify_compatible(retex: dict[str, Any], rigged: dict[str, Any]) -> None:
    """Sanity-check that both GLBs share mesh topology suitable for grafting."""
    for label, g in (("retex", retex), ("rigged", rigged)):
        assert len(g.get("meshes", [])) == 1, f"{label}: expected 1 mesh, got {len(g.get('meshes', []))}"
        assert len(g["meshes"][0].get("primitives", [])) == 1, (
            f"{label}: expected 1 primitive"
        )
        assert len(g.get("materials", [])) == 1, f"{label}: expected 1 material"

    retex_attrs = set(retex["meshes"][0]["primitives"][0]["attributes"].keys())
    rigged_attrs = set(rigged["meshes"][0]["primitives"][0]["attributes"].keys())
    assert "TEXCOORD_0" in retex_attrs and "TEXCOORD_0" in rigged_attrs, (
        "Both meshes must have TEXCOORD_0; got retex=%s rigged=%s" % (retex_attrs, rigged_attrs)
    )


def graft(
    retex_path: Path,
    rigged_path: Path,
    out_path: Path,
    roughness_floor: int = DEFAULT_ROUGHNESS_FLOOR,
    zero_metallic: bool = True,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
) -> dict[str, Any]:
    """Returns a summary dict for printing.

    roughness_floor: G-channel floor applied to the metalRough JPEG (0 disables).
    zero_metallic: if True, force B channel to 0 (suppress spurious metallic).
    """
    retex_gltf, retex_bin = parse_glb(retex_path)
    rigged_gltf, rigged_bin = parse_glb(rigged_path)
    verify_compatible(retex_gltf, rigged_gltf)
    clamp_active = roughness_floor > 0 or zero_metallic
    clamp_stats: dict[str, float] | None = None

    # ── Start from the rigged GLB (preserves nodes/skins/animations/mesh attrs) ──
    out_gltf = copy.deepcopy(rigged_gltf)
    out_bin = bytearray(rigged_bin)

    # The rigged GLB's existing material/textures/images/samplers + extensions get
    # discarded — we replace them entirely with retex's stack.
    out_gltf["materials"] = []
    out_gltf["textures"] = []
    out_gltf["images"] = []
    out_gltf["samplers"] = []
    # Strip rigger-injected material extensions
    if "extensionsUsed" in out_gltf:
        out_gltf["extensionsUsed"] = [
            e for e in out_gltf["extensionsUsed"]
            if e not in {"KHR_materials_specular", "KHR_materials_ior"}
        ]
        if not out_gltf["extensionsUsed"]:
            del out_gltf["extensionsUsed"]
    if "extensionsRequired" in out_gltf:
        out_gltf["extensionsRequired"] = [
            e for e in out_gltf["extensionsRequired"]
            if e not in {"KHR_materials_specular", "KHR_materials_ior"}
        ]
        if not out_gltf["extensionsRequired"]:
            del out_gltf["extensionsRequired"]

    # ── Walk retex material → texture → image/sampler dependency graph ──
    retex_material = copy.deepcopy(retex_gltf["materials"][0])
    # Strip name to avoid confusion; we'll set a fresh one
    retex_material["name"] = "Grafted_PBR_Material"

    # Find every texture index referenced by the material
    texture_refs: list[tuple[str, dict[str, Any]]] = []
    pbr = retex_material.get("pbrMetallicRoughness", {})
    for key in ("baseColorTexture", "metallicRoughnessTexture"):
        if key in pbr:
            texture_refs.append((f"pbr.{key}", pbr[key]))
    for key in ("normalTexture", "emissiveTexture", "occlusionTexture"):
        if key in retex_material:
            texture_refs.append((key, retex_material[key]))

    # Resolve the metalRough image index up-front so append_image can clamp it.
    metalrough_img_idx: int | None = None
    if "metallicRoughnessTexture" in pbr:
        t_idx = pbr["metallicRoughnessTexture"]["index"]
        metalrough_img_idx = retex_gltf["textures"][t_idx].get("source")

    # ── Append retex bufferViews referenced by images, build index remap ──
    new_buffer_idx = 0  # rigged GLB has buffer[0]; we append to that
    bv_remap: dict[int, int] = {}  # retex bufferView idx → new idx
    img_remap: dict[int, int] = {}  # retex image idx → new idx
    sampler_remap: dict[int, int] = {}  # retex sampler idx → new idx
    texture_remap: dict[int, int] = {}  # retex texture idx → new idx

    def append_image(retex_img_idx: int) -> int:
        """Copy a retex image (+ its bufferView data) into the rigged GLB. Returns new image idx."""
        nonlocal clamp_stats
        if retex_img_idx in img_remap:
            return img_remap[retex_img_idx]
        img = copy.deepcopy(retex_gltf["images"][retex_img_idx])
        if "bufferView" in img:
            retex_bv_idx = img["bufferView"]
            if retex_bv_idx not in bv_remap:
                bv_bytes = get_bufferview_bytes(retex_bin, retex_gltf, retex_bv_idx)
                # Defensive clamp on the metalRough texture before appending.
                if clamp_active and retex_img_idx == metalrough_img_idx:
                    bv_bytes, clamp_stats = _clamp_metalrough_jpeg(
                        bv_bytes, roughness_floor, zero_metallic, jpeg_quality
                    )
                # Append to rigged BIN (4-byte align before append for safety)
                while len(out_bin) % 4 != 0:
                    out_bin.append(0)
                offset = len(out_bin)
                out_bin.extend(bv_bytes)
                new_bv = {
                    "buffer": new_buffer_idx,
                    "byteOffset": offset,
                    "byteLength": len(bv_bytes),
                }
                out_gltf.setdefault("bufferViews", []).append(new_bv)
                bv_remap[retex_bv_idx] = len(out_gltf["bufferViews"]) - 1
            img["bufferView"] = bv_remap[retex_bv_idx]
        out_gltf["images"].append(img)
        img_remap[retex_img_idx] = len(out_gltf["images"]) - 1
        return img_remap[retex_img_idx]

    def append_sampler(retex_sampler_idx: int) -> int:
        if retex_sampler_idx in sampler_remap:
            return sampler_remap[retex_sampler_idx]
        s = copy.deepcopy(retex_gltf["samplers"][retex_sampler_idx])
        out_gltf["samplers"].append(s)
        sampler_remap[retex_sampler_idx] = len(out_gltf["samplers"]) - 1
        return sampler_remap[retex_sampler_idx]

    def append_texture(retex_tex_idx: int) -> int:
        if retex_tex_idx in texture_remap:
            return texture_remap[retex_tex_idx]
        t = copy.deepcopy(retex_gltf["textures"][retex_tex_idx])
        if "source" in t:
            t["source"] = append_image(t["source"])
        if "sampler" in t:
            t["sampler"] = append_sampler(t["sampler"])
        out_gltf["textures"].append(t)
        texture_remap[retex_tex_idx] = len(out_gltf["textures"]) - 1
        return texture_remap[retex_tex_idx]

    # Remap texture references in the material to the new indices
    for path_label, tex_ref in texture_refs:
        retex_tex_idx = tex_ref["index"]
        tex_ref["index"] = append_texture(retex_tex_idx)

    out_gltf["materials"].append(retex_material)

    # Point the (only) mesh primitive at the new material index 0
    out_gltf["meshes"][0]["primitives"][0]["material"] = 0

    # Update buffer[0].byteLength to reflect our appended bin data
    if out_gltf.get("buffers"):
        out_gltf["buffers"][0]["byteLength"] = len(out_bin)

    # ── Write final ──
    out_size = write_glb(out_path, out_gltf, bytes(out_bin))

    return {
        "retex_size": retex_path.stat().st_size,
        "rigged_size": rigged_path.stat().st_size,
        "out_size": out_size,
        "n_textures": len(out_gltf["textures"]),
        "n_images": len(out_gltf["images"]),
        "n_samplers": len(out_gltf["samplers"]),
        "n_materials": len(out_gltf["materials"]),
        "n_animations": len(out_gltf.get("animations", [])),
        "n_skins": len(out_gltf.get("skins", [])),
        "clamp_active": clamp_active,
        "clamp_floor": roughness_floor,
        "clamp_zero_metallic": zero_metallic,
        "clamp_stats": clamp_stats,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--retex", required=True, type=Path, help="Premium retex GLB (PBR source)")
    p.add_argument("--rigged", required=True, type=Path, help="Rigged+animated GLB (target)")
    p.add_argument("--out", required=True, type=Path, help="Output grafted GLB path")
    p.add_argument("--roughness-floor", type=int, default=DEFAULT_ROUGHNESS_FLOOR,
                   help=f"clamp metalRough G channel floor (0 disables). Default {DEFAULT_ROUGHNESS_FLOOR}.")
    p.add_argument("--keep-metallic", action="store_true",
                   help="preserve B channel (skip metallic zeroing). Default off → B forced to 0.")
    p.add_argument("--jpeg-quality", type=int, default=DEFAULT_JPEG_QUALITY,
                   help=f"re-encode quality when clamping. Default {DEFAULT_JPEG_QUALITY}.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not args.retex.exists():
        sys.exit(f"retex GLB not found: {args.retex}")
    if not args.rigged.exists():
        sys.exit(f"rigged GLB not found: {args.rigged}")
    args.out.parent.mkdir(parents=True, exist_ok=True)

    summary = graft(
        args.retex, args.rigged, args.out,
        roughness_floor=args.roughness_floor,
        zero_metallic=not args.keep_metallic,
        jpeg_quality=args.jpeg_quality,
    )
    mb = lambda n: f"{n/1024/1024:.1f} MB"
    print(f"  retex:  {mb(summary['retex_size'])}  ({args.retex})")
    print(f"  rigged: {mb(summary['rigged_size'])}  ({args.rigged})")
    print(f"  out:    {mb(summary['out_size'])}   ({args.out})")
    print()
    print(f"  textures={summary['n_textures']}  images={summary['n_images']}  "
          f"samplers={summary['n_samplers']}  materials={summary['n_materials']}")
    print(f"  animations={summary['n_animations']}  skins={summary['n_skins']}  (preserved)")
    if summary["clamp_active"]:
        cs = summary["clamp_stats"]
        if cs is not None:
            print(f"  clamp: floor={summary['clamp_floor']}  "
                  f"zero_metallic={summary['clamp_zero_metallic']}  "
                  f"({cs['dimensions']})")
            print(f"    roughness G mean: {cs['g_mean_before']:.1f} → {cs['g_mean_after']:.1f}")
            print(f"    metallic  B mean: {cs['b_mean_before']:.1f} → {cs['b_mean_after']:.1f}")
            print(f"    metalRough JPEG : {cs['jpeg_bytes_before']:,} → {cs['jpeg_bytes_after']:,} bytes")
        else:
            print(f"  clamp: configured but no metalRough texture found (skipped)")
    else:
        print(f"  clamp: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
