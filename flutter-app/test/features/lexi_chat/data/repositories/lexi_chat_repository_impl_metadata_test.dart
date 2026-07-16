import 'package:flutter_test/flutter_test.dart';
import 'package:ai_tutor_app/core/network/api_client.dart';
import 'package:ai_tutor_app/core/network/network_info.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/data/datasources/ai_tutor_chat_data_source.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/data/repositories/ai_tutor_chat_repository_impl.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/domain/entities/ai_tutor_message.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/domain/entities/ai_tutor_messages_page.dart';

class _AlwaysConnectedNetworkInfo implements NetworkInfo {
  @override
  Future<bool> get isConnected async => true;
}

class _StubAiTutorChatDataSource extends AiTutorChatDataSource {
  _StubAiTutorChatDataSource()
    : super(
        apiClient: ApiClient(
          baseUrl: 'http://localhost:8000',
          enableLogging: false,
          networkInfo: _AlwaysConnectedNetworkInfo(),
        ),
      );

  int metadataCalls = 0;
  int pagedCalls = 0;
  String? lastMetadataSessionId;
  String? lastPagedSessionId;
  int? lastPagedLimit;
  String? lastPagedCursor;

  Object? metadataError;
  Object? pagedError;

  AiTutorMessagesMetadata metadataResult = const AiTutorMessagesMetadata(
    totalCount: 0,
    hasMessages: false,
    latestCursor: null,
    oldestCursor: null,
    latestTs: null,
    oldestTs: null,
  );

  AiTutorMessagesPage pagedResult = const AiTutorMessagesPage(
    messages: [],
    hasMore: false,
    nextCursor: null,
    returned: 0,
  );

  @override
  Future<AiTutorMessagesMetadata> getMessagesMetadata({
    required String sessionId,
  }) async {
    metadataCalls += 1;
    lastMetadataSessionId = sessionId;
    if (metadataError != null) {
      throw metadataError!;
    }
    return metadataResult;
  }

  @override
  Future<AiTutorMessagesPage> getMessagesPaged({
    required String sessionId,
    int limit = 50,
    String? cursor,
  }) async {
    pagedCalls += 1;
    lastPagedSessionId = sessionId;
    lastPagedLimit = limit;
    lastPagedCursor = cursor;
    if (pagedError != null) {
      throw pagedError!;
    }
    return pagedResult;
  }
}

void main() {
  late _StubAiTutorChatDataSource dataSource;
  late AiTutorChatRepositoryImpl repository;

  setUp(() {
    dataSource = _StubAiTutorChatDataSource();
    repository = AiTutorChatRepositoryImpl(dataSource: dataSource);
  });

  group('getMessagesPaged metadata-first', () {
    test(
      'returns empty page when metadata says session has no messages',
      () async {
        dataSource.metadataResult = const AiTutorMessagesMetadata(
          totalCount: 0,
          hasMessages: false,
          latestCursor: null,
          oldestCursor: null,
          latestTs: null,
          oldestTs: null,
        );

        final result = await repository.getMessagesPaged(
          sessionId: 'session_1',
        );

        expect(result.messages, isEmpty);
        expect(result.hasMore, false);
        expect(result.nextCursor, isNull);
        expect(result.returned, 0);
        expect(dataSource.metadataCalls, 1);
        expect(dataSource.lastMetadataSessionId, 'session_1');
        expect(dataSource.pagedCalls, 0);
      },
    );

    test(
      'calls paged endpoint when metadata indicates messages exist',
      () async {
        dataSource.metadataResult = const AiTutorMessagesMetadata(
          totalCount: 8,
          hasMessages: true,
          latestCursor: 'latest',
          oldestCursor: 'oldest',
          latestTs: '2026-04-16T00:00:10Z',
          oldestTs: '2026-04-16T00:00:00Z',
        );
        dataSource.pagedResult = AiTutorMessagesPage(
          messages: [
            AiTutorMessage(
              id: 'm1',
              role: 'assistant',
              content: 'Hi learner',
              timestamp: DateTime.parse('2026-04-16T00:00:00Z'),
            ),
          ],
          hasMore: true,
          nextCursor: 'next-cursor',
          returned: 1,
        );

        final result = await repository.getMessagesPaged(
          sessionId: 'session_1',
        );

        expect(result.messages.length, 1);
        expect(result.messages.first.id, 'm1');
        expect(result.hasMore, true);
        expect(result.nextCursor, 'next-cursor');
        expect(result.returned, 1);
        expect(dataSource.metadataCalls, 1);
        expect(dataSource.pagedCalls, 1);
        expect(dataSource.lastPagedSessionId, 'session_1');
        expect(dataSource.lastPagedLimit, 50);
        expect(dataSource.lastPagedCursor, isNull);
      },
    );

    test('still calls paged endpoint when metadata request throws', () async {
      dataSource.metadataError = Exception('metadata unavailable');
      dataSource.pagedResult = AiTutorMessagesPage(
        messages: [
          AiTutorMessage(
            id: 'm2',
            role: 'user',
            content: 'Hello',
            timestamp: DateTime.parse('2026-04-16T00:01:00Z'),
          ),
        ],
        hasMore: false,
        nextCursor: null,
        returned: 1,
      );

      final result = await repository.getMessagesPaged(sessionId: 'session_1');

      expect(result.messages.length, 1);
      expect(result.messages.first.id, 'm2');
      expect(result.returned, 1);
      expect(dataSource.metadataCalls, 1);
      expect(dataSource.pagedCalls, 1);
      expect(dataSource.lastPagedSessionId, 'session_1');
    });

    test('skips metadata check when cursor is provided', () async {
      dataSource.pagedResult = const AiTutorMessagesPage(
        messages: [],
        hasMore: false,
        nextCursor: null,
        returned: 0,
      );

      final result = await repository.getMessagesPaged(
        sessionId: 'session_1',
        limit: 20,
        cursor: 'cursor-1',
      );

      expect(result.messages, isEmpty);
      expect(result.returned, 0);
      expect(dataSource.metadataCalls, 0);
      expect(dataSource.pagedCalls, 1);
      expect(dataSource.lastPagedSessionId, 'session_1');
      expect(dataSource.lastPagedLimit, 20);
      expect(dataSource.lastPagedCursor, 'cursor-1');
    });
  });
}
