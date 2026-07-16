import 'package:flutter/material.dart';
import 'package:ai_tutor_app/core/theme/app_theme.dart';
import 'package:ai_tutor_app/features/learning/presentation/models/tutor_catalog.dart';
import 'package:ai_tutor_app/features/learning/presentation/providers/tutor_catalog_provider.dart';
import 'package:ai_tutor_app/features/learning/presentation/screens/adaptive_quiz_screen.dart';
import 'package:ai_tutor_app/features/learning/presentation/screens/guided_problem_solving_screen.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/presentation/pages/ai_tutor_chat_page.dart';
import 'package:provider/provider.dart';

class SubjectSelectionScreen extends StatefulWidget {
  const SubjectSelectionScreen({super.key});

  @override
  State<SubjectSelectionScreen> createState() => _SubjectSelectionScreenState();
}

class _SubjectSelectionScreenState extends State<SubjectSelectionScreen> {
  final TextEditingController _searchController = TextEditingController();
  String _selectedSubjectId = TutorCatalog.subjects.first.id;

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<TutorCatalogProvider>().loadSubjects();
    });
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final catalogProvider = context.watch<TutorCatalogProvider>();
    final subjects = catalogProvider.subjects;
    final selectedSubject = subjects.firstWhere(
      (subject) => subject.id == _selectedSubjectId,
      orElse: () =>
          subjects.isNotEmpty ? subjects.first : TutorCatalog.byId('math'),
    );
    final query = _searchController.text.trim().toLowerCase();
    final topics = selectedSubject.topics
        .where((topic) {
          if (query.isEmpty) return true;
          return topic.title.toLowerCase().contains(query) ||
              topic.subtitle.toLowerCase().contains(query);
        })
        .toList(growable: false);

    return Scaffold(
      backgroundColor: isDark
          ? AppColors.backgroundDark
          : const Color(0xFFF5F8FE),
      appBar: AppBar(title: const Text('Choose a Subject'), centerTitle: true),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
          children: [
            TextField(
              controller: _searchController,
              onChanged: (_) => setState(() {}),
              decoration: InputDecoration(
                hintText: 'Search subjects or topics...',
                prefixIcon: const Icon(Icons.search_rounded),
                filled: true,
                fillColor: isDark ? AppColors.surfaceDark : Colors.white,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(18),
                  borderSide: BorderSide.none,
                ),
              ),
            ),
            const SizedBox(height: 18),
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: subjects.length,
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 3,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                childAspectRatio: 1.02,
              ),
              itemBuilder: (context, index) {
                final subject = subjects[index];
                final isSelected = subject.id == _selectedSubjectId;
                return _SubjectCard(
                  subject: subject,
                  isSelected: isSelected,
                  onTap: () => setState(() => _selectedSubjectId = subject.id),
                );
              },
            ),
            const SizedBox(height: 22),
            Text(
              '${selectedSubject.title} Topics',
              style: Theme.of(
                context,
              ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 12),
            ...topics.map(
              (topic) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _TopicCard(subject: selectedSubject, topic: topic),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SubjectCard extends StatelessWidget {
  const _SubjectCard({
    required this.subject,
    required this.isSelected,
    required this.onTap,
  });

  final TutorSubject subject;
  final bool isSelected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(22),
      child: Ink(
        decoration: BoxDecoration(
          color: isSelected
              ? subject.color
              : (isDark ? AppColors.surfaceDark : Colors.white),
          borderRadius: BorderRadius.circular(22),
          border: Border.all(
            color: isSelected
                ? subject.color
                : (isDark ? AppColors.borderDarkSoft : const Color(0xFFE2E8F0)),
          ),
          boxShadow: isSelected
              ? [
                  BoxShadow(
                    color: subject.color.withValues(alpha: 0.28),
                    blurRadius: 18,
                    offset: const Offset(0, 8),
                  ),
                ]
              : null,
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                subject.icon,
                color: isSelected
                    ? Colors.white
                    : (isDark
                          ? subject.color.withValues(alpha: 0.92)
                          : subject.color),
                size: 28,
              ),
              const SizedBox(height: 10),
              Text(
                subject.title,
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontWeight: FontWeight.w700,
                  fontSize: 13,
                  color: isSelected
                      ? Colors.white
                      : (isDark ? Colors.white : AppColors.textDark),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TopicCard extends StatelessWidget {
  const _TopicCard({required this.subject, required this.topic});

  final TutorSubject subject;
  final TutorTopic topic;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      decoration: BoxDecoration(
        color: isDark ? AppColors.surfaceDark : Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: isDark ? AppColors.borderDarkSoft : const Color(0xFFE2E8F0),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 22,
                  backgroundColor: subject.color.withValues(alpha: 0.12),
                  child: Icon(subject.icon, color: subject.color),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        topic.title,
                        style: Theme.of(context).textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        topic.subtitle,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: isDark
                              ? AppColors.textMuted
                              : AppColors.textSlateLight,
                        ),
                      ),
                    ],
                  ),
                ),
                Text(
                  '${(topic.progress * 100).round()}%',
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    color: subject.color,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: LinearProgressIndicator(
                value: topic.progress,
                minHeight: 8,
                backgroundColor: isDark
                    ? AppColors.surfaceDarkInput
                    : const Color(0xFFE8EEF8),
                valueColor: AlwaysStoppedAnimation<Color>(subject.color),
              ),
            ),
            const SizedBox(height: 14),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _ActionPill(
                  label: 'Ask Tutor',
                  color: subject.color,
                  icon: Icons.chat_bubble_outline_rounded,
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => AiTutorChatPage(
                          subjectTitle: subject.title,
                          topicTitle: topic.title,
                        ),
                      ),
                    );
                  },
                ),
                _ActionPill(
                  label: 'Guided Solve',
                  color: subject.color,
                  icon: Icons.draw_rounded,
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => GuidedProblemSolvingScreen(
                          subject: subject,
                          topic: topic,
                        ),
                      ),
                    );
                  },
                ),
                _ActionPill(
                  label: 'Quiz',
                  color: subject.color,
                  icon: Icons.quiz_rounded,
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) =>
                            AdaptiveQuizScreen(subject: subject, topic: topic),
                      ),
                    );
                  },
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ActionPill extends StatelessWidget {
  const _ActionPill({
    required this.label,
    required this.color,
    required this.icon,
    required this.onTap,
  });

  final String label;
  final Color color;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(999),
      child: Ink(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.10),
          borderRadius: BorderRadius.circular(999),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 16, color: color),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(color: color, fontWeight: FontWeight.w700),
            ),
          ],
        ),
      ),
    );
  }
}
