import 'package:ai_tutor_app/core/di/core_di.dart';
import 'package:ai_tutor_app/core/di/service_locator.dart';
import 'package:ai_tutor_app/features/achievements/di/achievement_di.dart';
import 'package:ai_tutor_app/features/auth/di/auth_di.dart';
import 'package:ai_tutor_app/features/chat/di/chat_di.dart';
import 'package:ai_tutor_app/features/course/di/course_di.dart';
import 'package:ai_tutor_app/features/home/di/home_di.dart';
import 'package:ai_tutor_app/features/learning/di/learning_di.dart';
import 'package:ai_tutor_app/features/level/di/level_di.dart';
import 'package:ai_tutor_app/features/notifications/di/notification_di.dart';
import 'package:ai_tutor_app/features/profile/di/profile_di.dart';
import 'package:ai_tutor_app/features/progress/di/progress_di.dart';
import 'package:ai_tutor_app/features/social/di/social_di.dart';
import 'package:ai_tutor_app/features/user/di/user_di.dart';
import 'package:ai_tutor_app/features/voice/di/voice_di.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/di/ai_tutor_chat_di.dart';

export 'service_locator.dart';

/// Orchestrates dependency registration across core and feature modules.
Future<void> initializeDependencies({bool skipDatabase = false}) async {
  await registerCore(skipDatabase: skipDatabase);

  registerAuthModule();
  registerChatModule(skipDatabase: skipDatabase);
  registerCourseModule(skipDatabase: skipDatabase);
  registerLearningModule();
  registerProgressModule();
  registerUserModule(skipDatabase: skipDatabase);
  registerHomeModule();
  registerProfileModule(); // Profile stats system
  registerAchievementModule(); // Achievement/Badge system
  registerNotificationModule(); // Notification system
  registerLevelModule(); // Level/XP system
  registerSocialModule(); // Friends, Activity Feed
  initVoiceDependencies(sl);
  // Phase 6: AI Tutor Chat — Story Adventure
  registerAiTutorChatModule(); // Phase 6: AI Tutor Chat — Story Adventure
}
