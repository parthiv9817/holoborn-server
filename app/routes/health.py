import time

from fastapi import APIRouter, Request

from app.models.schemas import HealthResponse


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    state = request.app.state
    started_at = getattr(state, "started_at", time.time())
    frames = getattr(state, "frames_processed", 0)
    return HealthResponse(
        status="alive",
        frames_processed=frames,
        uptime_seconds=time.time() - started_at,
    )
