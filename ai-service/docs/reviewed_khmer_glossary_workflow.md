# Reviewed Khmer STEM terminology workflow

Only `ReviewedKhmerGlossarySet` records may supply Khmer technical terms to
Visual Tutor. Each set is scoped to one grade, subject, and lesson, and carries
a glossary version, curriculum version, source ID, and an `approved` reviewer
status. Every included term carries the same evidence.

Authoring `khmer_terms` dictionaries are not student-facing terminology. They
may help a curriculum editor prepare a review, but Visual Tutor ignores them at
the public retrieval and planning boundary.

For a Khmer lesson, use the approved Khmer term while leaving equations, units,
symbols, variables, and chemical notation unchanged. For a bilingual lesson,
write Khmer first and add one short English gloss on the term's first use. Keep
the selected term stable for the rest of the lesson.

If no approved term is available, retain English and create a scope-only
`glossary_gap` review item. It contains the term plus grade, subject, and
lesson—never student text, answer keys, or learner evidence.

## Content status

No reviewed Khmer glossary sets are currently present in the repository. Do
not label examples as reviewed or add Khmer technical translations until an
approved Cambodian curriculum source and reviewer record are supplied. The
release coverage manifest reports the resulting zero coverage by grade and
subject.
