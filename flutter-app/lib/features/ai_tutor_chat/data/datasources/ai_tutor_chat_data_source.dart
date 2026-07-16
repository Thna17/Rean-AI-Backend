import 'dart:async';
import 'dart:convert';
import 'package:ai_tutor_app/core/network/api_client.dart';
import 'package:ai_tutor_app/core/utils/app_logger.dart';
import 'package:ai_tutor_app/core/utils/constants.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/domain/entities/ai_tutor_message.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/domain/entities/ai_tutor_messages_page.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/domain/entities/ai_tutor_session.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/domain/entities/ai_tutor_stream_event.dart';

const _tag = 'AiTutorChatDataSource';

class AiTutorMessagesMetadata {
  final int totalCount;
  final bool hasMessages;
  final String? latestCursor;
  final String? oldestCursor;
  final String? latestTs;
  final String? oldestTs;

  const AiTutorMessagesMetadata({
    required this.totalCount,
    required this.hasMessages,
    required this.latestCursor,
    required this.oldestCursor,
    required this.latestTs,
    required this.oldestTs,
  });
}

/// Remote data source for AI Tutor Chat — talks to AI Service at :8001.
class AiTutorChatDataSource {
  final ApiClient apiClient;

  AiTutorChatDataSource({required this.apiClient});

  bool _isSessionNotFoundError(Object error) {
    final msg = error.toString().toLowerCase();
    return msg.contains('status 404') ||
        msg.contains('404') ||
        msg.contains('not found');
  }

  String _normalizeMarkdownBoldMarkers(String text) {
    if (!text.contains('**')) return text;

    final out = <String>[];
    var inBold = false;
    int? openMarkerIndex;
    var i = 0;

    while (i < text.length) {
      final isDoubleStar =
          i + 1 < text.length && text[i] == '*' && text[i + 1] == '*';
      final isExactPair =
          isDoubleStar &&
          (i == 0 || text[i - 1] != '*') &&
          (i + 2 >= text.length || text[i + 2] != '*');

      if (!isExactPair) {
        out.add(text[i]);
        i += 1;
        continue;
      }

      final prevChar = i > 0 ? text[i - 1] : '';
      final nextChar = i + 2 < text.length ? text[i + 2] : '';
      final canOpen = nextChar.isNotEmpty && nextChar.trim().isNotEmpty;
      final canClose = prevChar.isNotEmpty && prevChar.trim().isNotEmpty;

      if (!inBold) {
        if (canOpen) {
          out.add('**');
          openMarkerIndex = out.length - 1;
          inBold = true;
        }
      } else {
        if (canClose) {
          out.add('**');
          openMarkerIndex = null;
          inBold = false;
        }
      }

      i += 2;
    }

    if (inBold && openMarkerIndex != null && openMarkerIndex < out.length) {
      out.removeAt(openMarkerIndex);
    }

    return out.join();
  }

  String _sanitizeAssistantContent(String input) {
    var text = input;

    // Remove hidden reasoning blocks if the model leaks them.
    text = text.replaceAll(
      RegExp(r'<think\b[^>]*>[\s\S]*?<\/think>', caseSensitive: false),
      '',
    );
    text = text.replaceAll(RegExp(r'<\/?think>', caseSensitive: false), '');

    // Remove leaked internal TRACECAG payloads from assistant content.
    text = text.replaceAll(
      RegExp(
        r'\[JIT_SOFT_GRAPH\]\s*(?:\n|\r\n?)?\s*\{[\s\S]*?\}\s*',
        caseSensitive: false,
      ),
      '',
    );
    text = text.replaceAll(
      RegExp(
        r'^\s*\{(?:\\?"v\\?"|"v")[\s\S]*?(?:\\?"e\\?"|"e")[\s\S]*?\}\s*$',
        caseSensitive: false,
        multiLine: true,
      ),
      '',
    );

    // Preserve markdown markers so the UI can render lists/emphasis correctly.
    // Normalize common model output like "1) item" to markdown ordered list style.
    text = text.replaceAllMapped(RegExp(r'(\d+)\)\s+'), (m) => '${m[1]}. ');
    text = text.replaceAllMapped(
      RegExp(r'(?<!\n)(\d+\.\s+)'),
      (m) => '\n${m[1]}',
    );

    // Unescape markdown punctuation if model returns escaped symbols.
    text = text.replaceAll('\\*', '*');
    text = text.replaceAll('\\_', '_');

    // Remove malformed bold markers while preserving valid markdown emphasis.
    text = _normalizeMarkdownBoldMarkers(text);

    // Normalize excessive blank lines from stripped sections.
    text = text.replaceAll(RegExp(r'\n{3,}'), '\n\n').trim();

    if (text.isEmpty) {
      return 'Squawk! I had a small glitch. Can you ask that again?';
    }

    return text;
  }

