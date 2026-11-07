# SeeLess v0.3 Architecture Remediation — Design Draft

* **Author:** Sanskar
* **Date:** 2026-11-07
* **Status:** Draft — Step 4 (Alternatives Considered) complete

---

## The Problem

SeeLess is an AI-powered audio description platform for visually impaired viewers. A user uploads a video, and SeeLess generates audio descriptions of important visual information without interrupting original dialogue, music, or sound effects.

The v0.2.1 codebase has critical architectural debt and the product roadmap has seven progressive iterations that must be developed:

1. **Complete working MVP** — end-to-end accessible video generation
2. **Advanced visual intelligence** — character tracking, action recognition, expressions, scene continuity
3. **Intelligent narration engine** — event prioritization, context-aware descriptions, dialogue-safe scheduling
4. **Professional audio experience** — consistent voice, volume normalization, ducking, separate audio-description track
5. **Generalized video intelligence** — movies, documentaries, tutorials, interviews, presentations, sports, news
6. **Full product experience** — user accounts, video library, accessible player, processing history
7. **Production engineering** — Docker, CI/CD, monitoring, scalable workers, storage, integrations

The current v0.2.1 codebase partially covers Iterations 1, 3, 4, and 7 but skips the core product intelligence (Iterations 2, 3, 5, 6).

---

## Overview

This design reorganizes the engineering work into the product roadmap phases. The infrastructure work (Celery, Redis, Docker, CI/CD, Observability) supports the product phases rather than existing as separate parallel tracks.

**Core architectural shift**: Replace synchronous `BackgroundTasks` with Redis-backed Celery workers. This decouples HTTP latency from processing time, enables retry/backoff for external APIs, and provides durability.

**Non-negotiable product requirements** (every phase must respect):
- Original actor dialogue remains untouched — never repeat, paraphrase, or regenerate it
- Narration describes visual information only
- Never place narration over protected dialogue intervals
- Preserve original music, sound effects, ambience
- Gentle ducking of non-dialogue audio optional
- Never invent visual events
- Avoid repetitive/insignificant descriptions
- Gnani AI exclusive STT/TTS provider; Google Gemini exclusive visual/description provider

---

## Goals

### Phase 0 — Codebase Stabilization (P0 engineering)
- Convert EGM to installable `src/` package with `pyproject.toml`; remove `sys.path` hacks
- Migrate `google.generativeai` → `google.genai` SDK across visual analysis & description services
- Add Gnani TTS exponential backoff (max 3 retries, base 2s, jitter ±0.5s)
- Add Gnani STT circuit breaker (5 failures → 30s open) + DNS timeout config
- Centralize all provider config in `config.py` (15+ new keys)
- Structured error logging for external API failures

**Exit**: Backend starts clean; Gemini + Gnani STT + Gnani TTS work; config is env-based; API failures don't crash app

### Phase 1 — Complete Working MVP
- Frontend: landing, upload, validation, processing screen, progress, result page, accessible playback, download
- Backend: FastAPI app, upload/processing APIs, video metadata, FFmpeg audio extraction, frame extraction, validation, storage
- Scene analysis: PySceneDetect boundaries, timestamps, basic frame sampling (2fps), scene metadata
- Audio understanding: Gnani STT → transcript, speech timestamps, protected intervals, timeline normalization
- Visual understanding: Gemini on representative frames → people, objects, actions, scene context, visual events
- Description generation: grounded descriptions from visual events (not transcript paraphrase)
- Narration scheduler: gap-finding, safety padding, priority, shortening, omission
- Speech generation: Gnani TTS per segment, retry, measure actual clip duration, consistent voice
- Audio assembly: original soundtrack base, insert narration, preserve dialogue/music/effects, optional ducking, separate audio-description track, timestamped transcript
- Quality validation: timing, overlap, sync, duration, integrity, duplication, soundtrack preservation

**Exit**: End-to-end MP4 → accessible MP4 on real videos (dialogue-heavy + visual-heavy)

