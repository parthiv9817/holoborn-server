"""Insert two real eyeball spheres into a rigged Hunyuan/Meshy GLB.

Prototype (single-avatar) probe to test whether real spherical eyes fix the
"flat painted doll-eye" look. Geometry-only fix that renders in the CURRENT
Quest APK (standard glTF PBR + the scene's IBL gives the specular catchlight):

  - UV-sphere eyeball, planar +Z UV projection (iris decals the front)
  - procedural iris/sclera texture (radial fibers, limbal ring, pupil, catchlight)
  - low-roughness PBR material so image-based lighting produces a live highlight
  - two nodes parented to the `Head` bone (via inverse-bind matrix) so the eyes
    ride the breathing head-bob; both reuse ONE eyeball mesh

All placement is CLI-tunable for the Y-test nudge loop. Pipeline integration
is intentionally deferred — this operates on a staged GLB only.

Run:
    .venv/bin/python tools/insert_eyes.py \\
        --in results/avatars/test_rigged.glb --out results/avatars/test_rigged.glb \\
        --ipd 0.063 --eye-y 1.59 --eye-z 0.09 --radius 0.013 --roughness 0.12
"""
from __future__ import annotations

import argparse
import io
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from pygltflib import (GLTF2, Accessor, BufferView, Image as GLTFImage, Material,
                       Mesh, Node, PbrMetallicRoughness, Primitive, Sampler,
                       Texture, TextureInfo)

HEAD_BONE = "Head"
F32, U16 = 5126, 5123
VEC3, VEC2, SCALAR = "VEC3", "VEC2", "SCALAR"
ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER = 34962, 34963


def make_eye_texture(size=512, iris_rgb=(64, 42, 26)) -> bytes:
    """Procedural eye: warm sclera, fibrous iris, limbal ring, pupil, catchlight."""
    cx = cy = size / 2.0
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    rad = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (size * 0.5)  # 0 center .. 1 edge
    ang = np.arctan2(yy - cy, xx - cx)

    # sclera: near-white, warming only at the far edges (corners of the eye)
    img = np.empty((size, size, 3), np.float32)
    img[:] = (246, 244, 241)
    edge = np.clip((rad - 0.62) * 2.6, 0, 1)[..., None]
    img += edge * np.array([2.0, -9.0, -7.0], np.float32)

    iris_r, pupil_r = 0.33, 0.15  # fractions of the half-size
    iris_rgb = np.array(iris_rgb, np.float32)
    # radial fiber noise + brightness falloff from pupil to limbus
    fibers = 0.5 + 0.5 * np.sin(ang * 110.0 + rad * 26.0)
    fibers = fibers * np.clip((rad - pupil_r) / (iris_r - pupil_r), 0, 1)
    iris_col = iris_rgb[None, None, :] * (0.62 + 0.55 * fibers[..., None])
    iris_mask = ((rad <= iris_r) & (rad > pupil_r))[..., None]
    img = np.where(iris_mask, iris_col, img)
    # limbal ring: dark band at the iris rim
    limbal = (np.abs(rad - iris_r) < 0.035) & (rad <= iris_r + 0.035)
    img[limbal] *= 0.35
    # pupil: black
    img[rad <= pupil_r] = (8, 8, 9)

    out = Image.fromarray(np.clip(img, 0, 255).astype("uint8"))
    out = out.filter(ImageFilter.GaussianBlur(0.6))
    # catchlight: small crisp window-reflection dot at the upper-left pupil rim
    d = ImageDraw.Draw(out)
    cl = size * 0.026
    ox, oy = cx - size * 0.06, cy - size * 0.10
    d.ellipse([ox - cl, oy - cl, ox + cl, oy + cl], fill=(250, 250, 248))
    out = out.filter(ImageFilter.GaussianBlur(0.7))
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def make_uv_sphere(radius: float, stacks=32, slices=48):
    """Sphere with planar +Z UVs (front of eyeball samples texture centre)."""
    pos, nrm, uv = [], [], []
    for i in range(stacks + 1):
        phi = math.pi * i / stacks
        for j in range(slices + 1):
            theta = 2 * math.pi * j / slices
            x, y, z = (math.sin(phi) * math.cos(theta), math.cos(phi),
                       math.sin(phi) * math.sin(theta))
            nrm.append((x, y, z))
            pos.append((x * radius, y * radius, z * radius))
            uv.append((0.5 + x * 0.5, 0.5 - y * 0.5))  # planar +Z decal
    idx = []
    w = slices + 1
    for i in range(stacks):
        for j in range(slices):
            a, b = i * w + j, i * w + j + 1
            c, dd = (i + 1) * w + j, (i + 1) * w + j + 1
            idx += [a, c, b, b, c, dd]
    return (np.array(pos, np.float32), np.array(nrm, np.float32),
            np.array(uv, np.float32), np.array(idx, np.uint16))


def _append(blob: bytearray, data: bytes) -> tuple[int, int]:
    while len(blob) % 4:
        blob.append(0)
    off = len(blob)
    blob.extend(data)
    return off, len(data)


