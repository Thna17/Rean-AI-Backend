import 'package:ai_tutor_app/features/notifications/domain/repositories/notification_repository.dart';

class ReviewReminderNotificationSyncService {
  static const notificationId = 'vocabulary_review_due_reminder';

  ReviewReminderNotificationSyncService({
    required NotificationRepository notificationRepository,
    DateTime Function()? now,
  });

  Future<void> sync() async {
    // No-op: Vocabulary feature removed
  }
}
