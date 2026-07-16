import 'package:flutter/material.dart';
import 'package:flutter_math_fork/flutter_math.dart';
import 'package:ai_tutor_app/core/theme/app_theme.dart';

enum TutorLessonSectionType {
  formula,
  symbols,
  given,
  steps,
  finalAnswer,
  explanation,
}

class TutorLessonSection {
  const TutorLessonSection({
    required this.type,
    required this.title,
    required this.lines,
  });

  final TutorLessonSectionType type;
  final String title;
  final List<String> lines;
}

class TutorLessonAnswer {
  const TutorLessonAnswer({required this.sections});

  final List<TutorLessonSection> sections;

  static TutorLessonAnswer? tryParse(String raw) {
    final text = raw
        .replaceAll('\r\n', '\n')
        .replaceAll(RegExp(r'\n{3,}'), '\n\n')
        .trim();
    if (text.isEmpty) return null;

    final expandedText = _expandInlineSectionHeadings(text);

    final sections = _parseLabeledSections(expandedText);
    if (_isUsefulLesson(sections)) {
      return TutorLessonAnswer(sections: sections);
    }

    final inferred = _parseNumberedOrNaturalSections(expandedText);
    if (_isUsefulLesson(inferred)) {
      return TutorLessonAnswer(sections: inferred);
    }

    return null;
  }

  bool get isKhmer {
    return sections.any(
      (section) =>
          RegExp(r'[\u1780-\u17FF]').hasMatch(section.title) ||
          section.lines.any(
            (line) => RegExp(r'[\u1780-\u17FF]').hasMatch(line),
          ),
    );
  }

  static String _expandInlineSectionHeadings(String text) {
    const labels = [
      'FORMULA',
      'SYMBOL',
      'SYMBOLS',
      'GIVEN',
      'STEP',
      'STEPS',
      'FINAL',
      'រូបមន្ត',
      'សមីការ',
      'អត្ថន័យនៃនិមិត្តសញ្ញា',
      'អត្ថន័យនិមិត្តសញ្ញា',
      'តម្លៃដែលបានផ្តល់',
      'តម្លៃដែលបានផ្ដល់',
      'ដំណោះស្រាយជាជំហានៗ',
      'ដំណោះស្រាយជាជំហាន',
      'ចម្លើយចុងក្រោយ',
      'ចម្លើយ',
    ];
    final labelPattern = labels.map(RegExp.escape).join('|');
    final inlineHeadingPattern = RegExp(
      '^($labelPattern)\\s*[:：]\\s*(.+)\$',
      caseSensitive: false,
    );

    final expanded = <String>[];
    for (final line in text.split('\n')) {
      final trimmed = line.trim();
      final match = inlineHeadingPattern.firstMatch(trimmed);
      if (match == null) {
        expanded.add(line);
        continue;
      }

      final label = match.group(1)?.trim();
      final remainder = match.group(2)?.trim();
      if (label == null ||
          label.isEmpty ||
          remainder == null ||
          remainder.isEmpty) {
        expanded.add(line);
        continue;
      }

      expanded
        ..add('$label:')
        ..add(remainder);
    }
    return expanded.join('\n');
  }

  static bool _isUsefulLesson(List<TutorLessonSection> sections) {
    final types = sections.map((section) => section.type).toSet();
    return sections.length >= 2 &&
        (types.contains(TutorLessonSectionType.formula) ||
            types.contains(TutorLessonSectionType.steps)) &&
        types.contains(TutorLessonSectionType.finalAnswer);
  }

  static List<TutorLessonSection> _parseLabeledSections(String text) {
    final headingPattern = RegExp(
      r'^(FORMULA|SYMBOLS?|GIVEN|STEPS?|FINAL|រូបមន្ត|សមីការ|អត្ថន័យនៃនិមិត្តសញ្ញា|អត្ថន័យនិមិត្តសញ្ញា|តម្លៃដែលបានផ្តល់|តម្លៃដែលបានផ្ដល់|ដំណោះស្រាយជាជំហានៗ|ដំណោះស្រាយជាជំហាន|ចម្លើយចុងក្រោយ|ចម្លើយ)\s*:?\s*$',
      caseSensitive: false,
    );
    return _parseByHeadingPattern(text, (line) {
      final match = headingPattern.firstMatch(line.trim());
      if (match == null) return null;
      return _sectionMeta(match.group(1) ?? '');
    });
  }

