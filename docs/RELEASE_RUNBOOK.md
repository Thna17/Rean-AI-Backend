# Release runbook

## Required gates

1. A reviewed release branch has a clean status apart from approved release artifacts.
2. GitHub CI passes Flutter analyze/tests, Node build/tests, AI-service tests, curriculum release gate, and admin build/tests.
3. The curriculum coverage manifest is reviewed; unsupported scope is not advertised.
4. Staging validates authentication, stream recovery, answer locks, telemetry, and rollback before rollout.

## Secret-manager values

Never commit these values. Configure them per environment in the deployment secret manager and GitHub Secrets/Variables where applicable:

- Node gateway: Firebase Admin credentials, `JWT_ACCESS_SECRET`, `VISUAL_TUTOR_INTERNAL_TOKEN`, `CORS_ALLOWED_ORIGINS`, `AI_SERVICE_BASE_URL`.
- AI service: `SECRET_KEY`, `VISUAL_TUTOR_INTERNAL_TOKEN`, `OPENROUTER_API_KEY` when hosted tutoring is enabled, MongoDB credentials, Redis password, and approved CORS origins.
- Docker: MongoDB root credentials and Redis password.
- Flutter Vercel deployment: `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID_FLUTTER`; repository variables `BACKEND_BASE_URL` and `AI_SERVICE_BASE_URL`.

`VISUAL_TUTOR_INTERNAL_TOKEN` must be the same 32+ character secret in the Node gateway and AI service. Use distinct values for local, staging, and production.

## Deployment

1. Let CI complete on the release commit.
2. CD builds `ai_tutor/build/web`, publishes container images for the Node gateway, AI service, and admin, then deploys the Flutter static bundle.
3. Deploy the exact image tags to staging with secret-manager values; run the staging checklist and verify `/api/v1/health` through the real ingress.
4. Promote the same immutable tags to production. Keep the prior image tags available for rollback.

## Rollback

Rollback means redeploying the prior known-good Node gateway, AI service, admin, and Flutter web versions together. Do not restore learner data unless a separate, tested data-recovery plan requires it. Record image tags, migration status, smoke-test results, and the rollback operator in the incident log.