### Phase 2 — Advanced Visual Intelligence
- Adaptive frame sampling (detect important changes vs fixed 2fps)
- Character detection + tracking across frames/scenes
- Action recognition (what people are doing)
- Facial expressions + body language (meaningful gestures)
- Object recognition (relevant objects)
- Background event detection (outside main action)
- Scene continuity (context between scenes)
- Spatial relationships (relative positions)
- Confidence scoring (uncertainty tracking)

**Exit**: Important visual events captured accurately, including those missed by basic sampling

### Phase 3 — Intelligent Narration Engine
- Event prioritization (plot-relevant > movement; avoid repetition)
- Context-aware descriptions (character/location/scene continuity; natural language)
- Intelligent timing (gap detection, immediate vs delayed, shortening, omission)
- Dialogue protection (Gnani timestamps + safety margins + actual TTS duration + reschedule + final validation)
- Narration quality (dedup, conciseness, continuity, no speculation)

**Exit**: Narration relevant, non-repetitive, understandable, dialogue-safe

### Phase 4 — Professional Audio Experience
- Consistent Gnani TTS narrator voice
- Appropriate speech pacing + natural pauses
- Volume normalization (narration vs original)
- Original audio preservation
- Optional music/ambience ducking
- Smooth transitions + A/V sync
- Separate audio-description track (standalone WAV/MP3)
- Final output quality checks

**Exit**: Professionally mixed accessible audio with preserved soundtrack

### Phase 5 — Generalized Video Intelligence
- Video-type classification (movie, documentary, educational, tutorial, interview, presentation, sports, news)
- Content-specific description strategies
- Adaptive narration density per category
- OCR + diagram understanding (slides, charts, equations)
- Better fast-motion analysis
- Long-video context management

**Exit**: One platform handling multiple video categories

### Phase 6 — Full Product Experience
- User management: registration, profiles, settings, video library, processing history
- Video experience: accessible player, enable/disable descriptions, original vs accessible comparison, playback controls, narration speed, voice settings, audio-description track selection
- Processing experience: progress, notifications, retry, management, downloads, error explanations
- Accessibility: screen-reader UI, keyboard nav, accessible controls, high-contrast, status announcements

**Exit**: Polished, accessible web application users return to

### Phase 7 — Production Engineering & Integrations
- **Async infra**: Celery workers, Redis broker, task queues, checkpoints, retries, idempotent processing, worker recovery
- **Deployment**: Backend/worker/frontend Dockerfiles, Docker Compose, automated testing, linting, type-checking, build validation, CI/CD workflows
- **Monitoring**: Prometheus metrics, structured logging, trace IDs, processing latency, provider API failure rates, queue monitoring, worker health, dependency health checks
- **Storage**: SQLite → PostgreSQL migration path, object storage, large file management, retention policies, failed job handling
- **Integrations**: Authorized YouTube/Drive/cloud imports, public API (respect DRM/authorization)
- **Security**: Secure uploads, file validation, API auth, rate limiting, secrets management, data deletion, storage isolation, provider failure recovery, cost optimization

**Exit**: Production-ready service handling multiple users + large workloads

---

## Non-Goals

- Full microservice decomposition (monolithic FastAPI + Celery)
- Multi-tenant architecture (single-tenant MVP)
- Real-time streaming TTS (batch processing sufficient)
- Custom model fine-tuning (vendor models as-is)
- Alternative STT/TTS providers (Gnani contractual)
- Kubernetes deployment (Docker Compose for local; K8s future)
- Whisper/faster-whisper/Silero/ElevenLabs (Gnani exclusive)

---

## Technical Plan

### High-Level Architecture (Phase 1+)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  FastAPI    │────▶│   Redis     │
│  (Next.js)  │     │   API       │     │  (Broker)   │
└─────────────┘     └──────┬──────┘     └──────┬──────┘
                           │                   │
                    ┌──────▼──────┐     ┌──────▼──────┐
                    │  Celery     │     │  Celery     │
                    │  Worker     │────▶│  Worker     │
                    │  (TTS/STT)  │     │  (Video)    │
                    └──────┬──────┘     └──────┬──────┘
                           │                   │
                    ┌──────▼───────────────────▼──────┐
                    │   External Services             │
                    │   • Gnani STT (api.vachana.ai)  │
                    │   • Gnani TTS (api.vachana.ai)  │
                    │   • Google Gemini (genai)       │
                    └─────────────────────────────────┘
