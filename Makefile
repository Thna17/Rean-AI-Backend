.DEFAULT_GOAL := help

FLUTTER ?= flutter
DART ?= dart
PYTHON ?= venv/bin/python3

.PHONY: help
help: ## Show available commands
	@printf "ReanAI monorepo commands (run from repo root)\n\n"
	@printf "Usage:\n  make <target>\n\n"
	@printf "Targets:\n"
	@grep -E '^[a-zA-Z0-9_\-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-22s %s\n", $$1, $$2}'

# ── Flutter Student App (ai_tutor) ──────────────────────────────────────────

.PHONY: flutter-doctor
flutter-doctor: ## Run flutter doctor in ai_tutor
	@cd ai_tutor && $(FLUTTER) doctor

.PHONY: flutter-get
flutter-get: ## Install dependencies in ai_tutor
	@cd ai_tutor && $(FLUTTER) pub get

.PHONY: flutter-clean
flutter-clean: ## Clean Flutter build artifacts in ai_tutor
	@cd ai_tutor && $(FLUTTER) clean

.PHONY: flutter-analyze
flutter-analyze: ## Analyze Dart code in ai_tutor
	@cd ai_tutor && $(FLUTTER) analyze

.PHONY: flutter-test
flutter-test: ## Run Flutter tests in ai_tutor
	@cd ai_tutor && $(FLUTTER) test

.PHONY: flutter-test-tutor
flutter-test-tutor: ## Run visual tutor whiteboard tests in ai_tutor
	@cd ai_tutor && $(FLUTTER) test test/features/visual_tutor

.PHONY: flutter-build-web
flutter-build-web: ## Build web release bundle with --pwa-strategy=none
	@cd ai_tutor && $(FLUTTER) build web --pwa-strategy=none

.PHONY: flutter-serve-web
flutter-serve-web: ## Serve Flutter web app on port 53124
	@cd ai_tutor && python3 tool/serve_web.py 53124

# ── AI Service (ai-service) ──────────────────────────────────────────────────

.PHONY: ai-test
ai-test: ## Run visual tutor tests in ai-service
	@cd ai-service && $(PYTHON) -m pytest -q \
		tests/test_visual_tutor_worked_solution.py \
		tests/test_local_limits_demo.py \
		tests/test_visual_tutor_teaching_plan_contract.py \
		tests/test_universal_stem_solutions.py

.PHONY: ai-run
ai-run: ## Run AI service on port 8001
	@cd ai-service && $(PYTHON) -m uvicorn api.main:app --reload --port 8001

# ── Backend Gateway (backend-ai-tutor) ────────────────────────────────────────

.PHONY: gateway-dev
gateway-dev: ## Run Express gateway in development mode on port 4000
	@cd backend-ai-tutor/backend && npm run dev

.PHONY: gateway-test
gateway-test: ## Run gateway tests
	@cd backend-ai-tutor/backend && npm test

.PHONY: gateway-build
gateway-build: ## Build TypeScript gateway
	@cd backend-ai-tutor/backend && npm run build

# ── Admin Dashboard (admin-ai-tutor) ─────────────────────────────────────────

.PHONY: admin-dev
admin-dev: ## Run admin Next.js dashboard on port 3000
	@cd admin-ai-tutor && npm run dev

.PHONY: admin-build
admin-build: ## Build admin Next.js dashboard
	@cd admin-ai-tutor && npm run build
