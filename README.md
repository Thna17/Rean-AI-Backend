# ReanAI Visual Tutor

ReanAI is a Khmer-first, interactive STEM tutor for Cambodian Grade 10–12 students. The Flutter client displays safe, typed whiteboard actions while the Node gateway and Python AI service enforce tutoring, curriculum, and privacy rules.

## Current services

| Service | Directory | Entrypoint | Default local port |
| --- | --- | --- | --- |
| Learner app | `ai_tutor` | `lib/main.dart` | Flutter-selected |
| API gateway | `backend-ai-tutor/backend` | `src/server.ts` | 4000 |
| AI and curriculum service | `ai-service` | `api/main.py` | 8001 |
| Admin web app | `admin-ai-tutor` | Next.js `app/` | 3000 |

There is no deployable `flutter-app`, `backend-service`, `admin-service`, or `mcp-server` directory in this repository.

## Start here

- [Architecture](docs/ARCHITECTURE.md)
- [Local development](docs/LOCAL_DEVELOPMENT.md)
- [Release runbook](docs/RELEASE_RUNBOOK.md)
- [Known limitations](docs/KNOWN_LIMITATIONS.md)
- [Work Roadmap Prompts](docs/ai-work-prompts.md)

For a clean-checkout verification, run:

```bash
./scripts/verify-clean-checkout.sh
```

This command installs dependencies and runs checks; it does not deploy.
