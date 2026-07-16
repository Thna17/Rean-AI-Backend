import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:ai_tutor_app/core/theme/app_theme.dart';
import 'package:ai_tutor_app/features/learning/presentation/providers/tutor_catalog_provider.dart';
import 'package:ai_tutor_app/features/progress/presentation/providers/progress_provider.dart';

class MyProgressScreen extends StatefulWidget {
  const MyProgressScreen({super.key});

  @override
  State<MyProgressScreen> createState() => _MyProgressScreenState();
}

class _MyProgressScreenState extends State<MyProgressScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ProgressProvider>().fetchMyProgress();
      context.read<TutorCatalogProvider>().loadDashboard();
    });
  }

  Future<void> _refresh() async {
    await Future.wait([
      context.read<ProgressProvider>().fetchMyProgress(),
      context.read<TutorCatalogProvider>().loadDashboard(),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Scaffold(
      backgroundColor: isDark
          ? AppColors.backgroundDark
          : const Color(0xFFF5F8FE),
      appBar: AppBar(title: const Text('Progress')),
      body: Consumer2<ProgressProvider, TutorCatalogProvider>(
        builder: (context, provider, tutorProvider, _) {
          final summary = provider.summary;
          final dashboard = tutorProvider.dashboard;
          final completion = dashboard == null
              ? 0.0
              : (dashboard.completionPercentage / 100)
                    .clamp(0.0, 1.0)
                    .toDouble();
          final trendItems = dashboard?.scoreTrend.isNotEmpty == true
              ? dashboard!.scoreTrend
              : const <Map<String, dynamic>>[];
          final weakTopicItems =
              dashboard?.weakTopics
                  .map(
                    (item) => _PanelItem(
                      label: item['title']?.toString() ?? 'Topic',
                      meta: item['progress'] is num
                          ? '${(((item['progress'] as num).toDouble()) * 100).round()}%'
                          : '${item['error_count'] ?? 0} errors',
                    ),
                  )
                  .toList(growable: false) ??
              const <_PanelItem>[];
          final mistakeItems =
              dashboard?.recentMistakes
                  .map(
                    (item) => _PanelItem(
                      label: item['title']?.toString() ?? 'Recent mistake',
                      meta: item['subject']?.toString() ?? '',
                    ),
                  )
                  .toList(growable: false) ??
              const <_PanelItem>[];

          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
              children: [
                _CompletionCard(progress: completion),
                const SizedBox(height: 16),
                _Panel(
                  title: 'Score Trend',
                  child: Column(
                    children: trendItems.isEmpty
                        ? const [
                            _EmptyPanelText(
                              text:
                                  'Complete a quiz to build your score trend.',
                            ),
                          ]
                        : trendItems
                              .map(
                                (item) => _TrendRow(
                                  label: item['label']?.toString() ?? 'Recent',
                                  value: ((item['value'] as num?) ?? 0)
                                      .toDouble(),
                                ),
                              )
                              .toList(growable: false),
                  ),
                ),
                const SizedBox(height: 16),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: _ListPanel(
                        title: 'Weak Topics',
                        items: weakTopicItems,
                        emptyText: 'No weak topics yet.',
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _ListPanel(
                        title: 'Recent Mistakes',
                        items: mistakeItems,
                        emptyText: 'Mistakes from quizzes will appear here.',
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                _RecommendationCard(
                  topic:
                      dashboard?.recommendationTopic ??
                      'Start Linear Equations',
                  totalXp: summary?.totalXp ?? 0,
                  currentStreak: summary?.currentStreak ?? 0,
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _CompletionCard extends StatelessWidget {
  const _CompletionCard({required this.progress});

  final double progress;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final percent = (progress * 100).round();

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: isDark ? AppColors.surfaceDark : Colors.white,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: isDark ? AppColors.borderDarkSoft : const Color(0xFFE2E8F0),
        ),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 92,
            height: 92,
            child: Stack(
              alignment: Alignment.center,
              children: [
                CircularProgressIndicator(
                  value: progress,
                  strokeWidth: 10,
                  backgroundColor: isDark
                      ? AppColors.surfaceDarkInput
                      : const Color(0xFFE2E8F0),
                  valueColor: const AlwaysStoppedAnimation<Color>(
                    Color(0xFF14B8A6),
                  ),
                ),
                Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      '$percent%',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const Text('Completed', style: TextStyle(fontSize: 12)),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Great job!',
                  style: Theme.of(
                    context,
                  ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 6),
                Text(
                  'You\'re ahead of 78% of students and building consistent mastery.',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: isDark
                        ? AppColors.textMuted
                        : AppColors.textSlateLight,
                    height: 1.45,
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

class _Panel extends StatelessWidget {
  const _Panel({required this.title, required this.child});

  final String title;
  final Widget child;

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
            title,
            style: Theme.of(
              context,
            ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 14),
          child,
        ],
      ),
    );
  }
}

class _TrendRow extends StatelessWidget {
  const _TrendRow({required this.label, required this.value});

  final String label;
  final double value;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          SizedBox(
            width: 52,
            child: Text(
              label,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: isDark ? AppColors.textMuted : AppColors.textSlateLight,
              ),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: LinearProgressIndicator(
                value: value,
                minHeight: 10,
                backgroundColor: isDark
                    ? AppColors.surfaceDarkInput
                    : const Color(0xFFE2E8F0),
                valueColor: const AlwaysStoppedAnimation<Color>(
                  Color(0xFF2563EB),
                ),
              ),
            ),
          ),
          const SizedBox(width: 10),
          Text(
            '${(value * 100).round()}%',
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
        ],
      ),
    );
  }
}

class _ListPanel extends StatelessWidget {
  const _ListPanel({
    required this.title,
    required this.items,
    required this.emptyText,
  });

  final String title;
  final List<_PanelItem> items;
  final String emptyText;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      title: title,
      child: items.isEmpty
          ? _EmptyPanelText(text: emptyText)
          : Column(
              children: items
                  .map(
                    (item) => Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Row(
                        children: [
                          const Icon(
                            Icons.circle,
                            size: 8,
                            color: Color(0xFF0EA5E9),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              item.label,
                              style: Theme.of(context).textTheme.bodyMedium
                                  ?.copyWith(fontWeight: FontWeight.w600),
                            ),
                          ),
                          Text(
                            item.meta,
                            style: Theme.of(context).textTheme.bodySmall
                                ?.copyWith(color: AppColors.textSlateLight),
                          ),
                        ],
                      ),
                    ),
                  )
                  .toList(growable: false),
            ),
    );
  }
}

class _EmptyPanelText extends StatelessWidget {
  const _EmptyPanelText({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
        color: AppColors.textSlateLight,
        height: 1.4,
      ),
    );
  }
}

class _PanelItem {
  const _PanelItem({required this.label, required this.meta});

  final String label;
  final String meta;
}

class _RecommendationCard extends StatelessWidget {
  const _RecommendationCard({
    required this.topic,
    required this.totalXp,
    required this.currentStreak,
  });

  final String topic;
  final int totalXp;
  final int currentStreak;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFFDFF7FF), Color(0xFFECFEFF)],
        ),
        borderRadius: BorderRadius.circular(24),
      ),
      child: Row(
        children: [
          const CircleAvatar(
            radius: 24,
            backgroundColor: Colors.white,
            child: Icon(Icons.menu_book_rounded, color: Color(0xFF0891B2)),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Recommended for you',
                  style: TextStyle(
                    color: AppColors.textSlateLight,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Review $topic',
                  style: const TextStyle(
                    color: AppColors.textDark,
                    fontWeight: FontWeight.w800,
                    fontSize: 18,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'XP $totalXp • $currentStreak day streak • 15 min review',
                  style: const TextStyle(
                    color: AppColors.textSlateLight,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
          const Icon(Icons.arrow_forward_ios_rounded, size: 18),
        ],
      ),
    );
  }
}
