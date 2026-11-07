# SeeLess AI-Powered Audio Description Platform
* **Author:** Sanskar
* **Date:** 2026-11-07

## Overview
SeeLess is an AI-powered audio description platform that processes video content and generates descriptive audio tracks. This brief synthesizes Goldfish-model findings for v0.2.1, identifying critical blockers and architectural debt requiring staged remediation.

## Analysis
**Blocker — Gnani TTS rate limit & linear latency** (`backend/app/services/tts_service.py`): HTTP 429 responses under load; per-segment serial requests cause O(n) latency. No retry/backoff.

**Major — Gemini SDK deprecation**: `google.generativeai` deprecated in favor of `google.genai`. Migration required across all LLM call sites.

**Major — EGM vendored flat layout** (`backend/elephant-goldfish-model/`): Flat directory without `pyproject.toml` or package structure prevents clean dependency management and versioning.

**Major — FastAPI `BackgroundTasks` sync execution**: Background tasks run synchronously in-process without Redis/Celery broker, blocking request workers and losing durability.

**Major — Gnani STT DNS failures & rate limits**: Intermittent DNS resolution failures and 429 responses on speech-to-text endpoints.

**Nit — Next.js SWC warnings & hardcoded env**: SWC minifier warnings in build; environment variables hardcoded in frontend config.

**Major — Docker & CI pipeline absence**: No containerization, no CI/CD, no automated testing pipeline.

## Goals vs. Non-Goals
**Goals (v0.2.1 → v0.3.0)**
- Eliminate TTS 429 blocker via Celery queue + exponential backoff + batching
- Migrate to `google.genai` SDK
- Package EGM as installable module with `pyproject.toml`
- Introduce Redis + Celery for async task processing
- Add STT retry logic with circuit breaker
- Implement Docker Compose for local dev + CI pipeline

**Non-Goals**
- Full microservice decomposition
- Multi-tenant architecture
- Real-time streaming TTS
- Custom model fine-tuning

## Alternatives Weighed
| Area | Option A | Option B | Decision |
|------|----------|----------|----------|
| Task queue | Celery + Redis | RQ + Redis | Celery (maturity, monitoring, Canvas) |
| TTS batching | Client-side concat | Server-side merge | Server-side (single API call, atomic) |
| SDK migration | Incremental | Big-bang | Incremental (per-module feature flags) |
| EGM packaging | `pip install -e .` | Submodule | `pyproject.toml` + editable install |
| CI | GitHub Actions | GitLab CI | GitHub Actions (repo native) |

## Key Decisions & Staging for Next Steps
**Stage 1 — Stabilize (P0)**
1. Add `pyproject.toml` to `backend/elephant-goldfish-model/`, publish as local editable package
2. Migrate `google.generativeai` → `google.genai` in all call sites
3. Implement TTS exponential backoff (max 3 retries, base 2s, jitter ±0.5s)
4. Add STT retry with circuit breaker (5 failures → 30s open)

**Stage 2 — Async Infrastructure (P1)**
5. Provision Redis (Docker Compose)
6. Replace `BackgroundTasks` with Celery tasks; define task signatures for TTS, STT, video processing
7. Implement TTS batching: collect segments → single Gnani call → split response

**Stage 3 — CI/CD & Hardening (P2)**
8. Docker Compose for backend + frontend + Redis
9. GitHub Actions: lint → type-check → unit → integration
10. Frontend: remove hardcoded env, fix SWC warnings, add `.env.example`

**Stage 4 — Observability (P3)**
11. Structured logging + metrics (Prometheus)
12. Distributed tracing (OpenTelemetry)
13. Health checks for all external dependencies (Gnani, Gemini)