```

### Phase-by-Phase File Changes

#### Phase 0: Stabilization (P0)

| File | Change | Rationale |
|------|--------|-----------|
| `backend/elephant-goldfish-model/pyproject.toml` | **CREATE** — `src/elephant_goldfish` package, `[project]`, `[build-system]`, `[tool.setuptools.packages.find]` | Installable package |
| `backend/elephant-goldfish-model/src/elephant_goldfish/__init__.py` | **CREATE** — package marker | Clean imports |
| `backend/app/__init__.py` | **MODIFY** — remove `sys.path.insert(0, "elephant-goldfish-model")` | Remove path hack |
| `backend/requirements.txt` | **MODIFY** — add `-e ./elephant-goldfish-model` | Editable install |
| `backend/app/services/visual_analysis_service.py` | **MODIFY** — `google.generativeai` → `google.genai`; client init & calls | SDK migration |
| `backend/app/services/description_service.py` | **MODIFY** — same SDK migration | SDK migration |
| `backend/app/services/tts_service.py` | **MODIFY** — `RetryPolicy` class (exponential backoff: max 3, base 2s, jitter ±0.5s); wrap `generate_narration_audio_gnani` | Eliminate 429 crashes |
| `backend/app/services/audio_analysis_service.py` | **MODIFY** — `CircuitBreaker` (5 failures → 30s open); wrap STT chunks; DNS timeout config | Handle DNS/rate limits |
| `backend/app/config.py` | **MODIFY** — add: `GNANI_TTS_MAX_RETRIES`, `GNANI_TTS_BACKOFF_BASE`, `GNANI_TTS_JITTER`, `GNANI_STT_MAX_RETRIES`, `GNANI_STT_CIRCUIT_BREAKER_THRESHOLD`, `GNANI_STT_CIRCUIT_BREAKER_TIMEOUT`, `GNANI_DNS_TIMEOUT`, plus 8 more for frame sampling, scene detection, scheduler | Externalize all hardcoded constants |

#### Phase 1: Complete MVP (P1 async infra starts here)

| File | Change | Rationale |
|------|--------|-----------|
| `backend/app/workers/celery_app.py` | **MODIFY** — uncomment Celery; `broker_url=redis://redis:6379/0`, `result_backend=redis://redis:6379/0`, `task_serializer=json`, `task_acks_late=True`, `worker_prefetch_multiplier=1` | Enable Celery |
| `backend/app/workers/tasks.py` | **MODIFY** — `process_video` as `@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)`; sub-tasks: `transcribe_audio`, `analyze_visuals`, `generate_descriptions`, `schedule_narration`, `synthesize_tts`, `assemble_video` | Async pipeline |
| `backend/app/services/tts_service.py` | **MODIFY** — verify Gnani API batch support first; if unsupported, individual async calls with semaphore rate limiter | **Do not assume batching** |
| `backend/requirements.txt` | **MODIFY** — uncomment `celery>=5.3.6`; add `redis>=5.0.3`, `httpx>=0.27.0` | Dependencies |
| `docker-compose.yml` | **MODIFY** — add `api`, `worker`, `frontend` services; `depends_on: redis`; volumes | Local dev stack |
| `backend/app/services/scheduler_service.py` | **MODIFY** — speech interval safety padding, actual TTS clip duration measurement, rescheduling after TTS, final overlap verification, soundtrack preservation | Product-critical |

#### Phase 2: Visual Intelligence

