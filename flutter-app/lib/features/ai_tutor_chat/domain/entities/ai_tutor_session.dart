/// Domain entity for a AI Tutor chat session.
class AiTutorSession {
  final String sessionId;
  final String userId;
  final DateTime createdAt;
  final String? storyContext;
  final String? title;
  final DateTime? updatedAt;
  final int? messageCount;

  const AiTutorSession({
    required this.sessionId,
    required this.userId,
    required this.createdAt,
    this.storyContext,
    this.title,
    this.updatedAt,
    this.messageCount,
  });
}
