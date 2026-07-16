import 'package:ai_tutor_app/core/di/service_locator.dart';
import 'package:ai_tutor_app/features/achievements/domain/usecases/get_recent_badges_usecase.dart';
import 'package:ai_tutor_app/features/profile/presentation/providers/profile_provider.dart';
import 'package:ai_tutor_app/features/user/domain/usecases/get_user_stats_usecase.dart';
import 'package:ai_tutor_app/features/user/domain/usecases/get_weekly_activity_usecase.dart';

void registerProfileModule() {
  // Register ProfileProvider with Recent Badges support
  // Following agent-skills/gamification-achievement-badges pattern
  sl.registerFactory<ProfileProvider>(
    () => ProfileProvider(
      getUserStatsUseCase: sl<GetUserStatsUseCase>(),
      getWeeklyActivityUseCase: sl<GetWeeklyActivityUseCase>(),
      getRecentBadgesUseCase: sl<GetRecentBadgesUseCase>(),
    ),
  );
}
