import 'package:ai_tutor_app/features/ai_tutor_chat/domain/entities/ai_tutor_message.dart';

sealed class AiTutorStreamEvent {
  const AiTutorStreamEvent();
}

/// Sent immediately: the AI pipeline has started processing.
class AiTutorStreamThinking extends AiTutorStreamEvent {
  const AiTutorStreamThinking();
}

/// One word (or token) from the AI response — shows typewriter effect.
class AiTutorStreamChunk extends AiTutorStreamEvent {
  final String text;
  const AiTutorStreamChunk(this.text);
}

/// Final event: full message with corrections, audio, etc.
class AiTutorStreamDone extends AiTutorStreamEvent {
  final String messageId;
  final String sessionId;

  /// Full response text — fallback when chunk accumulation is empty.
  final String? fullText;
  final List<AiTutorCorrection> corrections;
  final List<String> linkedConcepts;
  final String? vietnameseHint;
  final Map<String, dynamic>? scores;
  final String? audioBase64;
  final String? storyContext;
  final Map<String, dynamic> metadata;

  const AiTutorStreamDone({
    required this.messageId,
    required this.sessionId,
    this.fullText,
    required this.corrections,
    required this.linkedConcepts,
    this.vietnameseHint,
    this.scores,
    this.audioBase64,
    this.storyContext,
    required this.metadata,
  });
}

/// Sent if the pipeline fails unrecoverably.
class AiTutorStreamError extends AiTutorStreamEvent {
  final String error;
  const AiTutorStreamError(this.error);
}