| File | Change | Rationale |
|------|--------|-----------|
| `backend/app/services/frame_extraction_service.py` | **CREATE** — adaptive sampling (scene change detection + motion vectors), configurable FPS per content type | Replace fixed 2fps |
| `backend/app/services/character_service.py` | **CREATE** — detection, tracking (appearance + temporal consistency), identity across scenes | Character tracking |
| `backend/app/services/action_recognition_service.py` | **CREATE** — action classification from frame sequences | Action recognition |
| `backend/app/services/expression_service.py` | **CREATE** — facial expression + gesture detection | Expressions/body language |
| `backend/app/services/background_event_service.py` | **CREATE** — detect important events outside main subject | Background events |
| `backend/app/services/continuity_service.py` | **CREATE** — scene-to-scene context propagation | Scene continuity |
| `backend/app/services/spatial_service.py` | **CREATE** — relative positions, spatial relationships | Spatial understanding |
| `backend/app/services/visual_analysis_service.py` | **MODIFY** — orchestrate new services; structured visual events with confidence scores | Integration |
| `backend/app/config.py` | **MODIFY** — add adaptive sampling, tracking, confidence thresholds | Config |

#### Phase 3: Narration Intelligence

| File | Change | Rationale |
|------|--------|-----------|
| `backend/app/services/prioritization_service.py` | **CREATE** — importance ranking (plot-relevant > movement; dedup) | Event prioritization |
| `backend/app/services/contextual_description_service.py` | **CREATE** — character/location/scene continuity; natural language generation | Context-aware descriptions |
| `backend/app/services/scheduler_service.py` | **MODIFY** — intelligent gap detection, priority scheduling, shortening, omission logic | Intelligent timing |
| `backend/app/services/dialogue_protection_service.py` | **CREATE** — Gnani timestamps + safety margins + actual TTS duration + reschedule + final validation | Dialogue protection |
| `backend/app/services/narration_quality_service.py` | **CREATE** — dedup, conciseness, continuity, anti-speculation | Narration quality |

#### Phase 4: Audio Quality

| File | Change | Rationale |
|------|--------|-----------|
| `backend/app/services/tts_service.py` | **MODIFY** — consistent voice settings, pacing, pause insertion | Consistent narrator |
| `backend/app/services/audio_mixing_service.py` | **CREATE** — volume normalization, ducking, smooth transitions, A/V sync, separate track generation | Professional mixing |
| `backend/app/services/quality_service.py` | **MODIFY** — final validation: timing, overlap, sync, duration, integrity, duplication, soundtrack | Quality gates |

#### Phase 5: Generalized Intelligence

| File | Change | Rationale |
|------|--------|-----------|
| `backend/app/services/video_classifier.py` | **CREATE** — classify content type (movie, doc, edu, tutorial, interview, presentation, sports, news) | Video-type classification |
| `backend/app/services/ocr_diagram_service.py` | **CREATE** — OCR + diagram/chart/equation understanding | Educational/presentation content |
| `backend/app/services/fast_motion_service.py` | **CREATE** — high-FPS sampling for fast action | Sports/action content |
| `backend/app/services/long_video_service.py` | **CREATE** — context management for >30min videos | Long-form content |
| `backend/app/services/visual_analysis_service.py` | **MODIFY** — strategy selection per video type | Content-specific descriptions |

#### Phase 6: Product Experience

| File | Change | Rationale |
|------|--------|-----------|
| `frontend/src/pages/*.tsx` | **CREATE/MODIFY** — landing, library, player, history, settings, processing pages | Full UX |
| `frontend/src/components/AccessiblePlayer.tsx` | **CREATE** — enable/disable descriptions, speed, voice, track selection, original comparison | Accessible playback |
| `backend/app/api/users.py` | **CREATE** — registration, profiles, auth | User management |
| `backend/app/api/videos.py` | **MODIFY** — library, history, retry, downloads, management | Video management |
| `backend/app/config.py` | **MODIFY** — user-facing settings (voice, speed, contrast) | User preferences |

#### Phase 7: Production Engineering

