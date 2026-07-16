import 'package:dartz/dartz.dart';
import 'package:ai_tutor_app/core/error/failures.dart';
import 'package:ai_tutor_app/core/usecase/usecase.dart';
import 'package:ai_tutor_app/features/learning/domain/entities/lesson_entity.dart';
import 'package:ai_tutor_app/features/learning/domain/repositories/learning_repository.dart';

/// Get Lesson Content Use Case
/// Fetches the content/exercises for a specific lesson
class GetLessonContentUseCase
    implements UseCase<LessonEntity, GetLessonContentParams> {
  final LearningRepository _repository;

  GetLessonContentUseCase({required LearningRepository repository})
    : _repository = repository;

  @override
  Future<Either<Failure, LessonEntity>> call(GetLessonContentParams params) {
    return _repository.getLessonContent(params.lessonId);
  }
}

/// Parameters for GetLessonContentUseCase
class GetLessonContentParams {
  final String lessonId;

  GetLessonContentParams({required this.lessonId});
}
