import 'package:dartz/dartz.dart';
import 'package:ai_tutor_app/core/error/failures.dart';
import 'package:ai_tutor_app/core/usecase/usecase.dart';
import 'package:ai_tutor_app/features/auth/domain/repositories/auth_repository.dart';

class SignOutUseCase implements UseCase<void, NoParams> {
  final AuthRepository repository;

  SignOutUseCase(this.repository);

  @override
  Future<Either<Failure, void>> call(NoParams params) async {
    return await repository.logout();
  }
}
