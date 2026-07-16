import 'package:ai_tutor_app/core/di/core_di.dart';
import 'package:ai_tutor_app/core/di/service_locator.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/data/datasources/ai_tutor_chat_data_source.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/data/repositories/ai_tutor_chat_repository_impl.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/domain/repositories/ai_tutor_chat_repository.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/presentation/providers/ai_tutor_chat_provider.dart';

/// Register all AI Tutor Chat dependencies.
void registerAiTutorChatModule() {
  // DataSource → uses AiApiClient (port 8001)
  sl.registerLazySingleton<AiTutorChatDataSource>(
    () => AiTutorChatDataSource(apiClient: sl<AiApiClient>()),
  );

  // Repository
  sl.registerLazySingleton<AiTutorChatRepository>(
    () => AiTutorChatRepositoryImpl(dataSource: sl<AiTutorChatDataSource>()),
  );

  // Provider (factory → one per widget)
  sl.registerFactory<AiTutorChatProvider>(
    () => AiTutorChatProvider(
      repository: sl<AiTutorChatRepository>(),
      aiClient: sl<AiApiClient>(),
    ),
  );
}