  static List<TutorLessonSection> _parseNumberedOrNaturalSections(String text) {
    return _parseByHeadingPattern(text, (line) {
      final normalized = line.trim();
      final numbered = RegExp(r'^\d+\.\s+(.+)$').firstMatch(normalized);
      final candidate = numbered?.group(1) ?? normalized;
      return _sectionMeta(candidate);
    }, captureLeadFormula: true);
  }

  static List<TutorLessonSection> _parseByHeadingPattern(
    String text,
    _HeadingMeta? Function(String line) resolveHeading, {
    bool captureLeadFormula = false,
  }) {
    final sections = <TutorLessonSection>[];
    _HeadingMeta? active;
    final buffer = <String>[];

    void flush() {
      final meta = active;
      if (meta == null) return;
      final lines = buffer
          .map((line) => line.trim())
          .where((line) => line.isNotEmpty)
          .toList(growable: false);
      if (lines.isNotEmpty) {
        sections.add(
          TutorLessonSection(type: meta.type, title: meta.title, lines: lines),
        );
      }
      buffer.clear();
    }

    for (final line in text.split('\n')) {
      final meta = resolveHeading(line);
      if (meta != null) {
        flush();
        active = meta;
        continue;
      }

      if (active == null && captureLeadFormula && _looksLikeEquation(line)) {
        active = const _HeadingMeta(TutorLessonSectionType.formula, 'Formula');
      }

      if (active != null) buffer.add(line);
    }
    flush();
    return sections;
  }

  static _HeadingMeta? _sectionMeta(String label) {
    final khmerLabel = label.trim();
    if (khmerLabel.contains('រូបមន្ត') || khmerLabel.contains('សមីការ')) {
      return const _HeadingMeta(TutorLessonSectionType.formula, 'រូបមន្ត');
    }
    if (khmerLabel.contains('អត្ថន័យ') || khmerLabel.contains('និមិត្តសញ្ញា')) {
      return const _HeadingMeta(
        TutorLessonSectionType.symbols,
        'អត្ថន័យនៃនិមិត្តសញ្ញា',
      );
    }
    if (khmerLabel.contains('តម្លៃ') ||
        khmerLabel.contains('បានផ្តល់') ||
        khmerLabel.contains('បានផ្ដល់')) {
      return const _HeadingMeta(
        TutorLessonSectionType.given,
        'តម្លៃដែលបានផ្តល់',
      );
    }
    if (khmerLabel.contains('ដំណោះស្រាយ') || khmerLabel.contains('ជំហាន')) {
      return const _HeadingMeta(
        TutorLessonSectionType.steps,
        'ដំណោះស្រាយជាជំហានៗ',
      );
    }
    if (khmerLabel.contains('ចម្លើយ')) {
      return const _HeadingMeta(
        TutorLessonSectionType.finalAnswer,
        'ចម្លើយចុងក្រោយ',
      );
    }

    final normalized = label
        .toLowerCase()
        .replaceAll(RegExp(r'[^a-z ]+'), ' ')
        .replaceAll(RegExp(r'\s+'), ' ')
        .trim();

    if (normalized.contains('formula') ||
        normalized == 'note' ||
        normalized.startsWith('y ax b')) {
      return const _HeadingMeta(TutorLessonSectionType.formula, 'Formula');
    }
    if (normalized.contains('symbol') ||
        normalized.contains('meaning') ||
        normalized.contains('equation line where')) {
      return const _HeadingMeta(
        TutorLessonSectionType.symbols,
        'Meaning of Symbols',
      );
    }
    if (normalized.contains('given') ||
        normalized.contains('your problem') ||
        normalized.contains('plug in')) {
      return const _HeadingMeta(TutorLessonSectionType.given, 'Given Values');
    }
    if (normalized.contains('step') ||
        normalized.contains('calculation') ||
        normalized.contains('solve')) {
      return const _HeadingMeta(TutorLessonSectionType.steps, 'Step-by-Step');
    }
    if (normalized.contains('final')) {
      return const _HeadingMeta(
        TutorLessonSectionType.finalAnswer,
        'Final Answer',
      );
    }
    if (normalized.contains('slope')) {
      return const _HeadingMeta(TutorLessonSectionType.explanation, 'Concept');
    }
    return null;
  }
}

class _HeadingMeta {
  const _HeadingMeta(this.type, this.title);

  final TutorLessonSectionType type;
  final String title;
}

