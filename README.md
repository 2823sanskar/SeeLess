# SeeLess — AI-Powered Audio Description Platform
### Iteration 1 MVP

SeeLess is an AI-powered accessibility platform designed for visually impaired viewers. It analyzes video and audio content, transcribes original dialogue, detects visual actions and gestures, and schedules spoken audio descriptions in natural gaps without interrupting original actor dialogue, sound effects, or music.

---

## 🚀 Key Features (Iteration 1)

1. **MP4 Upload & Extraction**: Validates video dimensions, duration, and extracts high-fidelity audio and sampled video frames.
2. **Gnani AI STT**: Exclusively transcribes dialogue and provides speech interval boundaries with configurable safety padding.
3. **Visual Intelligence (Gemini)**: Detects character actions, facial expressions, and spatial events with scene continuity.
4. **Dialogue-Safe Scheduler**: Deterministic scheduler ensuring **zero narration overlap** with original dialogue.
5. **Gnani AI TTS**: Synthesizes spoken audio description clips using Gnani AI's Timbre models (`timbre-v2.5`).
6. **Audio & Media Assembly**: Combines original soundtrack with generated narration clips using FFmpeg and muxes into an accessible MP4.
7. **Accessible Multi-Track Player**: Custom video playback component with instant audio toggle between original audio and described master stem.
8. **Professional Audio Experience**: EBU R128 loudness normalization (-24 LUFS) and smart soundtrack ducking during narration segments.
9. **Player & Downloads**: Web interface with accessible HTML5 playback, video download, standalone audio-description WAV, and timestamped transcript JSON.

---

## 🛠️ Technology Stack

- **Frontend**: Next.js 15, React 19, TypeScript, Tailwind CSS
- **Backend**: FastAPI, SQLAlchemy, SQLite (MVP), Celery, Redis
- **Audio AI**: **Gnani AI** (Speech-to-Text STT & Text-to-Speech TTS)
- **Visual AI**: Google Gemini
- **Media Processing**: FFmpeg, FFprobe, PySceneDetect, OpenCV, PyDub

---

## 📋 Prerequisites

- **Python 3.10+** (Tested on Python 3.15)
- **Node.js 18+** & npm
- **FFmpeg & FFprobe** installed and added to `PATH`
- (Optional) Docker for running Redis (`docker compose up -d redis`)

---

## ⚙️ Installation & Setup

### 1. Configure Environment Variables

**Backend (`backend/.env`):**
```env
APP_NAME=SeeLess
APP_ENV=development
DATABASE_URL=sqlite:///./seeless.db
REDIS_URL=redis://localhost:6379/0
STORAGE_DIR=../storage

MAX_UPLOAD_SIZE_MB=500
MAX_VIDEO_DURATION_SECONDS=600

# Visual AI
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash

# Gnani AI Audio Services (Exclusive AI STT & TTS)
GNANI_API_KEY=your_gnani_api_key_here
GNANI_STT_ENDPOINT=https://api.vachana.ai/stt/v3
GNANI_TTS_ENDPOINT=https://api.vachana.ai/api/v1/tts/inference
GNANI_STT_MODEL=prisma-v3.0
GNANI_TTS_MODEL=timbre-v2.5
GNANI_VOICE_ID=Nalini
```

**Frontend (`frontend/.env.local`):**
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

### 2. Install Dependencies

**Backend:**
```bash
cd backend
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
npm install
npm run build
```

---

## 🏃 Running the Application

### 1. Start Redis (Optional for Celery; FastAPI background tasks run automatically if Redis is off)
```bash
docker compose up -d redis
```

### 2. Start Backend API
```bash
cd backend
# Windows:
$env:PYTHONPATH="."
python -m uvicorn app.main:app --reload --port 8000
```
Backend API docs available at: `http://localhost:8000/docs`

### 3. Start Celery Worker (Optional)
```bash
cd backend
$env:PYTHONPATH="."
celery -A app.workers.celery_app.celery_app worker --loglevel=info
```

### 4. Start Frontend
```bash
cd frontend
npm run dev
```
Open `http://localhost:3000` in your browser.

---

## 🧪 Testing

### Run Automated Pytest Suite
```bash
$env:PYTHONPATH="backend"
python -m pytest tests
```
Runs 13 unit and integration tests covering:
- Upload validation & error handling
- Gnani STT transcription parsing & speech padding
- Narration scheduler non-overlap algorithm
- Description generation format & constraints
- Audio assembly, track separation, and video creation

### Run End-to-End Pipeline Diagnostic
```bash
python scripts/test_pipeline.py
```
This generates a synthetic MP4, executes the complete 10-stage pipeline, verifies all artifacts, and validates quality.

---

## 🐳 Production Deployment (Phase 8)

### Quick Start with Docker Compose

```bash
docker compose up --build
```

This starts:
- **Redis** (port 6379) - Message broker for Celery
- **FastAPI Backend** (port 8000) - REST API with health checks
- **Celery Workers** - Background video processing
- **Next.js Frontend** (port 3000/80) - Accessible video player

### Health Endpoints

- `GET /api/health` - Liveness probe (basic service health)
- `GET /api/health/ready` - Readiness probe (checks DB, Redis, Celery, Gnani API)

### Docker Build Commands

```bash
# Build images only
docker compose build

# Rebuild with --no-cache
docker compose build --no-cache

# Start services in background
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down

# Remove volumes (clears Redis data)
docker compose down -v
```

### Environment Variables (Production)

Copy example files and configure:

```bash
# Backend
cp backend/.env.example backend/.env

# Frontend  
cp frontend/.env.example frontend/.env.local
```

Refer to `backend/.env.example` for all available configuration options including AI API keys.

