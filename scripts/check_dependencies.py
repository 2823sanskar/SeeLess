import sys
import os
import shutil

# Allow running from repo root: python scripts/check_dependencies.py
_backend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

def check():
    print("=== SeeLess Dependency & Environment Diagnostic ===")
    
    # 1. Python
    print(f"Python Version: {sys.version}")

    # 2. FFmpeg / FFprobe
    for bin_name in ["ffmpeg", "ffprobe"]:
        path = shutil.which(bin_name)
        if path:
            print(f"[OK] {bin_name} found at {path}")
        else:
            print(f"[FAIL] {bin_name} is NOT found in PATH. Please install FFmpeg.")

    # 3. Python Packages
    # Note: pydub's audioop dependency was removed from Python 3.13+. The SeeLess pipeline
    # uses FFmpeg directly for all audio mixing — pydub is not imported at runtime.
    pkgs = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "sqlalchemy",
        "requests",
        "httpx",
        "scenedetect",
        "cv2",
        "celery",
        "google.generativeai",
    ]
    for p in pkgs:
        try:
            __import__(p)
            print(f"[OK] Python package '{p}' available.")
        except ImportError as e:
            print(f"[FAIL] Missing package '{p}': {e}")

    # 4. Gnani AI Configuration Check
    try:
        from app.config import settings
        print(f"\nGnani STT Endpoint: {settings.GNANI_STT_ENDPOINT}")
        print(f"Gnani TTS Endpoint: {settings.GNANI_TTS_ENDPOINT}")
        print(f"Gnani Voice ID: {settings.GNANI_VOICE_ID}")
        print(f"Gnani API Key Configured: {'YES' if bool(settings.GNANI_API_KEY) else 'NO (Set GNANI_API_KEY in backend/.env)'}")
        print(f"Gemini API Key Configured: {'YES' if bool(settings.GEMINI_API_KEY) else 'NO (Set GEMINI_API_KEY in backend/.env)'}")
    except Exception as e:
        print(f"[FAIL] Config error: {e}")

if __name__ == "__main__":
    check()

