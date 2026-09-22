# Local development

## Prerequisites

- Flutter stable
- Node.js 20+
- Python 3.11+
- Docker Desktop (recommended for MongoDB and Redis)

## Start dependencies and service containers

Use a generated local-only internal token. Do not copy production secrets into the repository or shell history.

```bash
export VISUAL_TUTOR_INTERNAL_TOKEN="$(openssl rand -hex 32)"
docker compose -f docker-compose.dev.yml up --build
```

This starts the Node gateway at `http://localhost:4000` and AI service at `http://localhost:8001`. Start the optional admin container with `--profile admin`.

## Run services directly

```bash
# AI service
cd ai-service
python3 -m venv venv
venv/bin/python -m pip install -c constraints-ai.txt -r requirements.txt
ENVIRONMENT=development APP_ENV=development \
  VISUAL_TUTOR_INTERNAL_TOKEN="$VISUAL_TUTOR_INTERNAL_TOKEN" \
  ALLOWED_ORIGINS=http://localhost:53123,http://127.0.0.1:53123,http://localhost:53124,http://127.0.0.1:53124 \
  venv/bin/python -m uvicorn api.main:app --reload --port 8001

# Node gateway (new terminal)
cd backend-ai-tutor/backend
npm ci
NODE_ENV=development APP_ENV=development PORT=4000 \
  AI_SERVICE_BASE_URL=http://localhost:8001 \
  VISUAL_TUTOR_INTERNAL_TOKEN="$VISUAL_TUTOR_INTERNAL_TOKEN" \
  CORS_ALLOWED_ORIGINS=http://localhost:53123,http://127.0.0.1:53123,http://localhost:53124,http://127.0.0.1:53124 \
  npm run dev

# Flutter (new terminal)
cd ai_tutor
flutter pub get
flutter run -d chrome --web-port=53123 \
  --dart-define=APP_ENV=development \
  --dart-define=BACKEND_BASE_URL=http://localhost:4000/api/v1 \
  --dart-define=AI_SERVICE_BASE_URL=http://localhost:8001/api/v1
```

## Verify a fresh checkout

```bash
./scripts/verify-clean-checkout.sh
```

It creates `.verify-venv`, installs dependencies, validates Compose, and runs the same core checks as CI. It never starts a deployment.
