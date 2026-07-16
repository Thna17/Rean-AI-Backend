import 'package:dartz/dartz.dart';
import 'package:ai_tutor_app/core/error/failures.dart';
import 'package:ai_tutor_app/core/usecase/usecase.dart';
import 'package:ai_tutor_app/features/course/domain/entities/course_detail_entity.dart';
import 'package:ai_tutor_app/features/course/domain/repositories/course_repository.dart';

/// Get detailed course information with roadmap
class GetCourseDetailUseCase implements UseCase<CourseDetailEntity, String> {
  final CourseRepository repository;

  GetCourseDetailUseCase(this.repository);

  @override
  Future<Either<Failure, CourseDetailEntity>> call(String courseId) async {
    return await repository.getCourseDetail(courseId);
  }
}
