import 'package:dartz/dartz.dart';
import 'package:ai_tutor_app/core/error/failures.dart';
import 'package:ai_tutor_app/core/usecase/usecase.dart';
import 'package:ai_tutor_app/features/auth/domain/entities/user_entity.dart';
import 'package:ai_tutor_app/features/auth/domain/repositories/auth_repository.dart';

class GetCurrentUserUseCase implements UseCase<UserEntity, NoParams> {
  final AuthRepository repository;

  GetCurrentUserUseCase(this.repository);

  @override
  Future<Either<Failure, UserEntity>> call(NoParams params) async {
    return await repository.getCurrentUser();
  }
}
