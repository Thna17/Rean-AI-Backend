import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:ai_tutor_app/core/theme/app_theme.dart';
import 'package:ai_tutor_app/features/learning/presentation/models/tutor_catalog.dart';
import 'package:ai_tutor_app/features/learning/presentation/providers/tutor_catalog_provider.dart';

class GuidedProblemSolvingScreen extends StatefulWidget {
  const GuidedProblemSolvingScreen({
    super.key,
    required this.subject,
    required this.topic,
  });

  final TutorSubject subject;
  final TutorTopic topic;

  @override
  State<GuidedProblemSolvingScreen> createState() =>
      _GuidedProblemSolvingScreenState();
}

class _GuidedProblemSolvingScreenState
    extends State<GuidedProblemSolvingScreen> {
  final TextEditingController _answerController = TextEditingController();
  int _stepIndex = 0;
  String? _feedback;
  bool _showAnswerReveal = false;
  String? _attemptId;

  GuidedProblem get _problem => widget.topic.guidedProblem;
  GuidedStep get _currentStep => _problem.steps[_stepIndex];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final attemptId = await context
          .read<TutorCatalogProvider>()
          .createGuidedAttempt(subject: widget.subject, topic: widget.topic);
      if (mounted) {
        setState(() => _attemptId = attemptId);
      }
    });
  }

  @override
  void dispose() {
    _answerController.dispose();
    super.dispose();
  }

  Future<void> _checkStep() async {
    final answer = _answerController.text.trim();
    if (answer.isEmpty) {
      setState(() => _feedback = 'Write your next step before checking.');
      return;
    }

    final currentIndex = _stepIndex;
    final feedback =
        'Good direction. Focus on ${_currentStep.explanation.toLowerCase()}.';
    final isComplete = currentIndex >= _problem.steps.length - 1;
    setState(() {
      _feedback = feedback;
      if (!isComplete) {
        _stepIndex += 1;
        _answerController.clear();
      } else {
        _showAnswerReveal = true;
      }
    });
    final attemptId = _attemptId;
    if (attemptId != null) {
      await context.read<TutorCatalogProvider>().submitGuidedStep(
        attemptId: attemptId,
        stepIndex: currentIndex,
        studentAnswer: answer,
        expectedStep: _problem.expectedNextStep,
        feedback: feedback,
        isCorrect: true,
        completeAttempt: isComplete,
      );
      if (isComplete && mounted) {
        await context.read<TutorCatalogProvider>().loadDashboard();
      }
    }
  }

  Future<void> _showHint() async {
    setState(() => _feedback = _currentStep.hint);
    final attemptId = _attemptId;
    if (attemptId != null) {
      await context.read<TutorCatalogProvider>().submitGuidedStep(
        attemptId: attemptId,
        stepIndex: _stepIndex,
        studentAnswer: '',
        expectedStep: _problem.expectedNextStep,
        feedback: _currentStep.hint,
        isCorrect: false,
        hintRequested: true,
      );
    }
  }

  void _showExplanation() {
    setState(() => _feedback = _currentStep.explanation);
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final accent = widget.subject.color;

    return Scaffold(
      backgroundColor: isDark
          ? AppColors.backgroundDark
          : const Color(0xFFF6FAFF),
      appBar: AppBar(title: const Text('Visual Tutor')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
          children: [
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [accent, accent.withValues(alpha: 0.78)],
                ),
                borderRadius: BorderRadius.circular(24),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    widget.topic.title,
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                      fontSize: 14,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    _problem.prompt,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 26,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    _problem.coachIntro,
                    style: const TextStyle(color: Colors.white, fontSize: 15),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Container(
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
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      CircleAvatar(
                        backgroundColor: accent.withValues(alpha: 0.12),
                        child: Icon(
                          Icons.psychology_alt_rounded,
                          color: accent,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          _currentStep.title,
                          style: Theme.of(context).textTheme.titleLarge
                              ?.copyWith(fontWeight: FontWeight.w700),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Text(
                    _currentStep.explanation,
                    style: Theme.of(
                      context,
                    ).textTheme.bodyLarge?.copyWith(height: 1.5),
                  ),
                  const SizedBox(height: 16),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: isDark
                          ? AppColors.surfaceDarkInput
                          : const Color(0xFFF8FBFF),
                      borderRadius: BorderRadius.circular(18),
                    ),
                    child: Text(
                      'Your turn: ${_problem.expectedNextStep}',
                      style: TextStyle(
                        color: isDark
                            ? AppColors.textOnDarkPrimary
                            : AppColors.textDark,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: _answerController,
                    minLines: 1,
                    maxLines: 3,
                    decoration: InputDecoration(
                      hintText: 'Enter your next step...',
                      filled: true,
                      fillColor: isDark
                          ? AppColors.surfaceDarkInput
                          : Colors.white,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(16),
                        borderSide: BorderSide(
                          color: isDark
                              ? AppColors.borderDarkSoft
                              : const Color(0xFFD7E3F3),
                        ),
                      ),
                    ),
                  ),
                  if (_feedback != null) ...[
                    const SizedBox(height: 14),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: accent.withValues(alpha: 0.10),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: Text(
                        _feedback!,
                        style: TextStyle(
                          color: accent,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                  if (_showAnswerReveal) ...[
                    const SizedBox(height: 14),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.green.withValues(alpha: 0.10),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: Text(
                        'Final check: ${_problem.steps.last.explanation}',
                        style: const TextStyle(
                          color: AppColors.greenSuccessDark,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: FilledButton(
                    onPressed: _checkStep,
                    style: FilledButton.styleFrom(
                      backgroundColor: accent,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                    child: const Text('Check'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton(
                    onPressed: _showHint,
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                    child: const Text('Need Hint'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton(
                    onPressed: _showExplanation,
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                    child: const Text('Explain Step'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
