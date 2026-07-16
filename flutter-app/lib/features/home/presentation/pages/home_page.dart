import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:ai_tutor_app/core/theme/app_theme.dart';
import 'package:ai_tutor_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ai_tutor_app/features/home/presentation/providers/home_provider.dart';
import 'package:ai_tutor_app/features/learning/presentation/models/tutor_catalog.dart';
import 'package:ai_tutor_app/features/learning/presentation/providers/tutor_catalog_provider.dart';
import 'package:ai_tutor_app/features/learning/presentation/screens/adaptive_quiz_screen.dart';
import 'package:ai_tutor_app/features/learning/presentation/screens/guided_problem_solving_screen.dart';
import 'package:ai_tutor_app/features/learning/presentation/screens/subject_selection_screen.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/presentation/pages/ai_tutor_chat_page.dart';
import 'package:ai_tutor_app/features/progress/presentation/providers/streak_provider.dart';

class HomePageNew extends StatefulWidget {
  const HomePageNew({super.key});

  @override
  State<HomePageNew> createState() => _HomePageNewState();
}

class _HomePageNewState extends State<HomePageNew> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<HomeProvider>().loadHomeData();
      context.read<StreakProvider>().loadStreak();
      context.read<TutorCatalogProvider>()
        ..loadSubjects()
        ..loadDashboard();
    });
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: isDark
          ? AppColors.backgroundDark
          : const Color(0xFFF5F8FE),
      body: SafeArea(
        child:
            Consumer4<
              HomeProvider,
              AuthProvider,
              StreakProvider,
              TutorCatalogProvider
            >(
              builder:
                  (
                    context,
                    homeProvider,
                    authProvider,
                    streakProvider,
                    tutorProvider,
                    _,
                  ) {
                    final user = authProvider.currentUser;
                    final dashboard = tutorProvider.dashboard;
                    final subjects = tutorProvider.subjects;
                    final math = subjects.isNotEmpty
                        ? subjects.first
                        : TutorCatalog.byId('math');
                    final featuredTopic = math.topics.first;
                    final name =
                        dashboard?.studentName ??
                        (user?.displayName.isNotEmpty == true
                            ? user!.displayName
                            : (user?.username ?? 'Student'));
                    final streak =
                        dashboard?.streakDays ??
                        streakProvider.streak?.currentStreak ??
                        homeProvider.streakDays;

                    return RefreshIndicator(
                      onRefresh: () async {
                        await homeProvider.refreshData();
                        await streakProvider.loadStreak();
                        await tutorProvider.loadDashboard();
                        await tutorProvider.loadSubjects();
                      },
                      child: ListView(
                        padding: const EdgeInsets.fromLTRB(16, 10, 16, 28),
                        children: [
                          _DashboardHero(name: name, streak: streak),
                          const SizedBox(height: 16),
                          _ContinueLearningCard(
                            subject: math,
                            topic: featuredTopic,
                            progressOverride: dashboard?.continueProgress,
                            subjectTitleOverride: dashboard?.continueSubject,
                            topicTitleOverride: dashboard?.continueTopic,
                          ),
                          const SizedBox(height: 14),
                          Row(
                            children: [
                              Expanded(
                                child: _MetricCard(
                                  title: 'Today\'s Goal',
                                  value:
                                      '${dashboard?.todayCompleted ?? 2} / ${dashboard?.todayTarget ?? 3}',
                                  subtitle: 'Lessons completed',
                                  icon: Icons.local_fire_department_rounded,
                                  color: const Color(0xFFF97316),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: _MetricCard(
                                  title: 'Weak Topics',
                                  value: '${dashboard?.weakTopics.length ?? 3}',
                                  subtitle: 'Topics to review',
                                  icon: Icons.trending_down_rounded,
                                  color: const Color(0xFFEF4444),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 18),
                          if ((dashboard?.weakTopics.isNotEmpty ?? false)) ...[
                            Text(
                              'Focus Next',
                              style: Theme.of(context).textTheme.titleLarge
                                  ?.copyWith(fontWeight: FontWeight.w700),
                            ),
                            const SizedBox(height: 12),
                            ...dashboard!.weakTopics
                                .take(3)
                                .map(
                                  (item) => Padding(
                                    padding: const EdgeInsets.only(bottom: 10),
                                    child: _WeakTopicRow(
                                      subject:
                                          item['subject']?.toString() ??
                                          'General',
                                      title:
                                          item['title']?.toString() ??
                                          'General',
                                      count:
                                          (item['error_count'] as num?)
                                              ?.toInt() ??
                                          0,
                                    ),
                                  ),
                                ),
                            const SizedBox(height: 18),
                          ],
                          Text(
                            'Quick Actions',
                            style: Theme.of(context).textTheme.titleLarge
                                ?.copyWith(fontWeight: FontWeight.w700),
                          ),
                          const SizedBox(height: 12),
                          GridView.count(
                            shrinkWrap: true,
                            physics: const NeverScrollableScrollPhysics(),
                            crossAxisCount: 3,
                            crossAxisSpacing: 12,
                            mainAxisSpacing: 12,
                            childAspectRatio: 1.05,
                            children: [
                              _QuickActionTile(
                                label: 'Math',
                                icon: Icons.calculate_rounded,
                                color: const Color(0xFF2563EB),
                                onTap: () => Navigator.of(context).push(
                                  MaterialPageRoute(
                                    builder: (_) =>
                                        const SubjectSelectionScreen(),
                                  ),
                                ),
                              ),
                              _QuickActionTile(
                                label: 'Physics',
                                icon: Icons.science_rounded,
                                color: const Color(0xFF0F766E),
                                onTap: () => Navigator.of(context).push(
                                  MaterialPageRoute(
                                    builder: (_) =>
                                        const SubjectSelectionScreen(),
                                  ),
                                ),
                              ),
                              _QuickActionTile(
                                label: 'English',
                                icon: Icons.menu_book_rounded,
                                color: const Color(0xFF0891B2),
                                onTap: () => Navigator.of(context).push(
                                  MaterialPageRoute(
                                    builder: (_) =>
                                        const SubjectSelectionScreen(),
                                  ),
                                ),
                              ),
                              _QuickActionTile(
                                label: 'Quiz',
                                icon: Icons.quiz_rounded,
                                color: const Color(0xFF7C3AED),
                                onTap: () => Navigator.of(context).push(
                                  MaterialPageRoute(
                                    builder: (_) => AdaptiveQuizScreen(
                                      subject: math,
                                      topic: featuredTopic,
                                    ),
                                  ),
                                ),
                              ),
                              _QuickActionTile(
                                label: 'Ask Tutor',
                                icon: Icons.chat_bubble_outline_rounded,
                                color: const Color(0xFF0EA5E9),
                                onTap: () => Navigator.of(context).push(
                                  MaterialPageRoute(
                                    builder: (_) => const AiTutorChatPage(
                                      subjectTitle: 'Mathematics',
                                      topicTitle: 'Linear Equations',
                                    ),
                                  ),
                                ),
                              ),
                              _QuickActionTile(
                                label: 'Guided Solve',
                                icon: Icons.draw_rounded,
                                color: const Color(0xFF14B8A6),
                                onTap: () => Navigator.of(context).push(
                                  MaterialPageRoute(
                                    builder: (_) => GuidedProblemSolvingScreen(
                                      subject: math,
                                      topic: featuredTopic,
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    );
                  },
            ),
      ),
    );
  }
}

class _DashboardHero extends StatelessWidget {
  const _DashboardHero({required this.name, required this.streak});

  final String name;
  final int streak;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF2563EB), Color(0xFF1D4ED8)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(28),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Spacer(),
              Icon(Icons.notifications_none_rounded, color: Colors.white),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'Good morning,',
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
              color: Colors.white.withValues(alpha: 0.90),
            ),
          ),
          const SizedBox(height: 4),
          Text(
            '$name! 👋',
            style: Theme.of(context).textTheme.headlineMedium?.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 18),
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(22),
            ),
            child: Row(
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '$streak',
                      style: const TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.w800,
                        color: AppColors.textDark,
                      ),
                    ),
                    const Text(
                      'day streak',
                      style: TextStyle(
                        color: AppColors.textSlateLight,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
                const Spacer(),
                ...List.generate(
                  7,
                  (index) => Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 3),
                    child: CircleAvatar(
                      radius: 10,
                      backgroundColor: index < 6
                          ? const Color(0xFF2563EB)
                          : const Color(0xFFE2E8F0),
                      child: index < 6
                          ? const Icon(
                              Icons.check,
                              size: 12,
                              color: Colors.white,
                            )
                          : null,
                    ),
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

class _ContinueLearningCard extends StatelessWidget {
  const _ContinueLearningCard({
    required this.subject,
    required this.topic,
    this.progressOverride,
    this.subjectTitleOverride,
    this.topicTitleOverride,
  });

  final TutorSubject subject;
  final TutorTopic topic;
  final double? progressOverride;
  final String? subjectTitleOverride;
  final String? topicTitleOverride;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: isDark ? AppColors.surfaceDark : Colors.white,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: isDark ? AppColors.borderDarkSoft : const Color(0xFFE2E8F0),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Continue Learning',
            style: Theme.of(
              context,
            ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              CircleAvatar(
                radius: 24,
                backgroundColor: subject.color.withValues(alpha: 0.12),
                child: Icon(subject.icon, color: subject.color),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      topicTitleOverride ?? topic.title,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subjectTitleOverride ?? subject.title,
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
                '${((progressOverride ?? topic.progress) * 100).round()}%',
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
              value: progressOverride ?? topic.progress,
              minHeight: 8,
              backgroundColor: isDark
                  ? AppColors.surfaceDarkInput
                  : const Color(0xFFE2E8F0),
              valueColor: AlwaysStoppedAnimation<Color>(subject.color),
            ),
          ),
        ],
      ),
    );
  }
}

class _WeakTopicRow extends StatelessWidget {
  const _WeakTopicRow({
    required this.subject,
    required this.title,
    required this.count,
  });

  final String subject;
  final String title;
  final int count;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isDark ? AppColors.surfaceDark : Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: isDark ? AppColors.borderDarkSoft : const Color(0xFFE2E8F0),
        ),
      ),
      child: Row(
        children: [
          const CircleAvatar(
            radius: 16,
            backgroundColor: Color(0xFFDBEAFE),
            child: Icon(
              Icons.priority_high_rounded,
              size: 18,
              color: Color(0xFF2563EB),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                Text(
                  subject,
                  style: TextStyle(
                    color: isDark
                        ? AppColors.textMuted
                        : AppColors.textSlateLight,
                  ),
                ),
              ],
            ),
          ),
          Text(
            '$count errors',
            style: const TextStyle(
              color: Color(0xFFEF4444),
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.title,
    required this.value,
    required this.subtitle,
    required this.icon,
    required this.color,
  });

  final String title;
  final String value;
  final String subtitle;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? AppColors.surfaceDark : Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(
          color: isDark ? AppColors.borderDarkSoft : const Color(0xFFE2E8F0),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color),
          const SizedBox(height: 10),
          Text(
            title,
            style: Theme.of(
              context,
            ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          Text(
            value,
            style: Theme.of(
              context,
            ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 4),
          Text(
            subtitle,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: isDark ? AppColors.textMuted : AppColors.textSlateLight,
            ),
          ),
        ],
      ),
    );
  }
}

class _QuickActionTile extends StatelessWidget {
  const _QuickActionTile({
    required this.label,
    required this.icon,
    required this.color,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(22),
      child: Ink(
        decoration: BoxDecoration(
          color: isDark ? AppColors.surfaceDark : Colors.white,
          borderRadius: BorderRadius.circular(22),
          border: Border.all(
            color: isDark ? AppColors.borderDarkSoft : const Color(0xFFE2E8F0),
          ),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircleAvatar(
              radius: 22,
              backgroundColor: color.withValues(alpha: 0.12),
              child: Icon(icon, color: color),
            ),
            const SizedBox(height: 10),
            Text(label, style: const TextStyle(fontWeight: FontWeight.w700)),
          ],
        ),
      ),
    );
  }
}