  /// Create a new AiTutor session.
  Future<AiTutorSession> createSession({required String userId}) async {
    final json = await apiClient.post(
      '/ai_tutor/sessions',
      body: {'user_id': userId},
    );
    logDebug(_tag, 'createSession: $json');

    final data = json['data'] ?? json;
    return AiTutorSession(
      sessionId: data['session_id'] ?? '',
      userId: userId,
      createdAt: DateTime.tryParse(data['created_at'] ?? '') ?? DateTime.now(),
    );
  }

  /// Send a message to AI Tutor and get a structured response.
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
    final payload = {
      'user_id': userId,
      'session_id': sessionId,
      'message': message,
      'input_type': inputType,
      if (audioBase64 != null) 'audio_base64': audioBase64,
      'enable_tts': enableTts,
      'learner_level': learnerLevel,
      if (storyContext != null) 'story_context': storyContext,
      if (subject != null && subject.isNotEmpty) 'subject': subject,
      if (topic != null && topic.isNotEmpty) 'topic': topic,
    };

    final json = await apiClient.post(
      '/ai_tutor/chat',
      body: payload,
      headers: {
        if (idempotencyKey != null && idempotencyKey.isNotEmpty)
          'X-Idempotency-Key': idempotencyKey,
      },
      timeout: AppConstants.aiOperationTimeout,
    );

    final data = json['data'] ?? json;
    logDebug(_tag, 'sendMessage response keys: ${data.keys}');

    // Parse corrections
    final corrections = <AiTutorCorrection>[];
    final rawCorrections = data['corrections'] as List?;
    if (rawCorrections != null) {
      for (final c in rawCorrections) {
        corrections.add(
          AiTutorCorrection(
            errorSpan: c['error_span'] ?? '',
            correction: c['correction'] ?? '',
            errorType: c['error_type'] ?? '',
            explanation: c['explanation'] ?? '',
          ),
        );
      }
    }

    // Parse linked concepts
    final linkedConcepts = <String>[];
    final rawConcepts = data['linked_concepts'] as List?;
    if (rawConcepts != null) {
      linkedConcepts.addAll(rawConcepts.cast<String>());
    }

    // Parse scores
    Map<String, dynamic>? scores;
    if (data['scores'] != null) {
      scores = Map<String, dynamic>.from(data['scores']);
    }

