# Current architecture

## Deployable services

| Service | Source | Runtime entrypoint | Responsibility |
| --- | --- | --- | --- |
| Learner app | `ai_tutor` | `lib/main.dart` | Flutter web/mobile experience and safe board rendering |
| Node gateway | `backend-ai-tutor/backend` | `src/server.ts` | authentication boundary, API routes, Tutor stream proxy |
| AI service | `ai-service` | `api/main.py` | teaching plans, curriculum/KG retrieval, learner state, voice/scan services |
| Admin | `admin-ai-tutor` | Next.js `app/` | content and operational administration |

## Request path

`ai_tutor` calls the Node gateway at `/api/v1`. The gateway authenticates and forwards Visual Tutor work to `ai-service` with the shared internal token. The AI service returns only the versioned public teaching-plan contract; Flutter renders only declarative actions from that contract.

The AI service persists operational data in MongoDB and uses Redis for cache/session work. The Node gateway uses Firebase Admin for identity. Neither service accepts executable UI code from a model.

## Deployment artifacts

- `docker-compose.dev.yml`: local MongoDB, Redis, AI service, Node gateway, and optional admin profile.
- `docker-compose.yml`: production topology. It expects secret-manager values and a separate TLS/public-ingress layer.
- `.github/workflows/ci.yml`: builds/tests all current services and runs the curriculum release gate.
- `.github/workflows/cd.yml`: builds the Flutter bundle and publishes images for the Node gateway, AI service, and admin service.

Legacy names such as `flutter-app`, `backend-service`, `admin-service`, and `mcp-server` are not current services.
