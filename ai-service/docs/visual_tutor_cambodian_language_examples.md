# Cambodian Visual Tutor language examples

Language mode changes spoken and ordinary board text only. Equations, symbols,
units, formulae, and chemical notation remain universal.

## Mathematics — approved glossary available

Curriculum source: `math.g10.linear_equations.one_variable`.

- Khmer: `សូមមើលសមីការលីនេអ៊ែរ 2x + 5 = 15។ តើចំនួនថេរមួយណាត្រូវដកចេញទាំងសងខាង?`
- Bilingual: `សមីការលីនេអ៊ែរ (linear equation): 2x + 5 = 15. Which ចំនួនថេរ (constant) should we remove first?`

The terms `សមីការលីនេអ៊ែរ`, `ចំនួនថេរ`, and `ទាំងសងខាង` are values in the
approved curriculum `khmer_terms` map.

## Physics — glossary gap is visible, not invented

- Khmer: `សូមមើលរូបនេះ។ តើព្រួញណាចង្អុលចុះក្រោម?`
- Bilingual: `សូមមើលរូបនេះ។ Which arrow points downward?`

If the lesson needs a Khmer technical label for `force`, the planner keeps the
English label and emits `glossary_gaps: ["force"]` until curriculum review adds
an approved term.

## Chemistry — notation stays universal

- Khmer: `សូមមើល H₂ + O₂ → H₂O។ តើលេខណាត្រូវកែដំបូង?`
- Bilingual: `សូមមើល H₂ + O₂ → H₂O។ Which coefficient should we change first?`

If an approved Khmer term for `coefficient` is unavailable in the selected
Chemistry lesson, it remains English and is placed in `glossary_gaps`; the tutor
does not manufacture a Khmer translation.
