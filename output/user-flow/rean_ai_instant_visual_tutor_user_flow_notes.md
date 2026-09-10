# Rean AI Instant Visual Tutor User Flow Notes

Core message: Rean AI gives students instant help when they are stuck, starting with the most useful hint, visual, or first step. It then adapts until the student understands, while still allowing a verified full solution when necessary.

## PDF Page Descriptions
- 1. **System Overview** - Student-first journey: stuck problem to useful help, verified answer, practice, and progress.
- 2. **Authentication And Onboarding** - Fast account entry, short setup, then dashboard. No unnecessary personal data before learning.
- 3. **Student Dashboard Navigation** - Dashboard prioritizes instant learning actions over passive content browsing.
- 4. **Instant Help Entry Flow** - Submit quickly, acknowledge immediately, analyze in background.
- 5. **Background Question Analysis** - Internal classification supports the first useful intervention but does not become a student-facing setup wizard.
- 6. **Interactive Visual Tutor Loop** - One short message, one matching visual or formula, one focused question, then adaptive evaluation.
- 7. **Progressive Hint And Explain Differently** - Help becomes more direct when the student remains stuck, while alternative teaching strategies prevent repetition.
- 8. **Mathematical Verification And Answer Reveal** - No mathematical result is labelled correct until verification passes or limitations are clearly shown.
- 9. **Understanding Check And Progress Update** - Completion requires demonstrated understanding, not just seeing the final answer.
- 10. **Quiz Flow** - Quizzes can start from dashboard, completed lesson, weak topic, or recommendation.
- 11. **Voice Tutor Flow** - Voice input follows the same visual tutoring and hint rules after transcript confirmation.
- 12. **Profile, Progress, And Reporting** - Students can review learning status, adjust preferences, and report exact tutor responses.
- 13. **Simplified Administrator Flow** - Essential management and AI quality review only; every important action creates an audit log internally.
- 14. **Error And Recovery Flow** - Every error path provides a clear message, retry, safe fallback, return action, and logging where appropriate.
- 15. **Legend, Assumptions, And Excluded Scope** - Legend and scope boundaries for implementation and presentation.

## Assumptions
- Firebase Authentication is the identity provider.
- Flutter mobile owns the student experience.
- Node.js backend owns sessions, persistence, audit logging, and app APIs.
- FastAPI AI Tutor owns problem understanding, teaching strategy, verification routing, and AI-provider integration.
- SymPy or equivalent verification is required before math is marked correct.
- Khmer-first UX is assumed, with English support available.

## Excluded Future Scope
- Parent dashboard
- Teacher dashboard
- Advanced pronunciation scoring
- Full TRACE-CAG research architecture
- Complex admin assignment workflows
- Multi-level admin roles
- Local LLM management
- Advanced enterprise analytics
- Offline AI tutoring

## Decision Points
- Is the student authenticated?
- Has onboarding been completed?
- Which dashboard action was selected?
- Is the problem clear and supported?
- Was student work provided?
- Which first intervention is safest?
- Is the student response correct, partially correct, or incorrect?
- Should support level increase?
- Did mathematical verification pass?
- Did the student request the full solution early?
- Did the student complete guided steps?
- Can the student apply the idea independently?
- Is microphone permission granted?
- Is the transcript accurate?
- Is the admin authorized?
- Is the reported response incorrect or unsafe?
- Is retry available for the current error?

## Error Cases
- No internet
- Authentication failure
- AI timeout
- AI service unavailable
- Invalid structured response
- Failed verification
- Unsupported problem
- Image upload failure
- Audio upload failure
- Quiz loading failure
- Save-progress failure
- Expired session
- Unauthorized admin request

## Draw.io-Compatible Structure
The PNG pages are structured as swimlane flowcharts with stable node labels, lane names, and source Mermaid files. For draw.io recreation, import the Mermaid snippets page-by-page or use the page descriptions as swimlane specifications. Shape mapping: rounded rectangle = process, diamond = decision, pill = start/end, red rounded rectangle = error, yellow note = scope note.
