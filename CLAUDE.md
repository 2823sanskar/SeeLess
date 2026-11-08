# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SeeLess** is an AI-powered accessibility platform that generates audio descriptions for videos to assist visually impaired viewers. It processes MP4 files through a 10-stage pipeline using Gnani AI STT/TTS and Google Gemini for visual intelligence.

## Technology Stack

- **Frontend**: Next.js 16.4.5, React 19, TypeScript, Tailwind CSS
- **Backend**: FastAPI, SQLAlchemy, SQLite (MVP), Celery (optional with Redis), FFmpeg
- **AI Services**: Gnani AI (STT/TTS), Google Gemini (visual analysis)

## Project Structure

```
gnani-ai-product-2/
├── backend/
│   ├── app/
│   │   ├── api/              # REST endpoints (/videos, /health)
│   │   ├── services/         # Business logic: analytics_service, extraction_service, scene_service, etc.
│   │   ├── models.py         # SQLAlchemy ORM models (Video, Description, SpeechSegment, etc.)
│   │   ├── schemas.py        # Pydantic request/response schemas
│   │   ├── main.py           # FastAPI app entry point
│   │   └── config.py         # Settings via Pydantic BaseSettings
│   ├── tests/                # Pytest unit tests
│   └── .env                  # Environment configuration
├── frontend/
│   ├── app/                  # Next.js App Router pages
│   ├── components/           # Reusable UI components
│   ├── lib/                  # API client (api.ts) and types (types.ts)
│   └── .env.local            # NEXT_PUBLIC_API_URL
└── storage/                  # Generated video/audio artifacts
```

## Database Models (backend/app/models.py)

Core entities:
- **Video**: Original upload, metadata, status
- **ProcessingJob**: Pipeline stage tracking (PENDING/RUNNING/COMPLETED/FAILED)
- **ProcessingArtifact**: Accessible video, audio description, transcript files
- **Scene**: Visual scene boundaries
- **SpeechSegment**: Dialogue with timestamps from STT
- **Description**: AI-generated audio description text
- **NarrationClip**: TTS-generated audio files

## API Endpoints

- `POST /api/videos/upload` - Upload MP4
- `POST /api/videos/{id}/process` - Start processing pipeline
- `GET /api/videos/{id}/status` - Get job progress
- `GET /api/videos/{id}/result` - Final outputs (video, audio, transcript)
- `GET /api/videos/{id}/compliance` - Accessibility scorecard (Phase 7)
- `GET /api/videos/{id}/export/compliance?format=json|pdf` - Export report
- `GET /api/videos/{id}/download` - Download accessible MP4
- `GET /api/videos` - List/search videos (Phase 6)
- `POST /api/videos/batch-upload` - Multi-file upload
- `POST /api/videos/bulk-export` - Download multiple videos as ZIP

## Frontend Architecture

Pages:
- `/app/page.tsx` - Main upload interface
- `/app/dashboard/page.tsx` - Video library with batch upload
- `/app/result/[videoId]/page.tsx` - Accessible video player with compliance report
- `/app/processing/[videoId]/page.tsx` - Processing progress

Key Components:
- `AccessibleVideoPlayer` - Audio toggle, descriptions overlay
- `ComplianceReport` - WCAG scorecard with metrics (Phase 7)
- `VideoLibrary` - Searchable grid with filtering
- `VideoUploader` / `VideoBatchUploader` - File drop zones

## Common Development Commands

### Backend
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Set environment
$env:PYTHONPATH="."

# Start API server (Windows)
python -m uvicorn app.main:app --reload --port 8000

# Run tests
python -m pytest tests -v

# API docs
# http://localhost:8000/docs
```

### Frontend
```bash
cd frontend

# Install dependencies
npm install

# Development server
npm run dev

# Build
npm run build

# Lint
npm run lint

# Production server
npm run start
```

### Docker (Redis for Celery)
```bash
docker compose up -d redis
```

## Phase Completion Status

- Phase 1-6: Implemented (upload, STT, scene detection, scheduling, TTS, assembly, player, library, batch upload)
- Phase 7: Completed - Analytics & Accessibility Compliance Reporting
  - `backend/app/services/analytics_service.py` - Compliance metrics calculation
  - `backend/app/api/videos.py` - `/compliance` and `/export/compliance` endpoints
  - `frontend/components/ComplianceReport.tsx` - Visual scorecard
  - `frontend/app/result/[videoId]/page.tsx` - Integrated compliance display