class TutorLessonAnswerCard extends StatelessWidget {
  const TutorLessonAnswerCard({super.key, required this.answer});

  final TutorLessonAnswer answer;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final primary = AppColorRoles.primary(isDark);

    return Container(
      constraints: const BoxConstraints(maxWidth: 760),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF101B2D) : Colors.white,
        borderRadius: BorderRadius.circular(26),
        border: Border.all(
          color: isDark
              ? Colors.white.withValues(alpha: 0.08)
              : const Color(0xFFE4ECF7),
        ),
        boxShadow: [
          BoxShadow(
            color: isDark
                ? Colors.black.withValues(alpha: 0.25)
                : const Color(0xFF1C4D8F).withValues(alpha: 0.10),
            blurRadius: 24,
            offset: const Offset(0, 12),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(26),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _LessonHeroHeader(
              primary: primary,
              isDark: isDark,
              isKhmer: answer.isKhmer,
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 14, 14, 16),
              child: Column(
                children: [
                  for (final section in answer.sections) ...[
                    _TutorSolutionSection(section: section),
                    if (section != answer.sections.last)
                      const SizedBox(height: 12),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LessonHeroHeader extends StatelessWidget {
  const _LessonHeroHeader({
    required this.primary,
    required this.isDark,
    required this.isKhmer,
  });

  final Color primary;
  final bool isDark;
  final bool isKhmer;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: isDark
              ? [const Color(0xFF123D68), const Color(0xFF101B2D)]
              : [const Color(0xFFEAF4FF), const Color(0xFFF7FBFF)],
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 46,
            height: 46,
            decoration: BoxDecoration(
              color: primary,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                  color: primary.withValues(alpha: 0.28),
                  blurRadius: 16,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: const Icon(
              Icons.school_rounded,
              color: Colors.white,
              size: 25,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  isKhmer ? 'មេរៀនខ្លី' : 'Mini Lesson',
                  style: TextStyle(
                    color: isDark ? Colors.white : AppColors.textDark,
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                    letterSpacing: -0.4,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  isKhmer
                      ? 'រូបមន្ត ជំហាន និងចម្លើយចុងក្រោយ'
                      : 'Clear formula, steps, and final answer',
                  style: TextStyle(
                    color: isDark
                        ? Colors.white.withValues(alpha: 0.68)
                        : AppColors.textGrey,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
            decoration: BoxDecoration(
              color: isDark
                  ? Colors.white.withValues(alpha: 0.10)
                  : Colors.white.withValues(alpha: 0.82),
              borderRadius: BorderRadius.circular(999),
              border: Border.all(
                color: isDark
                    ? Colors.white.withValues(alpha: 0.10)
                    : const Color(0xFFD7E7FA),
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.verified_rounded, color: primary, size: 15),
                const SizedBox(width: 5),
                Text(
                  isKhmer ? 'គ្រូ AI' : 'Tutor',
                  style: TextStyle(
                    color: isDark ? Colors.white : AppColors.textDark,
                    fontSize: 12,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _TutorSolutionSection extends StatelessWidget {
  const _TutorSolutionSection({required this.section});

  final TutorLessonSection section;

  @override
  Widget build(BuildContext context) {
    if (section.type == TutorLessonSectionType.finalAnswer) {
      return _FinalAnswerSection(section: section);
    }
    if (section.type == TutorLessonSectionType.steps) {
      return _TutorStepTimeline(section: section);
    }

    final isDark = Theme.of(context).brightness == Brightness.dark;
    final accent = _sectionAccent(section.type);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isDark
            ? Colors.white.withValues(alpha: 0.045)
            : accent.withValues(alpha: 0.055),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: isDark
              ? Colors.white.withValues(alpha: 0.07)
              : accent.withValues(alpha: 0.15),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SectionTitle(section: section),
          const SizedBox(height: 10),
          for (final line in section.lines) ...[
            _LessonLine(line: line),
            if (line != section.lines.last) const SizedBox(height: 8),
          ],
        ],
      ),
    );
  }
}

class _TutorStepTimeline extends StatelessWidget {
  const _TutorStepTimeline({required this.section});

  final TutorLessonSection section;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final steps = _splitSteps(section.lines);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isDark
            ? Colors.white.withValues(alpha: 0.045)
            : const Color(0xFFF8FBFF),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: isDark
              ? Colors.white.withValues(alpha: 0.07)
              : const Color(0xFFE2ECF8),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SectionTitle(section: section),
          const SizedBox(height: 12),
          for (var i = 0; i < steps.length; i++)
            _TimelineStep(
              index: i,
              lines: steps[i],
              isLast: i == steps.length - 1,
            ),
        ],
      ),
    );
  }
}

class _TimelineStep extends StatelessWidget {
  const _TimelineStep({
    required this.index,
    required this.lines,
    required this.isLast,
  });

  final int index;
  final List<String> lines;
  final bool isLast;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final primary = AppColorRoles.primary(isDark);

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            children: [
              Container(
                width: 28,
                height: 28,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: primary,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '${index + 1}',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 13,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              if (!isLast)
                Expanded(
                  child: Container(
                    width: 2,
                    margin: const EdgeInsets.symmetric(vertical: 5),
                    color: primary.withValues(alpha: 0.20),
                  ),
                ),
            ],
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(bottom: isLast ? 0 : 14),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: isDark ? const Color(0xFF162236) : Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: isDark
                        ? Colors.white.withValues(alpha: 0.06)
                        : const Color(0xFFE8EEF7),
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (final line in lines) ...[
                      _LessonLine(line: line),
                      if (line != lines.last) const SizedBox(height: 8),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _FinalAnswerSection extends StatelessWidget {
  const _FinalAnswerSection({required this.section});

  final TutorLessonSection section;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: isDark
              ? [const Color(0xFF0E7A73), const Color(0xFF155EBA)]
              : [const Color(0xFFE7FFF8), const Color(0xFFEAF3FF)],
        ),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(
          color: isDark
              ? Colors.white.withValues(alpha: 0.12)
              : const Color(0xFFBCEBDF),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: isDark
                      ? Colors.white.withValues(alpha: 0.14)
                      : const Color(0xFF12B886).withValues(alpha: 0.13),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  Icons.check_circle_rounded,
                  color: isDark ? Colors.white : const Color(0xFF0D8F68),
                  size: 20,
                ),
              ),
              const SizedBox(width: 10),
              Text(
                section.title,
                style: TextStyle(
                  color: isDark ? Colors.white : const Color(0xFF063F34),
                  fontSize: 15,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          for (final line in section.lines) ...[
            _LessonLine(line: line, emphasized: true),
            if (line != section.lines.last) const SizedBox(height: 8),
          ],
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.section});

  final TutorLessonSection section;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final accent = _sectionAccent(section.type);
    return Row(
      children: [
        Container(
          width: 34,
          height: 34,
          decoration: BoxDecoration(
            color: accent.withValues(alpha: isDark ? 0.18 : 0.12),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(_sectionIcon(section.type), color: accent, size: 19),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            section.title,
            style: TextStyle(
              color: isDark ? Colors.white : AppColors.textDark,
              fontSize: 15,
              fontWeight: FontWeight.w900,
              letterSpacing: -0.2,
            ),
          ),
        ),
      ],
    );
  }
}

class _LessonLine extends StatelessWidget {
  const _LessonLine({required this.line, this.emphasized = false});

  final String line;
  final bool emphasized;

  @override
  Widget build(BuildContext context) {
    final cleaned = _cleanLine(line);
    if (cleaned.isEmpty) return const SizedBox.shrink();
    if (_looksLikeEquation(cleaned)) {
      return _TutorEquationBlock(expression: cleaned, emphasized: emphasized);
    }

    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Text(
      cleaned,
      style: TextStyle(
        color: isDark
            ? Colors.white.withValues(alpha: 0.86)
            : AppColors.textSlateLight,
        fontSize: emphasized ? 16 : 14,
        height: 1.45,
        fontWeight: emphasized ? FontWeight.w800 : FontWeight.w600,
      ),
    );
  }
}

class _TutorEquationBlock extends StatelessWidget {
  const _TutorEquationBlock({
    required this.expression,
    required this.emphasized,
  });

  final String expression;
  final bool emphasized;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final primary = AppColorRoles.primary(isDark);
    final tex = _toTexExpression(expression);

    return Container(
      width: double.infinity,
      padding: EdgeInsets.symmetric(
        horizontal: emphasized ? 16 : 12,
        vertical: emphasized ? 14 : 11,
      ),
      decoration: BoxDecoration(
        color: emphasized
            ? (isDark
                  ? Colors.white.withValues(alpha: 0.14)
                  : Colors.white.withValues(alpha: 0.92))
            : (isDark
                  ? Colors.black.withValues(alpha: 0.16)
                  : const Color(0xFFF2F7FF)),
        borderRadius: BorderRadius.circular(emphasized ? 18 : 14),
        border: Border.all(
          color: emphasized
              ? primary.withValues(alpha: 0.30)
              : primary.withValues(alpha: 0.13),
        ),
      ),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Math.tex(
          tex,
          textStyle: TextStyle(
            color: emphasized
                ? (isDark ? Colors.white : const Color(0xFF063F34))
                : (isDark ? Colors.white : AppColors.textDark),
            fontSize: emphasized ? 21 : 18,
            fontWeight: FontWeight.w800,
          ),
          onErrorFallback: (error) => Text(
            expression,
            style: TextStyle(
              color: isDark ? Colors.white : AppColors.textDark,
              fontSize: emphasized ? 18 : 15,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
      ),
    );
  }
}

List<List<String>> _splitSteps(List<String> lines) {
  final steps = <List<String>>[];
  var current = <String>[];
  final stepStart = RegExp(r'^(?:\d+\.|Step\s+\d+:)', caseSensitive: false);

  for (final line in lines) {
    final cleaned = line.trim();
    if (stepStart.hasMatch(cleaned) && current.isNotEmpty) {
      steps.add(current);
      current = <String>[];
    }
    current.add(cleaned.replaceFirst(RegExp(r'^\d+\.\s*'), ''));
  }
  if (current.isNotEmpty) steps.add(current);
  return steps.isEmpty ? [lines] : steps;
}

String _cleanLine(String line) {
  return line
      .trim()
      .replaceFirst(RegExp(r'^[-•]\s*'), '')
      .replaceFirst(RegExp(r'^equation\s*:\s*', caseSensitive: false), '')
      .replaceAll(r'\(', '')
      .replaceAll(r'\)', '')
      .trim();
}

bool _looksLikeEquation(String line) {
  final cleaned = _cleanLine(line);
  final lower = cleaned.toLowerCase();
  if (cleaned.contains(r'\frac') ||
      cleaned.contains(r'\boxed') ||
      cleaned.startsWith(r'\[') ||
      cleaned.startsWith('[')) {
    return true;
  }
  if (cleaned.contains(':') && !lower.startsWith('so:')) {
    return false;
  }
  if (RegExp(r'[.!?]$').hasMatch(cleaned)) {
    return false;
  }
  if (RegExp(r'\s').allMatches(cleaned).length > 5) {
    return false;
  }
  if (RegExp(r'(=>|=|÷|\+|-|\*)').hasMatch(cleaned) &&
      RegExp(r'[0-9a-zA-Z]').hasMatch(cleaned)) {
    return cleaned.length <= 90;
  }
  return false;
}

String _toTexExpression(String line) {
  var expression = _cleanLine(line)
      .replaceAll('=>', r'\Rightarrow ')
      .replaceAll('so:', '')
      .replaceAll('so：', '')
      .trim();

  expression = expression
      .replaceAll(RegExp(r'^\[\s*'), '')
      .replaceAll(RegExp(r'\s*\]$'), '')
      .replaceAll(RegExp(r'^\\\[\s*'), '')
      .replaceAll(RegExp(r'\s*\\\]$'), '')
      .replaceAll(RegExp(r'^\$\$?\s*'), '')
      .replaceAll(RegExp(r'\s*\$\$?$'), '')
      .trim();

  return expression;
}

Color _sectionAccent(TutorLessonSectionType type) {
  return switch (type) {
    TutorLessonSectionType.formula => const Color(0xFF2563EB),
    TutorLessonSectionType.symbols => const Color(0xFF7C3AED),
    TutorLessonSectionType.given => const Color(0xFF0891B2),
    TutorLessonSectionType.steps => const Color(0xFFEA580C),
    TutorLessonSectionType.finalAnswer => const Color(0xFF12B886),
    TutorLessonSectionType.explanation => const Color(0xFFF59E0B),
  };
}

IconData _sectionIcon(TutorLessonSectionType type) {
  return switch (type) {
    TutorLessonSectionType.formula => Icons.functions_rounded,
    TutorLessonSectionType.symbols => Icons.account_tree_rounded,
    TutorLessonSectionType.given => Icons.fact_check_rounded,
    TutorLessonSectionType.steps => Icons.route_rounded,
    TutorLessonSectionType.finalAnswer => Icons.verified_rounded,
    TutorLessonSectionType.explanation => Icons.lightbulb_rounded,
  };
}
