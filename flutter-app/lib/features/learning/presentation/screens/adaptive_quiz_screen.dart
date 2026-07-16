import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:ai_tutor_app/core/theme/app_theme.dart';
import 'package:ai_tutor_app/features/learning/presentation/models/tutor_catalog.dart';
import 'package:ai_tutor_app/features/learning/presentation/providers/tutor_catalog_provider.dart';

class AdaptiveQuizScreen extends StatefulWidget {
  const AdaptiveQuizScreen({
    super.key,
    required this.subject,
    required this.topic,
  });

  final TutorSubject subject;
  final TutorTopic topic;

  @override
  State<AdaptiveQuizScreen> createState() => _AdaptiveQuizScreenState();
}

class _AdaptiveQuizScreenState extends State<AdaptiveQuizScreen> {
  int _questionIndex = 0;
  int? _selectedIndex;
  int _score = 0;
  bool _submitted = false;
  String? _attemptId;

  QuizQuestion get _question => widget.topic.quizQuestions[_questionIndex];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final attemptId = await context
          .read<TutorCatalogProvider>()
          .createQuizAttempt(subject: widget.subject, topic: widget.topic);
      if (mounted) {
        setState(() => _attemptId = attemptId);
      }
    });
  }

  Future<void> _submit() async {
    if (_selectedIndex == null || _submitted) return;
    final selectedIndex = _selectedIndex!;
    final isCorrect = selectedIndex == _question.correctIndex;
    setState(() {
      _submitted = true;
      if (isCorrect) {
        _score += 1;
      }
    });
    final attemptId = _attemptId;
    if (attemptId != null) {
      await context.read<TutorCatalogProvider>().submitQuizAnswer(
        attemptId: attemptId,
        questionIndex: _questionIndex,
        question: _question,
        selectedIndex: selectedIndex,
        isCorrect: isCorrect,
      );
    }
  }

  Future<void> _next() async {
    if (_questionIndex >= widget.topic.quizQuestions.length - 1) {
      final attemptId = _attemptId;
      if (attemptId != null) {
        await context.read<TutorCatalogProvider>().completeQuizAttempt(
          attemptId: attemptId,
          score: _score,
          correctCount: _score,
          totalQuestions: widget.topic.quizQuestions.length,
        );
      }
      if (!mounted) return;
      Navigator.of(context).pop();
      return;
    }
    setState(() {
      _questionIndex += 1;
      _selectedIndex = null;
      _submitted = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final accent = widget.subject.color;
    final progress = (_questionIndex + 1) / widget.topic.quizQuestions.length;

    return Scaffold(
      backgroundColor: isDark
          ? AppColors.backgroundDark
          : const Color(0xFFF7FAFF),
      appBar: AppBar(title: const Text('Adaptive Practice')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Question ${_questionIndex + 1} / ${widget.topic.quizQuestions.length}',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 8,
                    ),
                    decoration: BoxDecoration(
                      color: isDark ? AppColors.surfaceDark : Colors.white,
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: Text(
                      '${(_questionIndex + 1) * 2 + 2}:45',
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              ClipRRect(
                borderRadius: BorderRadius.circular(999),
                child: LinearProgressIndicator(
                  value: progress,
                  minHeight: 8,
                  backgroundColor: isDark
                      ? AppColors.surfaceDarkInput
                      : const Color(0xFFE2E8F0),
                  valueColor: AlwaysStoppedAnimation<Color>(accent),
                ),
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  widget.topic.title,
                  style: TextStyle(color: accent, fontWeight: FontWeight.w700),
                ),
              ),
              const SizedBox(height: 16),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  color: isDark ? AppColors.surfaceDark : Colors.white,
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(
                    color: isDark
                        ? AppColors.borderDarkSoft
                        : const Color(0xFFE2E8F0),
                  ),
                ),
                child: Text(
                  _question.question,
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w700,
                    height: 1.35,
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Expanded(
                child: ListView.separated(
                  itemCount: _question.options.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 12),
                  itemBuilder: (context, index) {
                    final isSelected = _selectedIndex == index;
                    final isCorrect = _question.correctIndex == index;
                    final showCorrect = _submitted && isCorrect;
                    final showWrong = _submitted && isSelected && !isCorrect;

                    return InkWell(
                      onTap: _submitted
                          ? null
                          : () => setState(() => _selectedIndex = index),
                      borderRadius: BorderRadius.circular(18),
                      child: Ink(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: showCorrect
                              ? Colors.green.withValues(alpha: 0.10)
                              : showWrong
                              ? Colors.red.withValues(alpha: 0.10)
                              : (isDark ? AppColors.surfaceDark : Colors.white),
                          borderRadius: BorderRadius.circular(18),
                          border: Border.all(
                            color: showCorrect
                                ? AppColors.greenSuccessBright
                                : showWrong
                                ? AppColors.errorBright
                                : isSelected
                                ? accent
                                : (isDark
                                      ? AppColors.borderDarkSoft
                                      : const Color(0xFFD9E3F0)),
                            width: isSelected || showCorrect || showWrong
                                ? 2
                                : 1,
                          ),
                        ),
                        child: Row(
                          children: [
                            Expanded(
                              child: Text(
                                '${String.fromCharCode(65 + index)}. ${_question.options[index]}',
                                style: Theme.of(context).textTheme.bodyLarge
                                    ?.copyWith(
                                      fontWeight: isSelected
                                          ? FontWeight.w700
                                          : FontWeight.w500,
                                    ),
                              ),
                            ),
                            if (showCorrect)
                              const Icon(
                                Icons.check_circle,
                                color: AppColors.greenSuccessBright,
                              )
                            else if (showWrong)
                              const Icon(
                                Icons.cancel,
                                color: AppColors.errorBright,
                              ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
              ),
              if (_submitted) ...[
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: accent.withValues(alpha: 0.10),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Text(
                    _question.explanation,
                    style: TextStyle(
                      color: accent,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                const SizedBox(height: 12),
              ],
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _submitted ? _next : _submit,
                  style: FilledButton.styleFrom(
                    backgroundColor: accent,
                    padding: const EdgeInsets.symmetric(vertical: 18),
                  ),
                  child: Text(
                    _submitted
                        ? (_questionIndex ==
                                  widget.topic.quizQuestions.length - 1
                              ? 'Finish'
                              : 'Next Question')
                        : 'Submit',
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Score: $_score / ${widget.topic.quizQuestions.length}',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: isDark
                      ? AppColors.textMuted
                      : AppColors.textSlateLight,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
