from fastapi import APIRouter
from sqlalchemy import text
from app.database import SessionLocal
from app.config import settings

router = APIRouter(prefix="/api", tags=["Health"])

@router.get("/health")
async def health_check():
    """Liveness probe - basic service health"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "database": "connected" if _check_db() else "error",
        "redis": "connected" if _check_redis() else "unavailable"
    }

@router.get("/health/ready")
async def readiness_check():
    """Readiness probe - verifies all dependencies for traffic routing"""
    checks = {
        "database": _check_db(),
        "redis": _check_redis(),
        "celery": _check_celery(),
        "gnani_api": _check_gnani_api()
    }
    all_healthy = all(checks.values())
    return {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks
    }

def _check_db() -> bool:
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return True
    except Exception:
        return False

def _check_redis() -> bool:
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL, socket_timeout=1)
        return r.ping()
    except Exception:
        return False

def _check_celery() -> bool:
    try:
        from app.workers.tasks import USING_CELERY
        import redis
        if USING_CELERY:
            r = redis.from_url(settings.REDIS_URL, socket_timeout=1)
            return r.exists("celery")
        return True
    except Exception:
        return False

def _check_gnani_api() -> bool:
    return bool(settings.GNANI_API_KEY and settings.GNANI_API_KEY != "your_gnani_api_key_here")

