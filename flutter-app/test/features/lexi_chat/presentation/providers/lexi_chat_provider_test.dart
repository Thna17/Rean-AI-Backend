import 'package:flutter_test/flutter_test.dart';
import 'package:ai_tutor_app/core/di/core_di.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/domain/entities/ai_tutor_message.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/domain/entities/ai_tutor_stream_event.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/domain/entities/ai_tutor_messages_page.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/domain/entities/ai_tutor_session.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/domain/repositories/ai_tutor_chat_repository.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/presentation/providers/ai_tutor_chat_provider.dart';

class _FakeAiTutorChatRepository implements AiTutorChatRepository {
  int createSessionCalls = 0;
  int sendCalls = 0;
  int streamCalls = 0;
  String? lastIdempotencyKey;
  Stream<AiTutorStreamEvent> Function()? streamFactory;

  @override
  Future<AiTutorSession> createSession({required String userId}) async {
    createSessionCalls += 1;
    return AiTutorSession(
      sessionId: 's-1',
      userId: userId,
      createdAt: DateTime.parse('2026-05-30T00:00:00Z'),
      title: 'AI Tutor Chat',
    );
  }

  @override
  Future<void> deleteSession({required String sessionId}) async {}

  @override
  Future<List<AiTutorMessage>> getMessages({required String sessionId}) async {
    return const [];
  }

  @override
  Future<AiTutorMessagesPage> getMessagesPaged({
    required String sessionId,
    int limit = 50,
    String? cursor,
  }) async {
    return const AiTutorMessagesPage(
      messages: [],
      hasMore: false,
      nextCursor: null,
      returned: 0,
    );
  }

  @override
  Future<List<AiTutorSession>> getSessions({required String userId}) async {
    return const [];
  }

  @override
  Future<void> renameSession({
    required String sessionId,
    required String title,
  }) async {}

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
  }) async {
    sendCalls += 1;
    lastIdempotencyKey = idempotencyKey;
    return AiTutorMessage(
      id: 'assistant-$sendCalls',
      role: 'assistant',
      content: 'ok',
      timestamp: DateTime.parse('2026-05-30T00:00:01Z'),
    );
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
    streamCalls += 1;
    return streamFactory?.call() ??
        Stream<AiTutorStreamEvent>.fromIterable([
          const AiTutorStreamChunk('ok'),
          const AiTutorStreamDone(
            messageId: 'stream-assistant-1',
            sessionId: 's-1',
            corrections: [],
            linkedConcepts: [],
            metadata: {},
          ),
        ]);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('AiTutorChatProvider', () {
    test('builds web-safe request ids without crypto random', () async {
      final repo = _FakeAiTutorChatRepository();
      final provider = AiTutorChatProvider(
        repository: repo,
        aiClient: AiApiClient(),
      );
      addTearDown(provider.dispose);

      await provider.sendMessage('hello', userId: 'user@example.com');

      expect(repo.createSessionCalls, 1);
      expect(repo.sendCalls, 1);
      expect(
        repo.lastIdempotencyKey,
        matches(RegExp(r'^ai_tutor-user_example\.com-s-1-\d+-1$')),
      );
      expect(repo.lastIdempotencyKey, isNot(contains('@')));
      expect(provider.isSending, isFalse);
      expect(provider.messages.where((m) => m.role == 'user').length, 1);
      expect(provider.messages.last.content, 'ok');
    });

    test('falls back to non-streaming send when SSE closes empty', () async {
      final repo = _FakeAiTutorChatRepository()
        ..streamFactory = () => const Stream<AiTutorStreamEvent>.empty();
      final provider = AiTutorChatProvider(
        repository: repo,
        aiClient: AiApiClient(),
      );
      addTearDown(provider.dispose);

      await provider.sendMessageStreaming('hello', userId: 'user-1');

      expect(repo.streamCalls, 1);
      expect(repo.sendCalls, 1);
      expect(provider.isSending, isFalse);
      expect(provider.isAiTutorResponding, isFalse);
      expect(provider.messages.any((m) => m.syncStatus == 'streaming'), false);
      expect(provider.messages.where((m) => m.role == 'user').length, 1);
      expect(provider.messages.last.content, 'ok');
    });

    test('keeps streamed text when SSE has chunks but no done event', () async {
      final repo = _FakeAiTutorChatRepository()
        ..streamFactory = () => Stream<AiTutorStreamEvent>.fromIterable([
          const AiTutorStreamThinking(),
          const AiTutorStreamChunk('Hi'),
          const AiTutorStreamChunk(' there'),
        ]);
      final provider = AiTutorChatProvider(
        repository: repo,
        aiClient: AiApiClient(),
      );
      addTearDown(provider.dispose);

      await provider.sendMessageStreaming('hello', userId: 'user-1');

      expect(repo.streamCalls, 1);
      expect(repo.sendCalls, 0);
      expect(provider.isSending, isFalse);
      expect(provider.isAiTutorResponding, isFalse);
      expect(provider.messages.any((m) => m.syncStatus == 'streaming'), false);
      expect(provider.messages.last.role, 'assistant');
      expect(provider.messages.last.content, 'Hi there');
      expect(provider.messages.last.syncStatus, 'synced');
    });
  });
}
