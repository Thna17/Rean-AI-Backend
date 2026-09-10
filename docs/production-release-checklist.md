# Rean AI Tutor production release checklist

## Required environment

### Admin

- `NEXT_PUBLIC_BACKEND_BASE_URL` — browser same-origin BFF API base.
- `BACKEND_INTERNAL_BASE_URL` — server-only backend API base for `proxy.ts`.

### Backend API

- `NODE_ENV=production`, `APP_ENV=production`
- `JWT_ACCESS_SECRET` — unique 32+ character secret.
- `JWT_ACCESS_TTL_MINUTES`, `JWT_REFRESH_TTL_DAYS`
- `FIREBASE_PROJECT_ID`, `FIREBASE_CLIENT_EMAIL`, `FIREBASE_PRIVATE_KEY`
- `CORS_ALLOWED_ORIGINS` — explicit Admin/browser allow-list, never `*`.
- `AI_SERVICE_BASE_URL` — non-local AI service URL.
- `VISUAL_TUTOR_INTERNAL_TOKEN` — shared 32+ character service secret.
- `ALLOW_DEVELOPMENT_FALLBACKS=false`, `ALLOW_DEMO_AUTHENTICATION=false`, `AI_SERVICE_USE_DEV_MOCK=false`

### AI service

- `ENVIRONMENT=production`, `APP_ENV=production`, `DEBUG=false`
- `SECRET_KEY` and `VISUAL_TUTOR_INTERNAL_TOKEN` — unique 32+ character secrets.
- `MONGODB_URI`, `MONGODB_DATABASE` — durable TLS Mongo deployment.
- `REDIS_URL` — durable authenticated Redis deployment.
- `ALLOWED_ORIGINS` — explicit allow-list.
- `VISUAL_TUTOR_LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY`
- `GEMINI_API_KEY` when OCR is enabled; `STT_MODEL_NAME` / `TTS_MODEL_PATH` when enabled.
- `ADMIN_PUBLISHED_CURRICULUM_PATH` — durable shared volume/object-store mount; deploy a single publisher until this is replaced with transactional shared storage.

### Flutter

- Production backend base URL and Firebase mobile configuration supplied through the platform secret/config mechanism; no service-account credentials in the app.

## Pre-deploy gates

1. Store secrets only in the deployment secret manager; verify `.env*` and Firebase service-account JSON are ignored by Git.
2. Deploy Admin and backend through one same-origin BFF/reverse proxy so HttpOnly cookies and CSRF work; set both Admin URLs above.
3. Run migrations/index creation and back up Firestore, Mongo, and the published curriculum store.
4. Probe `Admin /api/health`, backend `/api/v1/health/ready`, and authenticated AI `/api/v1/visual_tutor/readiness`.
5. Confirm readiness shows Firestore/Mongo, LLM, and curriculum retrieval healthy. Optional OCR/STT/TTS may be degraded only if intentionally disabled.
6. Confirm request IDs appear unchanged in Admin/BFF/backend/AI logs and alerts cover tutor errors, stale board conflicts, publish failures, retrieval misses, review queue size, and restriction events.
7. Run the focused security, curriculum-pipeline, Visual Tutor lesson-state, Flutter board-state, and Admin builds before promotion.
8. Perform a staging smoke flow: create draft curriculum, publish, verify version/chunk IDs on tutor turn, submit Step 1 then Step 2, report/review a session, and confirm no solver or learner-memory fields in public JSON.

## Rollback

1. Stop promotion and route traffic to the previous immutable Admin/backend/AI images.
2. If a curriculum version caused the incident, archive it through Admin; this calls AI unpublish and reloads retrieval. If the API is unavailable, restore the prior durable `ADMIN_PUBLISHED_CURRICULUM_PATH` snapshot, then restart the single AI writer.
3. Revoke any compromised Admin refresh sessions and rotate `VISUAL_TUTOR_INTERNAL_TOKEN`, Firebase credentials, and affected provider keys in the secret manager.
4. Restore Firestore/Mongo only from a timestamped backup after validating scope; do not roll back unrelated student data.
5. Verify readiness, a safe tutor turn, public response redaction, and board version behavior before reopening traffic.
6. Preserve correlation IDs, audit logs, and the deployed image digests for incident review.

## Known deployment constraint

The published-curriculum JSONL overlay uses a process-local lock. It is safe only with a single publisher and durable shared storage. Multi-writer/multi-replica publication requires a transactional shared store or CAS object storage before broad production scale-out.