    return AiTutorMessage(
      id:
          data['message_id'] ??
          DateTime.now().millisecondsSinceEpoch.toString(),
      role: 'assistant',
      content: _sanitizeAssistantContent(
        data['ai_tutor_response'] ??
            data['response'] ??
            'Squawk! Something went wrong.',
      ),
      timestamp: DateTime.now(),
      audioBase64: data['audio_base64'],
      corrections: corrections,
      linkedConcepts: linkedConcepts,
      vietnameseHint: data['vietnamese_hint'],
      scores: scores,
    );
  }

  /// Get messages for a AI Tutor session.
  Future<List<AiTutorMessage>> getMessages({required String sessionId}) async {
    if (sessionId.isEmpty) return [];

    try {
      final json = await apiClient.get(
        '/ai_tutor/sessions/$sessionId/messages',
      );
      final data = json['data'] ?? json;
      final rawMessages = data['messages'] as List? ?? [];

      return rawMessages.map((m) {
        final role = m['role'] ?? 'user';
        final rawContent = m['content'] ?? '';
        return AiTutorMessage(
          id: m['id'] ?? '',
          role: role,
          content: role == 'assistant'
              ? _sanitizeAssistantContent(rawContent)
              : rawContent,
          timestamp: DateTime.tryParse(m['timestamp'] ?? '') ?? DateTime.now(),
        );
      }).toList();
    } catch (e) {
      logWarn(_tag, 'getMessages failed, return empty history: $e');
      return [];
    }
  }

  Future<AiTutorMessagesPage> getMessagesPaged({
    required String sessionId,
    int limit = 50,
    String? cursor,
  }) async {
    if (sessionId.isEmpty) {
      return const AiTutorMessagesPage(
        messages: [],
        hasMore: false,
        nextCursor: null,
        returned: 0,
      );
    }

    final safeLimit = limit < 1 ? 1 : (limit > 200 ? 200 : limit);

    try {
      final query = StringBuffer('limit=$safeLimit');
      if (cursor != null && cursor.isNotEmpty) {
        query.write('&cursor=${Uri.encodeComponent(cursor)}');
      }

      final json = await apiClient.get(
        '/ai_tutor/sessions/$sessionId/messages/paged?${query.toString()}',
      );
      final data = json['data'] ?? json;
      final rawMessages = data['messages'] as List? ?? [];
      final pagination = Map<String, dynamic>.from(
        (data['pagination'] ?? const <String, dynamic>{}) as Map,
      );

      final messages = rawMessages.map((m) {
        final map = Map<String, dynamic>.from(m as Map);
        final role = map['role'] ?? 'user';
        final rawContent = map['content'] ?? '';
        return AiTutorMessage(
          id: map['id'] ?? '',
          role: role,
          content: role == 'assistant'
              ? _sanitizeAssistantContent(rawContent)
              : rawContent,
          timestamp:
              DateTime.tryParse(map['timestamp'] ?? '') ?? DateTime.now(),
        );
      }).toList();

      return AiTutorMessagesPage(
        messages: messages,
        hasMore: pagination['has_more'] == true,
        nextCursor: pagination['next_cursor']?.toString(),
        returned: (pagination['returned'] as num?)?.toInt() ?? messages.length,
      );
    } catch (e) {
      if (_isSessionNotFoundError(e)) {
        logWarn(
          _tag,
          'getMessagesPaged session not found, return empty page: $e',
        );
        return const AiTutorMessagesPage(
          messages: [],
          hasMore: false,
          nextCursor: null,
          returned: 0,
        );
      }
      logWarn(_tag, 'getMessagesPaged fallback to full history: $e');
      final all = await getMessages(sessionId: sessionId);
      final page = all.length <= safeLimit
          ? all
          : all.sublist(all.length - safeLimit);
      return AiTutorMessagesPage(
        messages: page,
        hasMore: all.length > safeLimit,
        nextCursor: null,
        returned: page.length,
      );
    }
  }

  Future<AiTutorMessagesMetadata> getMessagesMetadata({
    required String sessionId,
  }) async {
    if (sessionId.isEmpty) {
      return const AiTutorMessagesMetadata(
        totalCount: 0,
        hasMessages: false,
        latestCursor: null,
        oldestCursor: null,
        latestTs: null,
        oldestTs: null,
      );
    }

    try {
      final json = await apiClient.get(
        '/ai_tutor/sessions/$sessionId/messages/metadata',
      );
      final data = json['data'] ?? json;
      final metadata = Map<String, dynamic>.from(
        (data['metadata'] ?? const <String, dynamic>{}) as Map,
      );
      final totalCount = (metadata['total_count'] as num?)?.toInt() ?? 0;

      return AiTutorMessagesMetadata(
        totalCount: totalCount,
        hasMessages: metadata['has_messages'] == true,
        latestCursor: metadata['latest_cursor']?.toString(),
        oldestCursor: metadata['oldest_cursor']?.toString(),
        latestTs: metadata['latest_ts']?.toString(),
        oldestTs: metadata['oldest_ts']?.toString(),
      );
    } catch (e) {
      if (_isSessionNotFoundError(e)) {
        rethrow;
      }
      logWarn(_tag, 'getMessagesMetadata failed, return empty metadata: $e');
      return const AiTutorMessagesMetadata(
        totalCount: 0,
        hasMessages: false,
        latestCursor: null,
        oldestCursor: null,
        latestTs: null,
        oldestTs: null,
      );
    }
  }

  Future<List<AiTutorSession>> getSessions({required String userId}) async {
    try {
      final json = await apiClient.get('/ai_tutor/sessions/user/$userId');
      final data = json['data'] ?? json;
      final rawSessions = data['sessions'] as List? ?? [];

      return rawSessions.map((s) {
        return AiTutorSession(
          sessionId: s['session_id'] ?? '',
          userId: s['user_id'] ?? userId,
          createdAt: DateTime.tryParse(s['created_at'] ?? '') ?? DateTime.now(),
          title: s['title']?.toString(),
          updatedAt: DateTime.tryParse(s['updated_at'] ?? ''),
          messageCount: (s['message_count'] as num?)?.toInt(),
        );
      }).toList();
    } catch (e) {
      logWarn(_tag, 'getSessions failed: $e');
      return [];
    }
  }

  Future<void> renameSession({
    required String sessionId,
    required String title,
  }) async {
    await apiClient.post(
      '/ai_tutor/sessions/$sessionId/rename',
      body: {'title': title},
    );
  }

  Future<void> deleteSession({required String sessionId}) async {
    await apiClient.post('/ai_tutor/sessions/$sessionId/delete', body: {});
  }

  /// Send a message to AI Tutor and receive an SSE stream of events.
  ///
  /// Yields [AiTutorStreamEvent] values in order:
  ///   1. [AiTutorStreamThinking]   — pipeline started
  ///   2. [AiTutorStreamChunk]      — one word at a time (typewriter effect)
  ///   3. [AiTutorStreamDone]       — full message with metadata
  ///   4. [AiTutorStreamError]      — on pipeline failure (may not follow thinking)
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
  }) async* {
    final payload = {
      'user_id': userId,
      'session_id': sessionId,
      'message': message,
      'input_type': inputType,
      if (audioBase64 != null) 'audio_base64': audioBase64,
      'enable_tts': enableTts,
      'learner_level': learnerLevel,
      if (storyContext != null) 'story_context': storyContext,
      if (subject != null && subject.isNotEmpty) 'subject': subject,
      if (topic != null && topic.isNotEmpty) 'topic': topic,
    };

    final rawStream = apiClient.postStream('/ai_tutor/stream', body: payload);

    // SSE parsing state
    String? currentEvent;
    final buffer = StringBuffer();

    await for (final chunk in rawStream.transform(utf8.decoder)) {
      buffer.write(chunk);
      // Process all complete lines in the buffer
      while (true) {
        final content = buffer.toString();
        final newlineIdx = content.indexOf('\n');
        if (newlineIdx == -1) break;

        final line = content.substring(0, newlineIdx).trimRight();
        buffer.clear();
        if (newlineIdx + 1 < content.length) {
          buffer.write(content.substring(newlineIdx + 1));
        }

        if (line.isEmpty) {
          // Empty line = end of SSE event block; reset event name
          currentEvent = null;
          continue;
        }

        if (line.startsWith('event:')) {
          currentEvent = line.substring(6).trim();
          continue;
        }

        if (line.startsWith('data:')) {
          final dataStr = line.substring(5).trim();
          final event = currentEvent;

          switch (event) {
            case 'thinking':
              yield const AiTutorStreamThinking();
              break;
            case 'chunk':
              try {
                final json = jsonDecode(dataStr) as Map<String, dynamic>;
                final text = json['text'] as String? ?? '';
                if (text.isNotEmpty) yield AiTutorStreamChunk(text);
              } catch (_) {}
              break;
            case 'done':
              try {
                final json = jsonDecode(dataStr) as Map<String, dynamic>;
                final corrections = <AiTutorCorrection>[];
                final rawCorrections = json['corrections'] as List?;
                if (rawCorrections != null) {
                  for (final c in rawCorrections) {
                    corrections.add(
                      AiTutorCorrection(
                        errorSpan: c['error_span'] ?? '',
                        correction: c['correction'] ?? '',
                        errorType: c['error_type'] ?? '',
                        explanation: c['explanation'] ?? '',
                      ),
                    );
                  }
                }
                final linkedConcepts = <String>[];
                final rawConcepts = json['linked_concepts'] as List?;
                if (rawConcepts != null) {
                  linkedConcepts.addAll(rawConcepts.cast<String>());
                }
                Map<String, dynamic>? scores;
                if (json['scores'] != null) {
                  scores = Map<String, dynamic>.from(json['scores'] as Map);
                }
                yield AiTutorStreamDone(
                  messageId: json['message_id'] as String? ?? '',
                  sessionId: json['session_id'] as String? ?? sessionId,
                  fullText: json['ai_tutor_response'] as String?,
                  corrections: corrections,
                  linkedConcepts: linkedConcepts,
                  vietnameseHint: json['vietnamese_hint'] as String?,
                  scores: scores,
                  audioBase64: json['audio_base64'] as String?,
                  storyContext: json['story_context'] as String?,
                  metadata: json['metadata'] != null
                      ? Map<String, dynamic>.from(json['metadata'] as Map)
                      : const {},
                );
              } catch (e) {
                logError(
                  _tag,
                  'sendMessageStream: failed to parse done event: $e',
                );
              }
              break;
            case 'error':
              try {
                final json = jsonDecode(dataStr) as Map<String, dynamic>;
                yield AiTutorStreamError(
                  json['error'] as String? ?? 'Unknown error',
                );
              } catch (_) {
                yield const AiTutorStreamError('Stream error');
              }
              break;
            default:
              break;
          }
        }
      }
    }
  }
}

// AiTutorStreamEvent types are defined in domain/entities/ai_tutor_stream_event.dart
