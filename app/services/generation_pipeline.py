import asyncio
import base64
import logging
import shutil
import time
from pathlib import Path

import cv2

from app.config import AVATARS_DIR, settings
from app.services.meshy_client import (
    MeshyDownloadError,
    MeshyJobError,
    download_retexture_glb,
    extract_glb_url,
    is_dummy_mode as meshy_is_dummy_mode,
)
from app.services.meshy_client import poll_until_complete as meshy_poll_until_complete
from app.services.meshy_client import submit_retexture
from app.services.portraitizer import portraitize
from app.services.runpod_client import (
    GlbDownloadError,
    RunpodJobError,
    delete_remote_glb,
    download_glb,
    poll_until_complete,
    submit_job,
)


log = logging.getLogger(__name__)


async def _portraitize_async(jpeg_bytes: bytes) -> bytes:
    # TEST MODE: when settings.test_portrait_override is set, skip the OpenAI call
    # entirely and feed a pre-cached portrait directly into the TRELLIS pipeline.
    # Used to test end-to-end Quest spawn flow while OpenAI billing is hard-limited.
    # Status timing (portraitizing -> generating) is preserved for the spawn ritual.
    if settings.test_portrait_override:
        p = Path(settings.test_portrait_override)
        if not p.is_absolute():
            # Resolve relative to repo root (two dirs above app/services/).
            p = Path(__file__).resolve().parent.parent.parent / p
        log.warning("TEST_PORTRAIT_OVERRIDE active — skipping OpenAI, using %s", p)
        return p.read_bytes()
    return await asyncio.to_thread(portraitize, jpeg_bytes)


async def process_task(
    task_id: str,
    averaged_jpeg: bytes,
    scan_dir: Path,
    task_record: dict,
) -> None:
    """Background pipeline: portraitize -> runpod submit -> poll -> download -> delete.

    Mutates task_record in place to communicate progress/status to /status route.
    """
    try:
        task_record["status"] = "portraitizing"
        t1 = time.perf_counter()
        portrait_bytes = await _portraitize_async(averaged_jpeg)
        log.info(
            "[task %s] portraitize elapsed=%.2fs bytes=%d",
            task_id, time.perf_counter() - t1, len(portrait_bytes),
        )
        (scan_dir / "portrait.png").write_bytes(portrait_bytes)
        task_record["portrait_path"] = str(scan_dir / "portrait.png")

        image_b64 = base64.b64encode(portrait_bytes).decode("ascii")

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
        runpod_job_id = await submit_job(image_b64)
        task_record["job_id"] = runpod_job_id
        task_record["last_runpod_status"] = "IN_QUEUE"
        log.info(
            "[task %s] submitted job=%s elapsed=%.2fs",
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
        try:
            t5 = time.perf_counter()
            retex_task_id = await submit_retexture(
                model_url=model_url,
                image_style_url=portrait_url,
                ai_model="meshy-6",
                enable_pbr=True,
                enable_original_uv=False,   # False = Meshy regenerates proper UV unwrap (matches web UI)
                remove_lighting=True,
                hd_texture=True,            # 4K base color — meshy-6 + Pro plan
                target_formats=["glb"],     # Only GLB — skip fbx/obj/usdz/stl (faster)
            )
            task_record["meshy_retexture_id"] = retex_task_id
            log.info(
                "[task %s] meshy retexture submitted id=%s dummy=%s elapsed=%.2fs",
                task_id, retex_task_id, meshy_is_dummy_mode(), time.perf_counter() - t5,
            )

            t6 = time.perf_counter()
            retex_task = await meshy_poll_until_complete(retex_task_id)
            log.info(
                "[task %s] meshy retexture completed elapsed=%.2fs",
                task_id, time.perf_counter() - t6,
            )

            clean_url = extract_glb_url(retex_task)
            t7 = time.perf_counter()
            clean_size = await download_retexture_glb(clean_url, final_path)
            log.info(
                "[task %s] clean glb downloaded -> %s (%d bytes, %.2fs)",
                task_id, final_path.name, clean_size, time.perf_counter() - t7,
            )

            # Cleanup intermediates — Quest only needs the final clean GLB.
            for p in (trellis_path, portrait_staged):
                try:
                    p.unlink()
                except OSError:
                    pass

            task_record["status"] = "complete"
            task_record["glb_path"] = str(final_path)
            task_record["glb_size_bytes"] = clean_size

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
