import asyncio
import base64
import functools
import logging
import shutil
import sys
import time
from pathlib import Path

import cv2
import httpx

from app.config import AVATARS_DIR, settings
from app.services.meshy_animation_client import (
    extract_rigged_glb_url,
    poll_rigging_until_complete,
    submit_rigging,
)
from app.services.meshy_client import (
    MeshyDownloadError,
    MeshyJobError,
    download_retexture_glb,
    extract_glb_url,
    is_dummy_mode as meshy_is_dummy_mode,
    run_with_transient_retry,
)
from app.services.meshy_client import poll_until_complete as meshy_poll_until_complete
from app.services.meshy_client import submit_retexture
from app.services.hunyuan_client import (
    poll_until_complete as hunyuan_poll,
)
from app.services.hunyuan_client import (
    submit_job as hunyuan_submit,
)
from app.services.portraitizer import portraitize, portraitize_dual
from app.services.runpod_client import (
    GlbDownloadError,
    RunpodJobError,
    delete_remote_glb,
    download_glb,
    poll_until_complete,
    submit_job,
)
from app.services.view_synthesizer import synthesize_views_grid

# tools/graft_pbr_materials.py — restores PBR materials onto rigged GLB
# (Meshy rigging strips the metallic/roughness/normal/emissive textures;
# graft re-bakes them from the retex source). Imported lazily by adding
# the repo root to sys.path the first time it's needed.
_GRAFT_FN = None


def _graft_pbr():
    global _GRAFT_FN
    if _GRAFT_FN is not None:
        return _GRAFT_FN
    repo_root = Path(__file__).resolve().parent.parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from tools.graft_pbr_materials import graft  # type: ignore[import-not-found]
    _GRAFT_FN = graft
    return _GRAFT_FN


log = logging.getLogger(__name__)


def _resolve_test_portrait_override() -> bytes | None:
    """Shared bypass for both single and dual portraitize paths."""
    if not settings.test_portrait_override:
        return None
    p = Path(settings.test_portrait_override)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent.parent / p
    log.warning("TEST_PORTRAIT_OVERRIDE active — skipping OpenAI, using %s", p)
    return p.read_bytes()


async def _portraitize_async(jpeg_bytes: bytes) -> bytes:
    # TEST MODE: when settings.test_portrait_override is set, skip the OpenAI call
    # entirely and feed a pre-cached portrait directly into the TRELLIS pipeline.
    # Used to test end-to-end Quest spawn flow while OpenAI billing is hard-limited.
    # Status timing (portraitizing -> generating) is preserved for the spawn ritual.
    override = _resolve_test_portrait_override()
    if override is not None:
        return override
    return await asyncio.to_thread(portraitize, jpeg_bytes)


async def _portraitize_async_dual(body_jpeg: bytes, face_jpeg: bytes) -> bytes:
    """Dual-input portraitizer (body + face) via gpt-image-2. Honors override."""
    override = _resolve_test_portrait_override()
    if override is not None:
        return override
    return await asyncio.to_thread(portraitize_dual, body_jpeg, face_jpeg)


