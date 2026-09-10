# Observability and staging smoke test

## Metrics and alerts

The backend exports service-authenticated counters at `GET /api/v1/health/metrics` with `X-Visual-Tutor-Internal-Token`. Configure the platform collector to scrape it over the private network and export it to Prometheus/OpenTelemetry. Do not expose this endpoint publicly.

Required dashboards and alerts:

| Signal | Dashboard | Alert threshold |
| --- | --- | --- |
| `tutor_response_errors_total` | Tutor reliability | sustained non-zero error rate for 5 minutes |
| `stale_board_conflicts_total` | Board consistency | material increase against normal baseline |
| `curriculum_publish_failures_total` | Curriculum delivery | any failed publish |
| retrieval miss rate / selected chunk count | Retrieval quality | sustained high miss rate per release |
| Admin review queue count | Safety operations | queue age or count beyond operating SLA |
| `student_restriction_events_total` | Safety operations | abnormal rate increase |
| `visual_tutor.board.action` | Board reliability | rendered/validated divergence or skipped spike |
| `visual_tutor.board.action_off_screen` | Board accessibility | any active action off-screen |
| `visual_tutor.retrieval.confidence` | Retrieval quality | low-confidence scope requires clarification |
| `visual_tutor.turn.completed` | Teaching quality | abnormal reteach/reveal or waiting-state drift |

Only bounded labels such as service, operation, HTTP status class, and curriculum generation may be used. Never attach student IDs, session IDs, raw prompts, messages, answers, or tokens as metric labels.

Visual Tutor events additionally permit only bounded action lifecycle/type,
subject/grade/language, tutor move, representation, hint/misconception outcome,
and device class. Client timing values (stream-to-first-visible and
student-response-to-next-action) are numeric metrics, never text payloads.

## Staging smoke procedure

Run only against an isolated staging project with a `smoke-<timestamp>` record prefix and a non-production Admin account.

1. Confirm Admin `/api/health`, backend `/api/v1/health/ready`, and AI private `/api/v1/visual_tutor/readiness` are healthy.
2. Log in through the Admin UI, create grade, subject, topic, content, and a draft curriculum version using the smoke prefix.
3. Submit for review and publish it. Confirm the publisher response records the curriculum version, chunk IDs, checksum, and generation.
4. Query AI readiness and confirm the reported curriculum generation advances. Start a student Tutor session for that exact topic.
5. Assert the public Tutor turn contains only safe curriculum references (`curriculum_version_id`, chunk IDs, grade/subject/topic IDs), and no solver facts, expected step, prompts, hidden answers, or learner-memory data.
6. Submit the expected Step 1 action, confirm Step 2 has a new matching `active_step_id`, then submit a deliberately stale board version and confirm a recoverable 409/snapshot response.
7. File a smoke-prefixed report, resolve it through Admin, and confirm its audit record/restriction action if applicable.
8. Archive/unpublish the smoke curriculum version; confirm retrieval no longer selects it. Delete only smoke-prefixed staging records using the approved cleanup job.

CI must supply secrets through its secret manager: staging Admin credentials, Firebase test credentials, Mongo/Redis URI, OpenRouter staging key, internal service token, and the durable RWX curriculum mount. A missing dependency is a failed smoke run; never substitute demo or local AI providers.