def _bv(g, blob, data: bytes, target=None) -> int:
    off, ln = _append(blob, data)
    g.bufferViews.append(BufferView(buffer=0, byteOffset=off, byteLength=ln, target=target))
    return len(g.bufferViews) - 1


def _acc(g, bv, ctype, count, atype, **kw) -> int:
    g.accessors.append(Accessor(bufferView=bv, componentType=ctype, count=count, type=atype, **kw))
    return len(g.accessors) - 1


def insert_eyes(in_path, out_path, ipd, eye_y, eye_z, radius, roughness, iris_rgb):
    g = GLTF2().load(str(in_path))
    blob = bytearray(g.binary_blob())

    # --- Head bone world transform (bind pose) from inverse-bind matrices ---
    skin = g.skins[0]
    head_node = next(i for i, n in enumerate(g.nodes) if (n.name or "") == HEAD_BONE)
    jidx = skin.joints.index(head_node)
    iacc = g.accessors[skin.inverseBindMatrices]
    ibv = g.bufferViews[iacc.bufferView]
    ioff = (ibv.byteOffset or 0) + (iacc.byteOffset or 0)
    ibm = np.frombuffer(bytes(blob), np.float32, 16, ioff + jidx * 64).reshape(4, 4).T
    head_world = np.linalg.inv(ibm)

    # --- eyeball geometry (one mesh, reused by both eyes) ---
    pos, nrm, uv, idx = make_uv_sphere(radius)
    pos_bv = _bv(g, blob, pos.tobytes(), ARRAY_BUFFER)
    nrm_bv = _bv(g, blob, nrm.tobytes(), ARRAY_BUFFER)
    uv_bv = _bv(g, blob, uv.tobytes(), ARRAY_BUFFER)
    idx_bv = _bv(g, blob, idx.tobytes(), ELEMENT_ARRAY_BUFFER)
    pos_a = _acc(g, pos_bv, F32, len(pos), VEC3,
                 min=pos.min(0).tolist(), max=pos.max(0).tolist())
    nrm_a = _acc(g, nrm_bv, F32, len(nrm), VEC3)
    uv_a = _acc(g, uv_bv, F32, len(uv), VEC2)
    idx_a = _acc(g, idx_bv, U16, len(idx), SCALAR)

    # --- eye texture + material ---
    img_bv = _bv(g, blob, make_eye_texture(iris_rgb=iris_rgb))
    g.images.append(GLTFImage(bufferView=img_bv, mimeType="image/png"))
    g.samplers.append(Sampler(magFilter=9729, minFilter=9987, wrapS=33071, wrapT=33071))
    g.textures.append(Texture(source=len(g.images) - 1, sampler=len(g.samplers) - 1))
    g.materials.append(Material(
        name="HoloBorn_Eye", doubleSided=True,
        pbrMetallicRoughness=PbrMetallicRoughness(
            baseColorTexture=TextureInfo(index=len(g.textures) - 1),
            metallicFactor=0.0, roughnessFactor=roughness)))
    g.meshes.append(Mesh(primitives=[Primitive(
        attributes={"POSITION": pos_a, "NORMAL": nrm_a, "TEXCOORD_0": uv_a},
        indices=idx_a, material=len(g.materials) - 1)]))
    eye_mesh = len(g.meshes) - 1

    # --- two eye nodes parented to Head (local = inv(head_world) @ world) ---
    inv_head = np.linalg.inv(head_world)
    for side, sx in (("L", -1.0), ("R", +1.0)):
        world = np.eye(4, dtype=np.float32)
        world[:3, 3] = [sx * ipd / 2.0, eye_y, eye_z]
        local = inv_head @ world
        check = (head_world @ local)[:3, 3]
        assert np.allclose(check, world[:3, 3], atol=1e-4), f"{side} placement drift {check}"
        g.nodes.append(Node(name=f"HoloBorn_Eye_{side}", mesh=eye_mesh,
                            matrix=local.T.flatten().tolist()))
        g.nodes[head_node].children = (g.nodes[head_node].children or []) + [len(g.nodes) - 1]

    g.set_binary_blob(bytes(blob))
    g.buffers[0].byteLength = len(blob)
    g.save(str(out_path))
    print(f"[ok] eyes inserted -> {out_path} ({len(bytes(blob))/1e6:.1f} MB), "
          f"+{len(pos)} verts/eye, head=node[{head_node}] jointIdx={jidx}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--in", dest="inp", required=True, type=Path)
    ap.add_argument("--out", dest="out", required=True, type=Path)
    ap.add_argument("--ipd", type=float, default=0.063)
    ap.add_argument("--eye-y", type=float, default=1.59)
    ap.add_argument("--eye-z", type=float, default=0.09)
    ap.add_argument("--radius", type=float, default=0.013)
    ap.add_argument("--roughness", type=float, default=0.12)
    ap.add_argument("--iris", default="64,42,26", help="iris RGB, e.g. 64,42,26 (dark brown)")
    a = ap.parse_args()
    iris = tuple(int(v) for v in a.iris.split(","))
    insert_eyes(a.inp, a.out, a.ipd, a.eye_y, a.eye_z, a.radius, a.roughness, iris)


if __name__ == "__main__":
    main()