| File | Change | Rationale |
|------|--------|-----------|
| `backend/Dockerfile` | **CREATE** — multi-stage: builder → runtime (python:3.12-slim); entrypoint `uvicorn` | Containerize API |
| `backend/Dockerfile.worker` | **CREATE** — same base; entrypoint `celery worker` | Containerize worker |
| `frontend/Dockerfile` | **CREATE** — multi-stage: builder (node:20) → runtime (nginx); copy `.env.example` | Containerize frontend |
| `docker-compose.yml` | **MODIFY** — api:8000, worker, frontend:3000, redis:6379, otel-collector, prometheus | Full stack |
| `.github/workflows/ci.yml` | **CREATE** — lint (ruff), typecheck (mypy), test (pytest), build (docker), frontend (npm ci/lint/build) | Automated CI |
| `backend/app/main.py` | **MODIFY** — Prometheus middleware, `/metrics`, structured JSON logging, `trace_id` propagation | Metrics & logs |
| `backend/app/services/*.py` | **MODIFY** — OpenTelemetry spans for external calls, span attributes | Distributed tracing |
| `backend/app/health.py` | **CREATE** — `/health/gnani-stt`, `/health/gnani-tts`, `/health/gemini` with timeout checks | Dependency health |
| `backend/app/config.py` | **MODIFY** — `OTEL_EXPORTER_OTLP_ENDPOINT`, `LOG_LEVEL`, DB pool config, PostgreSQL URL | Production config |
| `backend/requirements.txt` | **MODIFY** — add `psycopg2`, `asyncpg`, `prometheus-client`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp` | Observability deps |

### Data Flow: Video Processing Pipeline (Phase 1+)

```
POST /api/videos/upload
    │
    ▼
Create VideoRecord (status=UPLOADED)
    │
    ▼
Celery: process_video(video_id)
    │
    ├──▶ extract_audio_ffmpeg() ──▶ audio.wav
    │
    ├──▶ transcribe_audio(audio.wav)
    │       │
    │       ├──▶ chunk_audio(24s chunks, handle offsets)
    │       ├──▶ STT per chunk (circuit breaker + retry)
    │       └──▶ merge_transcripts(global timeline)
    │
    ├──▶ analyze_visuals(video.mp4)
    │       │
    │       ├──▶ extract_frames(adaptive sampling)
    │       ├──▶ character detection + tracking
    │       ├──▶ action recognition + expressions
    │       ├──▶ background events + spatial relationships
    │       └──▶ Gemini visual analysis (genai SDK)
    │
    ├──▶ generate_descriptions(transcript, visual_events)
    │       │
    │       ├──▶ prioritize events (importance ranking)
    │       ├──▶ contextual descriptions (continuity)
    │       └──▶ Gemini description (genai SDK)
    │
    ├──▶ schedule_narration(descriptions, speech_intervals)
    │       │
    │       ├──▶ gap detection + safety padding
    │       ├──▶ priority scheduling + shortening/omission
    │       └──▶ reschedule after TTS duration known
    │
    ├──▶ synthesize_tts(narration_segments)
    │       │
    │       ├──▶ verify Gnani batch support; else semaphore + individual
    │       ├──▶ measure actual clip durations
    │       └──▶ retry/backoff on 429
    │
    └──▶ assemble_video(original_audio, tts_clips)
            │
            ├──▶ FFmpeg mix with optional ducking
            ├──▶ separate audio-description track
            └──▶ final validation (no overlap, sync, integrity)

