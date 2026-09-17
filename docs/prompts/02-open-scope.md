Ignore CLAUDE.md in this directory — it describes a different project
(LexiLingo) and none of its paths exist here. Read GEMINI.md instead, fully,
before doing anything. It is the real context for this repository.

This task is prompt 2 in docs/ai-work-prompts.md: open the tutor to Grade 12
Mathematics, Physics and Chemistry. But first there is unfinished work in the
tree that must be closed out on its own.

== Step 0: finish the scan removal (prompt 1) before touching scope ==

The scan/photo feature has already been removed, but it is uncommitted and
unverified, in three repos:
  ai-service (outer repo): main.py, orchestrator.py,
    test_visual_tutor_production_config.py modified; visual_tutor_scan.py and
    test_visual_tutor_scan.py deleted
  ai_tutor (its own repo): tutor_shell.dart, visual_tutor_design.dart,
    dashboard_screen.dart, learning_selection_repository.dart and others
    modified; scan_problem_screen.dart and scan_problem_repository.dart deleted
  backend-ai-tutor (its own repo): tutor controller, routes, service, and
    tutor-api.test.ts modified

Verify it: each app builds, nothing still references the removed code, and each
test suite is no worse than the baseline in GEMINI.md §6. Check that removed
buttons did not leave a gap in any layout. Then commit it in each repo as its own
commit ("remove the scan feature"), separately from the scope work. Commit only
the scan-removal files — not docs/prompts/ or anything else. If something is
broken, fix it or tell me — do not start Step 1 on top of a broken tree.

== Step 1: open the scope ==

Today only Grade 12 limits get through. Two separate gates must BOTH change,
and changing only one still returns 403:

  1. ai-service/api/core/config.py:332 — VISUAL_TUTOR_SCOPE_LOCK, default
     "grade12_math_limits"
  2. ai-service/api/services/visual_tutor/pilot.py — enforce_pilot_scope(),
     driven by VISUAL_TUTOR_PILOT_GRADES / _SUBJECTS / _LESSONS /
     _LANGUAGE_MODES (config.py ~345), returns 403 outside the allow-list

The client also hard-codes the limits scope:
  ai_tutor/lib/screens/lessons/local_mvp_limits_scope.dart

Target: Grade 12 only; Mathematics, Physics, Chemistry; language modes english
and khmer. Everything else stays refused — Grade 10, Grade 11, and any other
subject such as biology.

Define the scope as data in one place that answers "is this grade + subject +
topic in scope?", and have both server gates use it. Keep the client's idea of
the scope consistent with the server's; a lesson the client offers must not be
refused by the server.

== Step 2: be honest about what we can't teach yet ==

Opening physics and chemistry does not mean we can solve them. Only limits have a
sympy-grounded worked solution (api/services/visual_tutor/worked_solution.py);
physics and chemistry solvers are prompts 3 and 4, not this task.

Find out what happens today when an in-scope question has no solver. If it falls
through to the LLM planner and the model does the arithmetic unchecked, that is
not acceptable for a student: return an honest "this topic isn't ready yet" in
the student's language instead. Do not build the solvers in this task.

== Step 3: refusal messages ==

A refused student must be told what they CAN ask — Grade 12 maths, physics or
chemistry — in their own language (Khmer or English), not a bare 403 message.

== Constraints ==

- Do not widen response_sanitizer.py or the teaching-plan contract to make any
  of this work. They exist so the tutor cannot leak answers or drift.
- Do not break the board invariants in GEMINI.md §5.
- Do not run the full ai-service suite: it runs out of memory on this 8 GB Mac.
  Use the fast command in GEMINI.md §6 plus the tests for what you changed.
- test_visual_tutor_routes.py has 3 pre-existing failures with an unknown
  cause (not the scope lock — the test setup disables it). Do not investigate
  them in this task; report whether their count changed.

== Done when ==

- Tests cover, for EACH of the three subjects, one in-scope request that gets
  through and one out-of-scope request that is refused; plus a Grade 10 request
  and a Grade 12 biology request, both refused with a helpful message.
- An in-scope physics or chemistry question with no solver gets the honest
  "not ready yet" response, covered by a test.
- Each new test fails on the old code before your change — run it that way once
  and say that you did.
- Each repo's suite is no worse than the GEMINI.md §6 baseline.

Commit per repo with clear messages. Do not push — I will review first.

When you finish, report: what changed in each repo, the real test numbers before
and after, which of the 3 pre-existing route failures you resolved and how, and
anything you did not verify.
