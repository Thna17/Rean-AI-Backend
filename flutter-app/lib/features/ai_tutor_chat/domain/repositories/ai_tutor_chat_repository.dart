import 'package:ai_tutor_app/features/ai_tutor_chat/domain/entities/ai_tutor_message.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/domain/entities/ai_tutor_messages_page.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/domain/entities/ai_tutor_session.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/domain/entities/ai_tutor_stream_event.dart';

/// Abstract repository for AI Tutor chat operations.
abstract class AiTutorChatRepository {
  /// Create a new session with AI Tutor.
  Future<AiTutorSession> createSession({required String userId});

  /// Send a message to AI Tutor and get a response.
  Future<AiTutorMessage> sendMessage({
    required String userId,
    required String sessionId,
    required String message,
    String inputType = 'text',
    String? audioBase64,
    bool enableTts = true,
    String learnerLevel = 'B1',
    String? storyContext,
    String? subject,
    String? topic,
    String? idempotencyKey,
  });

  /// Get message history for a session.
  Future<List<AiTutorMessage>> getMessages({required String sessionId});

  /// Get paged message history for a session.
  Future<AiTutorMessagesPage> getMessagesPaged({
    required String sessionId,
    int limit = 50,
    String? cursor,
  });

  /// Get all sessions for a user.
  Future<List<AiTutorSession>> getSessions({required String userId});

  /// Rename a session title.
  Future<void> renameSession({
    required String sessionId,
    required String title,
  });

  /// Delete a session and its messages.
  Future<void> deleteSession({required String sessionId});

  /// Send a message to AI Tutor and receive an SSE stream of typed events.
  Stream<AiTutorStreamEvent> sendMessageStream({
    required String userId,
    required String sessionId,
    required String message,
    String inputType = 'text',
    String? audioBase64,
    bool enableTts = true,
    String learnerLevel = 'B1',
    String? storyContext,
    String? subject,
    String? topic,
  });
}