async def process_task(
    task_id: str,
    body_jpeg: bytes,
    scan_dir: Path,
    task_record: dict,
    *,
    face_jpeg: bytes | None = None,
) -> None:
    """Background pipeline: portraitize -> runpod submit -> poll -> download -> delete.

    If `face_jpeg` is provided, runs the dual-input portraitizer (gpt-image-2);
    otherwise the legacy single-input path (gpt-image-1.5). All downstream
    stages (RunPod, Meshy Retex, Meshy Rigging, graft) are mode-agnostic.

    Mutates task_record in place to communicate progress/status to /status route.
    """
    try:
        # DRY-RUN: bail after the route has already saved frames + picked sharpest.
        # Marks the task complete so /status returns "complete" without firing any
        # downstream cost (OpenAI / RunPod / Meshy). Quest's poll will end cleanly.
        if settings.test_dry_run:
            log.warning(
                "[task %s] TEST_DRY_RUN active — skipping portraitize+runpod+meshy. "
                "Inputs saved at %s. Mode=%s",
                task_id, scan_dir,
                "dual" if face_jpeg is not None else "single",
            )
            task_record["status"] = "complete"
            task_record["portrait_mode"] = "dual" if face_jpeg is not None else "single"
            task_record["dry_run"] = True
            return

        task_record["status"] = "portraitizing"
        t1 = time.perf_counter()
        if face_jpeg is not None:
            portrait_bytes = await _portraitize_async_dual(body_jpeg, face_jpeg)
            task_record["portrait_mode"] = "dual"
        else:
            portrait_bytes = await _portraitize_async(body_jpeg)
            task_record["portrait_mode"] = "single"
        log.info(
            "[task %s] portraitize elapsed=%.2fs bytes=%d",
            task_id, time.perf_counter() - t1, len(portrait_bytes),
        )
        (scan_dir / "portrait.png").write_bytes(portrait_bytes)
        task_record["portrait_path"] = str(scan_dir / "portrait.png")

        # Cinematic delay — gives the P2a vortex its full window when the
        # portraitizer is bypassed (real OpenAI takes 30-60s; bypass takes ms).
        # Set TEST_PORTRAIT_DELAY_S=30 in .env to enable. 0 = skip.
        if settings.test_portrait_delay_s > 0:
            log.info(
                "[task %s] TEST_PORTRAIT_DELAY_S=%.1fs — sleeping before runpod submit",
                task_id, settings.test_portrait_delay_s,
            )
            await asyncio.sleep(settings.test_portrait_delay_s)

        task_record["status"] = "generating"
        t2 = time.perf_counter()

        if settings.use_hunyuan:
            # Hunyuan multi-view path: synthesize 4 turnaround views from the
            # single front portrait, then submit all 4 to the Hunyuan endpoint
            # (itd7oz9wexb1oo). Downstream Meshy retex/rig/graft is identical
            # — same S3 volume, same Meshy flow.
            log.info("[task %s] USE_HUNYUAN=true — routing via Hunyuan endpoint", task_id)
            tv = time.perf_counter()
            views = await asyncio.to_thread(synthesize_views_grid, portrait_bytes)
            log.info(
                "[task %s] view-gen elapsed=%.2fs views=%s",
                task_id, time.perf_counter() - tv, list(views.keys()),
            )
            for view_name, png in views.items():
                (scan_dir / f"view_{view_name}.png").write_bytes(png)

            runpod_job_id = await hunyuan_submit(views)
            task_record["pipeline_mode"] = "hunyuan"
            task_record["job_id"] = runpod_job_id
            task_record["last_runpod_status"] = "IN_QUEUE"
            log.info(
                "[task %s] submitted Hunyuan job=%s elapsed=%.2fs",
                task_id, runpod_job_id, time.perf_counter() - t2,
            )
            t3 = time.perf_counter()
            output = await hunyuan_poll(runpod_job_id)
        else:
            # TRELLIS path (production default).
            image_b64 = base64.b64encode(portrait_bytes).decode("ascii")
            runpod_job_id = await submit_job(image_b64)
            task_record["pipeline_mode"] = "trellis"
            task_record["job_id"] = runpod_job_id
            task_record["last_runpod_status"] = "IN_QUEUE"
            log.info(
                "[task %s] submitted TRELLIS job=%s elapsed=%.2fs",
                task_id, runpod_job_id, time.perf_counter() - t2,
            )
            t3 = time.perf_counter()
            output = await poll_until_complete(runpod_job_id)

        task_record["last_runpod_status"] = "COMPLETED"
        log.info(
            "[task %s] runpod completed elapsed=%.2fs output_keys=%s",
            task_id, time.perf_counter() - t3, list(output.keys()),
        )

        glb_volume_path = output.get("glb_volume_path")
        if not glb_volume_path:
            raise RunpodJobError(
                f"runpod output missing glb_volume_path: keys={list(output.keys())}"
            )

        # Download TRELLIS GLB to STAGING name. Quest never sees this — it's the
        # plastic-textured intermediate that Meshy Retexture cleans up.
        trellis_path = AVATARS_DIR / f"{task_id}_trellis.glb"
        final_path = AVATARS_DIR / f"{task_id}.glb"
        t4 = time.perf_counter()
        trellis_size = await download_glb(glb_volume_path, trellis_path)
        log.info(
            "[task %s] trellis glb downloaded -> %s (%d bytes, %.2fs)",
            task_id, trellis_path.name, trellis_size, time.perf_counter() - t4,
        )
        await delete_remote_glb(glb_volume_path)
        task_record["trellis_glb_path"] = str(trellis_path)

        # If MESHY_PUBLIC_HOST is unset, we cannot stage the GLB+portrait for
        # Meshy to fetch — fall back to serving the TRELLIS plastic version.
        meshy_host = settings.meshy_public_host.strip()
        if not meshy_host:
            log.warning(
                "[task %s] MESHY_PUBLIC_HOST not set — skipping Meshy Retexture, "
                "serving TRELLIS plastic as final",
                task_id,
            )
            shutil.move(str(trellis_path), str(final_path))
            task_record["status"] = "complete"
            task_record["glb_path"] = str(final_path)
            task_record["glb_size_bytes"] = trellis_size
            return

        # Stage portrait at /avatars/{task_id}_portrait.png so Meshy can fetch it.
        portrait_src = scan_dir / "portrait.png"
        portrait_staged = AVATARS_DIR / f"{task_id}_portrait.png"
        shutil.copy2(portrait_src, portrait_staged)
        log.info("[task %s] portrait staged -> %s", task_id, portrait_staged.name)

        # Tolerate MESHY_PUBLIC_HOST with or without scheme prefix.
        if meshy_host.startswith(("http://", "https://")):
            base = meshy_host.rstrip("/")
        else:
            scheme = "http" if meshy_host.startswith(("localhost", "127.")) else "https"
            base = f"{scheme}://{meshy_host.rstrip('/')}"
        model_url = f"{base}/avatars/{trellis_path.name}"
        portrait_url = f"{base}/avatars/{portrait_staged.name}"

        task_record["status"] = "retexturing"

        def _note_retex_submit(rid: str) -> None:
            task_record["meshy_retexture_id"] = rid
            log.info(
                "[task %s] meshy retexture submitted id=%s dummy=%s",
                task_id, rid, meshy_is_dummy_mode(),
            )

        try:
            t5 = time.perf_counter()
            # Retries the whole submit+poll on a transient service_unavailable
            # blip (Meshy's "please retry") so one unlucky 2s window can't doom
            # the avatar to the unpainted fallback below.
            retex_task = await run_with_transient_retry(
                functools.partial(
                    submit_retexture,
                    model_url=model_url,
                    image_style_url=portrait_url,
                    ai_model="meshy-6",
                    enable_pbr=True,
                    enable_original_uv=False,   # False = Meshy regenerates proper UV unwrap (matches web UI)
                    remove_lighting=True,
                    hd_texture=True,            # 4K base color — meshy-6 + Pro plan
                    target_formats=["glb"],     # Only GLB — skip fbx/obj/usdz/stl (faster)
                ),
                meshy_poll_until_complete,
                label="retexture",
                on_submit=_note_retex_submit,
            )
            log.info(
                "[task %s] meshy retexture completed elapsed=%.2fs",
                task_id, time.perf_counter() - t5,
            )

            clean_url = extract_glb_url(retex_task)
            t7 = time.perf_counter()
            clean_size = await download_retexture_glb(clean_url, final_path)
            log.info(
                "[task %s] clean glb downloaded -> %s (%d bytes, %.2fs)",
                task_id, final_path.name, clean_size, time.perf_counter() - t7,
            )

            # Cleanup retex intermediates (TRELLIS + portrait staging) — the
            # rigging step below uses `final_path` (the retex GLB) as input,
            # so we keep that file in place.
            for p in (trellis_path, portrait_staged):
                try:
                    p.unlink()
                except OSError:
                    pass

            # ── Phase 5: Meshy Rigging ──────────────────────────────────
            # The retex GLB is now at final_path = AVATARS_DIR / {task_id}.glb.
            # That URL is what Quest will fetch during Stage 2 scan reveal
            # (status="rigging" tells the UI to fire Stage 2 — the retex
            # avatar IS the Stage 2 form). We submit Meshy Rigging using the
            # retex URL as model_url, get back a rigged GLB, then graft the
            # premium PBR materials back onto the rigged mesh, and OVERWRITE
            # final_path with the final rigged+grafted result. By the time we
            # set status="complete", final_path contains the rigged form
            # that Stage 3 will fetch.
            #
            # NO animation step — we skip /animations entirely. Unity-side
            # breath driver (RiggedAvatarBreath) handles aliveness procedurally
            # via Spine02 oscillation on the rigged skeleton.
            task_record["status"] = "rigging"
            try:
                retex_public_url = f"{base}/avatars/{final_path.name}"

                def _note_rig_submit(rid: str) -> None:
                    task_record["meshy_rigging_id"] = rid
                    log.info("[task %s] meshy rigging submitted id=%s", task_id, rid)

                t8 = time.perf_counter()
                # Same transient-retry guard as retex — a service_unavailable
                # blip here would otherwise fall back to the un-rigged retex.
                rig_task = await run_with_transient_retry(
                    functools.partial(
                        submit_rigging,
                        model_url=retex_public_url,
                        height_meters=1.7,
                    ),
                    poll_rigging_until_complete,
                    label="rigging",
                    on_submit=_note_rig_submit,
                )
                log.info(
                    "[task %s] meshy rigging completed elapsed=%.2fs",
                    task_id, time.perf_counter() - t8,
                )

                rigged_remote_url = extract_rigged_glb_url(rig_task)
                rigged_raw_path = AVATARS_DIR / f"{task_id}_rigged_raw.glb"

                t10 = time.perf_counter()
                async with httpx.AsyncClient(timeout=180.0) as c:
                    r = await c.get(rigged_remote_url, follow_redirects=True)
                if r.status_code != 200:
                    raise MeshyDownloadError(
                        f"rigged GLB download HTTP {r.status_code} from {rigged_remote_url}"
                    )
                if r.content[:4] != b"glTF":
                    raise MeshyDownloadError(
                        f"rigged GLB not a glTF — magic={r.content[:4]!r}"
                    )
                rigged_raw_path.write_bytes(r.content)
                rigged_raw_size = rigged_raw_path.stat().st_size
                log.info(
                    "[task %s] rigged glb downloaded -> %s (%d bytes, %.2fs)",
                    task_id, rigged_raw_path.name, rigged_raw_size,
                    time.perf_counter() - t10,
                )

                # Graft PBR from the retex (final_path) onto rigged_raw_path,
                # write the result to a temp path. Then atomically move it
                # over final_path so Quest's next fetch returns the rigged
                # version. Graft runs CPU-bound (.glb parse + buffer copy);
                # use to_thread to avoid blocking the event loop.
                grafted_temp_path = AVATARS_DIR / f"{task_id}_grafted_temp.glb"
                t11 = time.perf_counter()
                graft_fn = _graft_pbr()
                graft_summary = await asyncio.to_thread(
                    graft_fn, final_path, rigged_raw_path, grafted_temp_path,
                )
                log.info(
                    "[task %s] graft pbr complete -> %s (%d bytes, %.2fs)",
                    task_id, grafted_temp_path.name,
                    graft_summary.get("out_size", 0), time.perf_counter() - t11,
                )

                # Atomic overwrite: final_path goes from retex → rigged+grafted.
                shutil.move(str(grafted_temp_path), str(final_path))
                final_size = final_path.stat().st_size

                # Cleanup
                try:
                    rigged_raw_path.unlink()
                except OSError:
                    pass

                task_record["status"] = "complete"
                task_record["glb_path"] = str(final_path)
                task_record["glb_size_bytes"] = final_size
                log.info(
                    "[task %s] PIPELINE COMPLETE — final rigged+grafted glb at %s (%d bytes)",
                    task_id, final_path.name, final_size,
                )

            except (MeshyJobError, MeshyDownloadError, TimeoutError, httpx.HTTPError) as e:
                # Rigging failed (Meshy error, our timeout, or any httpx-level
                # network issue including httpcore.ReadTimeout). Fall back to
                # serving the retex GLB as final. Quest's Stage 3 will fetch
                # the same {task_id}.glb URL and get the retex (no skeleton).
                # RiggedAvatarBreath will fail to resolve Spine02 → no breath,
                # but the rest of Stage 3 still fires. Better than failed.
                log.warning(
                    "[task %s] meshy rigging failed (%s: %s) — serving retex as final",
                    task_id, type(e).__name__, e,
                )
                task_record["status"] = "complete"
                task_record["glb_path"] = str(final_path)
                task_record["glb_size_bytes"] = clean_size
                task_record["rigging_error"] = f"{type(e).__name__}: {e}"

        except (MeshyJobError, MeshyDownloadError, TimeoutError) as e:
            log.warning(
                "[task %s] meshy retexture failed (%s) — falling back to TRELLIS plastic",
                task_id, e,
            )
            shutil.move(str(trellis_path), str(final_path))
            task_record["status"] = "complete"
            task_record["glb_path"] = str(final_path)
            task_record["glb_size_bytes"] = trellis_size
            task_record["meshy_error"] = str(e)

    except (RunpodJobError, GlbDownloadError, TimeoutError) as e:
        log.exception("[task %s] failed: %s", task_id, e)
        task_record["status"] = "failed"
        task_record["error"] = str(e)
    except Exception as e:
        log.exception("[task %s] unexpected error: %s", task_id, e)
        task_record["status"] = "failed"
        task_record["error"] = f"{type(e).__name__}: {e}"