Update VideoRecord (status=COMPLETED, output_path=...)
```

### Critical Technical Decisions (Review Required)

1. **Gemini fallback**: Current plan falls back to generic descriptions on failure. **Recommendation**: Remove fallback. On visual analysis failure, report failure or retry. Generic descriptions risk hallucinated visual content.

2. **Gnani TTS batching**: Plan assumes single request + split response. **Recommendation**: Verify Gnani API docs first. If unsupported, use individual async calls with token bucket rate limiter.

3. **STT timestamp reliability**: 24s chunks must convert to global timeline. Handle chunk offsets, overlaps, duplicate segments. **Recommendation**: Explicit offset tracking in merge step.

4. **Dialogue protection**: Must include safety padding, actual TTS duration measurement, rescheduling, final verification, soundtrack preservation. These are product-critical, not optional.

### Configuration Matrix

| Config Key | Phase | Default | Description |
|------------|-------|---------|-------------|
| `GNANI_TTS_MAX_RETRIES` | 0 | 3 | Max retry attempts for 429 |
| `GNANI_TTS_BACKOFF_BASE` | 0 | 2.0 | Exponential backoff base (seconds) |
| `GNANI_TTS_JITTER` | 0 | 0.5 | Jitter ±seconds |
| `GNANI_STT_MAX_RETRIES` | 0 | 3 | STT chunk retries |
| `GNANI_STT_CIRCUIT_BREAKER_THRESHOLD` | 0 | 5 | Consecutive failures before open |
| `GNANI_STT_CIRCUIT_BREAKER_TIMEOUT` | 0 | 30 | Open state duration (seconds) |
| `GNANI_DNS_TIMEOUT` | 0 | 5.0 | DNS resolution timeout |
| `FRAME_EXTRACTION_MODE` | 2 | `adaptive` | `fixed` or `adaptive` |
| `FRAME_EXTRACTION_FPS` | 2 | 2.0 | Fixed FPS fallback |
| `CHARACTER_TRACKING_ENABLED` | 2 | `true` | Enable cross-scene tracking |
| `EXPRESSION_DETECTION_ENABLED` | 2 | `true` | Facial expression analysis |
| `BACKGROUND_EVENT_DETECTION` | 2 | `true` | Detect off-subject events |
| `SCENE_CONTINUITY_ENABLED` | 2 | `true` | Cross-scene context |
| `NARRATION_PRIORITIZATION` | 3 | `true` | Importance ranking |
| `CONTEXTUAL_DESCRIPTIONS` | 3 | `true` | Continuity-aware generation |
| `DIALOGUE_SAFETY_PADDING_MS` | 3 | 200 | Safety margin around speech |
| `TTS_DURATION_MEASUREMENT` | 3 | `true` | Measure actual clip duration |
| `DUCKING_ENABLED` | 4 | `false` | Music/ambience ducking |
| `DUCKING_GAIN_DB` | 4 | -12 | Ducking gain reduction |
| `VIDEO_CLASSIFIER_ENABLED` | 5 | `true` | Content-type classification |
| `OCR_ENABLED` | 5 | `true` | OCR for slides/diagrams |
| `CELERY_BROKER_URL` | 1 | `redis://redis:6379/0` | Redis broker |
| `CELERY_RESULT_BACKEND` | 1 | `redis://redis:6379/0` | Redis results |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | 7 | `http://otel-collector:4317` | OpenTelemetry collector |
| `LOG_LEVEL` | 7 | `INFO` | Structured log level |
| `DATABASE_URL` | 7 | `sqlite:///./seeless.db` | PostgreSQL in prod |

### Error Handling Strategy

| Failure Point | Strategy |
|---------------|----------|
| Gnani STT 429 / DNS | Circuit breaker (5 → 30s); retry chunk 3× backoff; final failure → mark `UNTRANSCRIBED` (protected silence) |
| Gnani TTS 429 | Token bucket rate limiter (config RPS); verify batch support; else async semaphore; retry 3× backoff |
| Gemini 429 / 5xx | Retry 3× backoff (base 1s); fatal (401/404) → mark `FAILED`, **no generic fallback** |
| FFmpeg failure | Catch `ExtractionError`; actionable error (codec, disk, binary); mark job `FAILED` |
| DB lock (SQLite) | `pool_pre_ping=True`, `pool_recycle=300`; `SELECT FOR UPDATE` on status transitions |
| Worker crash/restart | Celery `task_acks_late=True` + `result_backend` = at-least-once; idempotent via `video_id` + stage checkpoints |

---

## Alternatives Considered

### Task Queue: Celery + Redis vs RQ + Redis
- **Celery + Redis** (Selected): Maturity, monitoring (Flower), Canvas workflows, task routing, rate limiting, extensive ecosystem. Supports complex pipelines with chord/group primitives needed for video processing stages.
- **RQ + Redis** (Rejected by author): Simpler but lacks Canvas, limited monitoring, no native task routing, smaller ecosystem. Would require custom orchestration for multi-stage video pipeline.

### TTS Batching: Server-side Merge vs Client-side Concat
- **Server-side merge / single API call** (Selected in concepts_brief, **re-evaluated**): Atomic operation, single network round-trip, easier retry semantics. **BUT**: Must verify Gnani API supports batch input + segmented output. If unsupported, this option is unavailable.
- **Client-side concat** (Fallback): Individual requests with semaphore rate limiter. Higher latency (O(n) calls) but works with any API. **Rejected by author as primary** due to 429 risk at scale; retained as verified fallback.

