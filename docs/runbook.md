# ReanAI Monorepo Runbook

This runbook documents procedures for verifying clean installs, avoiding truncated dependency issues, and validating all four codebases before release.

---

## 1. Overview of Codebases

ReanAI consists of four primary codebases under the repository root:

| Codebase | Technology | Role |
|---|---|---|
| `ai-service/` | Python 3.11 (`venv/`), FastAPI | AI Brain: Solvers (Sympy), DeepSeek LLM, RAG curriculum gate, SSE streaming |
| `backend-ai-tutor/backend/` | Node 20, Express, TypeScript | Gateway: Firebase Auth, Rate limiting, Session proxy, Admin API |
| `ai_tutor/` | Flutter (Web + Mobile) | Student App: Whiteboard Canvas, Audio/Speech, Catalog navigation |
| `admin-ai-tutor/` | Next.js 16, React 19, TypeScript | Admin Portal: Curriculum authoring/publishing, telemetry review |

---

## 2. Verify a Clean Install

To avoid dependency drift and corrupted or truncated installations:

1. **Use `npm ci`, never `npm install`**, for `backend-ai-tutor/backend` and `admin-ai-tutor`.
   - `npm ci` strictly respects `package-lock.json` and deletes any existing `node_modules/` before reinstalling, ensuring lockfile authoritativeness.
   - `npm install` can silently modify the lockfile or leave incomplete dependencies behind.

2. **Always invoke `venv/bin/python3` explicitly** in `ai-service`:
   - A bare `python3` after `source venv/bin/activate` in non-interactive subshells may resolve to the macOS system Python 3.9.
   - System Python 3.9 cannot evaluate Python 3.10+ union syntax (`str | None`), producing dozens of misleading collection errors.

3. **Verify native binaries in `admin-ai-tutor`**:
   - Next.js requires platform-specific native Rust binaries (`@next/swc-*`).
   - A network interruption or truncated install can leave `node_modules/@next/swc-<platform>/` containing only `README.md` and `package.json` while missing the ~88 MB `next-swc.<platform>.node` binary.
   - When missing or truncated (< 10 MB), Next.js fails during `npm run build` with:
     ```text
     Error: Failed to load SWC binary for darwin/arm64
     ```
   - **Verification command**:
     ```bash
     cd admin-ai-tutor
     ls -lh node_modules/@next/swc-*/next-swc.*.node
     # Ensure the file exists and is ~88 MB
     ```
   - **Remediation**:
     If truncated, reinstall the platform package or perform a clean reinstall:
     ```bash
     cd admin-ai-tutor && npm ci
     # Or reinstall the specific native package:
     # macOS Apple Silicon:
     npm install @next/swc-darwin-arm64
     # macOS Intel:
     npm install @next/swc-darwin-x64
     # Linux x64:
     npm install @next/swc-linux-x64-gnu
     ```

---

## 3. Pre-Release Verification Commands

Before merging or cutting any release, all commands below must pass across the four codebases:

```bash
# 1. AI Service — full test suite
cd ai-service && venv/bin/python3 -m pytest -q                      # ~1,460 passed

# 2. Student App — static analysis & unit tests
cd ai_tutor && flutter analyze && flutter test                      # clean, 400 passed

# 3. Student App — web production bundle build
cd ai_tutor && flutter build web --pwa-strategy=none                # succeeds

# 4. Gateway — clean install, test suite & TypeScript typecheck
cd backend-ai-tutor/backend && npm ci && npm test && npx tsc --noEmit # passes

# 5. Admin Portal — clean install & Next.js production build
cd admin-ai-tutor && npm ci && npm run build                        # succeeds
```

---

## 4. CI Native Binary Guard

GitHub Actions CI (`.github/workflows/ci.yml`) enforces the native binary check automatically in the `admin` job:

```yaml
- name: Verify native binaries
  run: |
    SWC_BINARIES=(node_modules/@next/swc-*/next-swc.*.node)
    if [ ! -e "${SWC_BINARIES[0]}" ]; then
      echo "::error::Required Next.js SWC native binary missing in node_modules/@next/swc-*/"
      exit 1
    fi
    FILESIZE=$(stat -c%s "${SWC_BINARIES[0]}" 2>/dev/null || stat -f%z "${SWC_BINARIES[0]}" 2>/dev/null || echo 0)
    if [ "$FILESIZE" -lt 10485760 ]; then
      echo "::error::Next.js SWC binary appears truncated or corrupted (size: $FILESIZE bytes, expected > 10MB)"
      exit 1
    fi
```

If the binary is missing or smaller than 10 MB, CI aborts before `npm run build`, surfacing actionable diagnostics.
