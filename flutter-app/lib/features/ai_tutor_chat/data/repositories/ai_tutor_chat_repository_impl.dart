import 'package:ai_tutor_app/features/ai_tutor_chat/data/datasources/ai_tutor_chat_data_source.dart';
import 'package:ai_tutor_app/core/utils/app_logger.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/domain/entities/ai_tutor_message.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/domain/entities/ai_tutor_messages_page.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/domain/entities/ai_tutor_session.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/domain/entities/ai_tutor_stream_event.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/domain/repositories/ai_tutor_chat_repository.dart';

const _tag = 'AiTutorChatRepositoryImpl';

/// Repository implementation for AI Tutor Chat.
class AiTutorChatRepositoryImpl implements AiTutorChatRepository {
  final AiTutorChatDataSource dataSource;

  AiTutorChatRepositoryImpl({required this.dataSource});

  @override
  Future<AiTutorSession> createSession({required String userId}) {
    return dataSource.createSession(userId: userId);
  }

  @override
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
  }) {
    return dataSource.sendMessage(
      userId: userId,
      sessionId: sessionId,
      message: message,
      inputType: inputType,
      audioBase64: audioBase64,
      enableTts: enableTts,
      learnerLevel: learnerLevel,
      storyContext: storyContext,
      subject: subject,
      topic: topic,
      idempotencyKey: idempotencyKey,
    );
  }

  @override
  Future<List<AiTutorMessage>> getMessages({required String sessionId}) {
    return dataSource.getMessages(sessionId: sessionId);
  }

  @override
  Future<AiTutorMessagesPage> getMessagesPaged({
    required String sessionId,
    int limit = 50,
    String? cursor,
  }) {
    if (cursor == null || cursor.isEmpty) {
      return _getPagedWithMetadata(
        sessionId: sessionId,
        limit: limit,
        cursor: cursor,
      );
    }

    return dataSource.getMessagesPaged(
      sessionId: sessionId,
      limit: limit,
      cursor: cursor,
    );
  }

  Future<AiTutorMessagesPage> _getPagedWithMetadata({
    required String sessionId,
    required int limit,
    String? cursor,
  }) async {
    try {
      final metadata = await dataSource.getMessagesMetadata(
        sessionId: sessionId,
      );
      if (!metadata.hasMessages || metadata.totalCount == 0) {
        return const AiTutorMessagesPage(
          messages: [],
          hasMore: false,
          nextCursor: null,
          returned: 0,
        );
      }
    } catch (e) {
      if (_isSessionNotFoundError(e)) {
        // Let provider handle stale session cleanup and auto-create a new session.
        rethrow;
      }
      // Metadata endpoint is an optimization layer only.
      logWarn(_tag, 'getMessagesMetadata failed, continue paged fetch: $e');
    }

    return dataSource.getMessagesPaged(
      sessionId: sessionId,
      limit: limit,
      cursor: cursor,
    );
  }

  bool _isSessionNotFoundError(Object error) {
    final msg = error.toString().toLowerCase();
    return msg.contains('status 404') ||
        msg.contains('404') ||
        msg.contains('not found');
  }

  @override
  Future<List<AiTutorSession>> getSessions({required String userId}) {
    return dataSource.getSessions(userId: userId);
  }

  @override
  Future<void> renameSession({
    required String sessionId,
    required String title,
  }) {
    return dataSource.renameSession(sessionId: sessionId, title: title);
  }

  @override
  Future<void> deleteSession({required String sessionId}) {
    return dataSource.deleteSession(sessionId: sessionId);
  }

  @override
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
  }) {
    return dataSource.sendMessageStream(
      userId: userId,
      sessionId: sessionId,
      message: message,
      inputType: inputType,
      audioBase64: audioBase64,
      enableTts: enableTts,
      learnerLevel: learnerLevel,
      storyContext: storyContext,
      subject: subject,
      topic: topic,
    );
  }
}
