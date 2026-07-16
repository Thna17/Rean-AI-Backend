import 'package:dartz/dartz.dart';
import 'package:ai_tutor_app/core/error/failures.dart';
import 'package:ai_tutor_app/features/user/domain/entities/user_stats_entity.dart';
import 'package:ai_tutor_app/features/user/domain/repositories/user_repository.dart';

/// Use case for getting user statistics
class GetUserStatsUseCase {
  final UserRepository repository;

  const GetUserStatsUseCase(this.repository);

  Future<Either<Failure, UserStatsEntity>> call() {
    return repository.getUserStats();
  }
}
