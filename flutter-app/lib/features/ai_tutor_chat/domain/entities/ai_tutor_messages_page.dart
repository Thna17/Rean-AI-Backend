import 'ai_tutor_message.dart';

/// Cursor-based page of AI Tutor chat messages.
class AiTutorMessagesPage {
  final List<AiTutorMessage> messages;
  final bool hasMore;
  final String? nextCursor;
  final int returned;

  const AiTutorMessagesPage({
    required this.messages,
    required this.hasMore,
    required this.nextCursor,
    required this.returned,
  });
}
