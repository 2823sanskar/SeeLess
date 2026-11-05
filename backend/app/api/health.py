from fastapi import APIRouter
from sqlalchemy import text
from app.database import engine
from app.config import settings

router = APIRouter(prefix="/api", tags=["Health"])

@router.get("/health")
async def health_check():
    db_status = "connected"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"

    redis_status = "not_checked"
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL, socket_timeout=1)
        if r.ping():
            redis_status = "connected"
    except Exception:
        redis_status = "unavailable"

    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "database": db_status,
        "redis": redis_status
    }