### SDK Migration: Incremental vs Big-bang
- **Incremental with feature flags** (Selected): Per-module migration (visual_analysis → description → tests). Reduces blast radius; enables rollback; parallel development possible. Feature flag `USE_GENAI_SDK` controls migration.
- **Big-bang** (Rejected by author): Single PR changes all call sites. High risk of subtle API differences causing silent failures; difficult to bisect; blocks other work during migration.

### EGM Packaging: pyproject.toml + editable install vs Git submodule
- **pyproject.toml + editable install** (Selected): Standard Python packaging; version pinning; dependency resolution; works with pip/uv; CI-friendly; enables `import elephant_goldfish` cleanly.
- **Git submodule** (Rejected by author): No version metadata; manual updates; no dependency resolution; IDE import resolution issues; breaks pip-based tooling.

### CI Platform: GitHub Actions vs GitLab CI
- **GitHub Actions** (Selected): Repository native; matrix builds for backend/frontend; reusable workflows; OIDC for cloud deploy; marketplace actions; free for public/private.
- **GitLab CI** (Rejected by author): Requires GitLab runner infrastructure; repository not on GitLab; adds operational complexity without benefit.

### Visual Intelligence: Fixed FPS vs Adaptive Sampling
- **Adaptive sampling** (Selected for Phase 2): Scene change detection + motion vectors capture important moments; reduces frames for static scenes; configurable per content type.
- **Fixed 2 FPS** (Current, Rejected for Phase 2+): Misses fast events; wastes compute on static scenes; no content awareness. Retained as fallback mode via `FRAME_EXTRACTION_MODE=fixed`.

### Narration Scheduling: Greedy Gap-filling vs Priority-based
- **Priority-based with shortening/omission** (Selected): Important events get scheduled first; lower priority shortened or omitted; respects dialogue safety as hard constraint.
- **Greedy gap-filling** (Rejected by author): Fills gaps sequentially without importance awareness; risks describing trivial movements while missing plot-critical actions.

### Audio Mixing: Simple Overlay vs Ducking + Separate Track
- **Ducking + separate audio-description track** (Selected for Phase 4): Professional quality; user choice (enable/disable descriptions); accessibility compliance; soundtrack preservation.
- **Simple overlay** (Rejected by author): Narration competes with music/effects; no separate track for assistive tech; fails accessibility requirements.

### Deployment: Docker Compose vs Kubernetes
- **Docker Compose** (Selected for Phase 7): Local dev parity; simple; sufficient for MVP scale; no cluster ops burden.
- **Kubernetes** (Rejected by author for Phase 7): Over-engineering for single-tenant MVP; adds significant ops complexity; deferred to post-MVP scaling phase.

### Database: SQLite vs PostgreSQL
- **SQLite → PostgreSQL migration path** (Selected): SQLite for Phase 0–6 (zero-config, file-based, sufficient for dev/single-user); PostgreSQL for Phase 7 production (concurrency, connection pooling, JSONB, replication).
- **PostgreSQL from start** (Rejected by author): Adds infra dependency early; complicates local dev; SQLite adequate until multi-user/concurrency needs.

### Observability: Prometheus + OpenTelemetry vs Cloud Vendor (Datadog/New Relic)
- **Prometheus + OpenTelemetry** (Selected): Vendor-neutral; open standards; self-hosted; integrates with Grafana; no per-host cost; portable to any cloud.
- **Cloud vendor APM** (Rejected by author): Vendor lock-in; per-host pricing; not necessary for MVP scale; adds procurement/approval overhead.

---

## Key Decisions & Staging

**Approved**: Four-phase engineering workstreams (P0–P3) kept but reorganized into 8 product phases (0–7).

**Next**: Proceed to Detailed Implementation section.

**Approval Gate:** How would you like to proceed?

1. **Approve Alternatives Considered and proceed to Detailed Implementation**
2. **Request revisions to Alternatives Considered** (inline comments on `design_draft.md` or write-in)