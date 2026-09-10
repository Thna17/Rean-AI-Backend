# Cambodian Grade 10 Visual Tutor pilot

## Status and entry gate

**Closed by default.** `VISUAL_TUTOR_PILOT_ENABLED=false` is the required
default. Do not enable the pilot until staging has passed every release gate,
including grounded curriculum coverage, reviewed Khmer glossary coverage,
board-runtime matrix, privacy/security review, and rollback rehearsal.

The rollout owner must configure all of these allowlists in the staging secret
manager: `VISUAL_TUTOR_PILOT_GRADES` (only `10`),
`VISUAL_TUTOR_PILOT_SUBJECTS`, `VISUAL_TUTOR_PILOT_LESSONS`, and
`VISUAL_TUTOR_PILOT_LANGUAGE_MODES`. A lesson is eligible only when it is in
these allowlists **and** passes the production curriculum and glossary gates.
Grade 11/12, unreviewed Physics/Chemistry, and low-confidence requests must
receive the normal student-safe clarification/recovery response.

## Teacher-supervised operating model

Start with a named, consented cohort of at most one teacher class. Teachers
observe live sessions, can pause use locally, and submit one of five feedback
categories: `incorrect_curriculum_content`, `unclear_khmer_terminology`,
`confusing_visual_explanation`, `wrong_adaptation`, or `board_rendering_issue`.
Reports contain only the category, approved lesson/version references, severity,
and optional teacher-authored note. Do not collect student text, answers,
session IDs, screenshots, audio, or learner-memory exports in the feedback form.

## Metrics and stop conditions

Monitor lesson completion, next-step correctness, reteach rate, hint rate,
teacher-reported accuracy, and rendering/recovery failure rate as aggregate
ratios. Stop the pilot immediately and disable the flag if any of these occur:

- an incorrect or ungrounded curriculum claim is confirmed;
- an unapproved Khmer term is shown;
- a privacy/security incident or answer-lock bypass is suspected;
- active board content is off-screen or recovery fails repeatedly;
- rendering/recovery failure exceeds 1% or teacher accuracy falls below 95%.

## Incident response and rollback

1. Set `VISUAL_TUTOR_PILOT_ENABLED=false` in the secret manager and roll the
   staging/pilot deployment; verify the flag is false in readiness output.
2. Preserve only non-sensitive operational metrics and teacher report IDs.
3. Remove the affected lesson/version from the allowlist and unpublish it.
4. Restore the prior deployment artifact and run the board restore, answer-lock,
   and curriculum-isolation smoke checks.
5. Notify teachers with the affected lesson label and safe alternative activity;
   do not disclose another learner's data.

## Teacher onboarding and support

Before a class, teachers practise one approved lesson, learn the five feedback
categories, and confirm that the tutor presents one step then waits. Support
uses the incident procedure above; urgent reports are acknowledged during the
teaching day and curriculum/Khmer reports remain blocked until reviewer signoff.
