import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter/foundation.dart' show kIsWeb, kReleaseMode, debugPrint;
import 'package:easy_localization/easy_localization.dart';
import 'package:sqflite/sqflite.dart';
import 'package:sqflite_common_ffi_web/sqflite_ffi_web.dart';
import 'package:provider/provider.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:ai_tutor_app/firebase_options.dart';
import 'package:ai_tutor_app/core/services/deep_link_service.dart';
import 'package:ai_tutor_app/core/services/purchases_service.dart';
import 'package:ai_tutor_app/core/services/firebase_messaging_service.dart';
import 'package:ai_tutor_app/core/services/app_navigation_service.dart';
import 'package:ai_tutor_app/core/services/notification_service.dart';
import 'package:ai_tutor_app/core/theme/app_theme.dart';
import 'package:ai_tutor_app/core/di/injection_container.dart' as di;
import 'package:ai_tutor_app/core/network/api_config.dart';
import 'package:ai_tutor_app/core/utils/app_logger.dart';
// import 'package:ai_tutor_app/core/services/course_import_service.dart'; // Already disabled
import 'package:ai_tutor_app/core/services/health_check_service.dart';
import 'package:ai_tutor_app/core/localization/network_first_asset_loader.dart';
import 'package:ai_tutor_app/core/startup/startup_coordinator.dart';
import 'package:ai_tutor_app/core/startup/startup_task.dart';
import 'package:ai_tutor_app/core/startup/local_state_migration_service.dart';
import 'package:ai_tutor_app/core/services/locale_service.dart';
import 'package:ai_tutor_app/core/services/language_flag_cache.dart';
import 'package:ai_tutor_app/core/services/sync_queue_lifecycle_runner.dart';
import 'package:ai_tutor_app/core/network/api_client.dart';
import 'package:ai_tutor_app/features/achievements/presentation/providers/achievement_provider.dart';
import 'package:ai_tutor_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:ai_tutor_app/features/auth/presentation/pages/reset_password_page.dart';
import 'package:ai_tutor_app/features/auth/presentation/widgets/auth_wrapper.dart';
import 'package:ai_tutor_app/features/chat/presentation/providers/chat_provider.dart';
import 'package:ai_tutor_app/features/chat/presentation/providers/story_provider.dart';
import 'package:ai_tutor_app/features/course/presentation/providers/course_provider.dart';
import 'package:ai_tutor_app/features/learning/presentation/providers/learning_provider.dart';
import 'package:ai_tutor_app/features/learning/presentation/providers/tutor_catalog_provider.dart';
import 'package:ai_tutor_app/features/level/presentation/providers/level_provider.dart';
import 'package:ai_tutor_app/features/level/presentation/providers/proficiency_provider.dart';
import 'package:ai_tutor_app/features/notifications/presentation/providers/notification_provider.dart';
import 'package:ai_tutor_app/features/profile/presentation/providers/profile_provider.dart';
import 'package:ai_tutor_app/features/progress/presentation/providers/progress_provider.dart';
import 'package:ai_tutor_app/features/social/presentation/providers/social_provider.dart';
import 'package:ai_tutor_app/features/user/presentation/providers/user_provider.dart';
import 'package:ai_tutor_app/features/user/presentation/providers/settings_provider.dart';
import 'package:ai_tutor_app/features/home/presentation/providers/home_provider.dart';
import 'package:ai_tutor_app/features/voice/presentation/providers/voice_provider.dart';
import 'package:ai_tutor_app/features/voice/presentation/providers/tts_settings_provider.dart';
import 'package:ai_tutor_app/features/voice/presentation/providers/speech_recognition_provider.dart';
import 'package:ai_tutor_app/features/progress/presentation/providers/streak_provider.dart';
import 'package:ai_tutor_app/features/progress/presentation/providers/daily_challenges_provider.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/presentation/providers/ai_tutor_chat_provider.dart';
import 'package:ai_tutor_app/features/ai_tutor_chat/presentation/pages/ai_tutor_chat_page.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await EasyLocalization.ensureInitialized();

  if (kIsWeb) {
    // Avoid sqflite web worker boot failures when sqflite_sw.js is not deployed.
    databaseFactory = databaseFactoryFfiWebNoWebWorker;
  }

  // Add error handler for Flutter and Dart errors
  FlutterError.onError = (details) {
    FlutterError.presentError(details);
    debugPrint('Flutter Error: ${details.exception}');
  };

  try {
    // Load only public client config. Raw .env files may contain server
    // secrets and must never be bundled into Flutter web assets.
    final envFile = kReleaseMode
        ? 'assets/env/prod_config'
        : 'assets/env/dev_config';
    await dotenv.load(fileName: envFile);
  } catch (e) {
    debugPrint('Warning: Could not load public config: $e');
  }

  debugPrint('Backend API base URL: ${ApiConfig.baseUrl}');
  debugPrint('AI service base URL: ${ApiConfig.aiServiceUrl}');

  // Initialize Firebase
  try {
    await Firebase.initializeApp(
      options: DefaultFirebaseOptions.currentPlatform,
    );
    debugPrint('Firebase initialized successfully');

    // Crashlytics: route Flutter framework errors to Crashlytics in release
    if (!kIsWeb) {
      FlutterError.onError = kReleaseMode
          ? FirebaseCrashlytics.instance.recordFlutterFatalError
          : FlutterError.presentError;
      // Also catch async errors thrown outside the Flutter widget tree
    }

    // Initialize Firebase Cloud Messaging
    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);
    // Push notification permission should not block app startup
    // so we delay it until after runApp()
  } catch (e) {
    debugPrint('Warning: Firebase initialization failed: $e');
  }

  // Initialize Dependency Injection (skip database on web)
  await LocalStateMigrationService().runIfNeeded();
  await di.initializeDependencies(skipDatabase: kIsWeb);

  // Initialize local notifications early so Settings sync can schedule reliably.
  await di.sl<NotificationService>().ensureInitialized();

  // Run startup tasks (health check, seeding). Keep non-blocking for first frame.
  if (!kIsWeb) {
    final coordinator = StartupCoordinator(
      tasks: [
        StartupTask(
          id: 'health_check',
          label: 'Ping backend /health',
          action: () async {
            final ok = await di.sl<HealthCheckService>().ping();
            if (!ok) throw Exception('Backend health check failed');
          },
        ),
      ],
    );

    unawaited(
      coordinator.run(
        onProgress: (result) => logDebug(
          'Startup',
          '${result.id}: ${result.status.name} ${result.message ?? ''}',
        ),
      ),
    );
  }

  // Wrap runApp in runZonedGuarded so uncaught async errors are forwarded to
  // Crashlytics. In release mode only — dev keeps the default red-screen behavior.
  if (!kIsWeb && kReleaseMode) {
    runZonedGuarded(
      () => runApp(
        EasyLocalization(
          supportedLocales: const [
            Locale('vi'),
            Locale('en'),
            Locale('ja'),
            Locale('ko'),
            Locale('zh'),
            Locale('fr'),
            Locale('es'),
          ],
          path: 'assets/i18n',
          fallbackLocale: const Locale('vi'),
          startLocale: const Locale('vi'),
          useOnlyLangCode: true,
          assetLoader: NetworkFirstAssetLoader(),
          child: const AiTutorApp(),
        ),
      ),
      (error, stack) =>
          FirebaseCrashlytics.instance.recordError(error, stack, fatal: true),
    );
  } else {
    runApp(
      EasyLocalization(
        supportedLocales: const [
          Locale('vi'),
          Locale('en'),
          Locale('ja'),
          Locale('ko'),
          Locale('zh'),
          Locale('fr'),
          Locale('es'),
        ],
        path: 'assets/i18n',
        fallbackLocale: const Locale('vi'),
        startLocale: const Locale('vi'),
        useOnlyLangCode: true,
        assetLoader: NetworkFirstAssetLoader(),
        child: const AiTutorApp(),
      ),
    );
  }

  // Initialize Firebase Messaging and Deep Links after UI starts rendering
  WidgetsBinding.instance.addPostFrameCallback((_) async {
    try {
      await FirebaseMessagingService.instance.initialize();
      debugPrint('Firebase Messaging initialized successfully');
    } catch (e) {
      debugPrint('Warning: Firebase Messaging initialization failed: $e');
    }
    try {
      await DeepLinkService.instance.init();
      debugPrint('Deep link service initialized');
    } catch (e) {
      debugPrint('Warning: Deep link service initialization failed: $e');
    }
    if (!kIsWeb) {
      try {
        await PurchasesService.instance.init(
          iosApiKey: dotenv.maybeGet('REVENUECAT_API_KEY_IOS'),
          androidApiKey: dotenv.maybeGet('REVENUECAT_API_KEY_ANDROID'),
        );
      } catch (e) {
        debugPrint('Warning: RevenueCat initialization failed: $e');
      }
    }
  });
}

class AiTutorApp extends StatefulWidget {
  const AiTutorApp({super.key});

  @override
  State<AiTutorApp> createState() => _AiTutorAppState();
}

class _AiTutorAppState extends State<AiTutorApp> with WidgetsBindingObserver {
  SyncQueueLifecycleRunner? _syncQueueRunner;
  // Tracks the last language code that was synced to EasyLocalization.
  // Guards against running locale sync on every Consumer2 rebuild (e.g. theme
  // changes), which on Flutter web causes a race condition that prevents the
  // theme from visually applying until an unrelated AuthProvider notification
  // triggers another Consumer2 rebuild.
  String? _lastSyncedLanguage;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        unawaited(LanguageFlagCache.preload(context));
      }
    });
    if (!kIsWeb) {
      _syncQueueRunner = SyncQueueLifecycleRunner(
        apiClient: di.sl<ApiClient>(),
      );
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _syncQueueRunner?.start();
      });
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _syncQueueRunner?.stop();
    DeepLinkService.instance.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _syncQueueRunner?.onAppResumed();
    }
  }

  String? _extractResetTokenFromDeepLink() {
    final queryToken = Uri.base.queryParameters['token'];
    if (queryToken != null && queryToken.isNotEmpty) {
      return queryToken;
    }

    final fragment = Uri.base.fragment;
    if (fragment.isNotEmpty) {
      final fragmentUri = Uri.tryParse(fragment);
      final fragmentToken = fragmentUri?.queryParameters['token'];
      if (fragmentToken != null && fragmentToken.isNotEmpty) {
        return fragmentToken;
      }
    }

    return null;
  }

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => di.sl<AuthProvider>()),
        ChangeNotifierProvider(create: (_) => di.sl<UserProvider>()),
        ChangeNotifierProvider(create: (_) => di.sl<HomeProvider>()),
        ChangeNotifierProvider(create: (_) => di.sl<ProfileProvider>()),
        ChangeNotifierProvider(create: (_) => di.sl<ChatProvider>()),
        ChangeNotifierProvider(create: (_) => di.sl<StoryProvider>()),
        ChangeNotifierProvider(create: (_) => di.sl<CourseProvider>()),
        ChangeNotifierProvider(create: (_) => di.sl<LearningProvider>()),
        ChangeNotifierProvider(
          create: (_) => TutorCatalogProvider(apiClient: di.sl<ApiClient>()),
        ),
        ChangeNotifierProvider(create: (_) => di.sl<ProgressProvider>()),
        ChangeNotifierProvider(create: (_) => di.sl<VoiceProvider>()),
        ChangeNotifierProvider(
          create: (_) => di.sl<SpeechRecognitionProvider>(),
        ),
        ChangeNotifierProvider(
          create: (_) => di.sl<TtsSettingsProvider>()..init(),
        ),
        ChangeNotifierProvider(
          create: (_) => di.sl<StreakProvider>()..loadStreak(),
        ),
        ChangeNotifierProvider(
          create: (_) => di.sl<DailyChallengesProvider>()..loadChallenges(),
        ),
        ChangeNotifierProvider(create: (_) => di.sl<AchievementProvider>()),
        ChangeNotifierProvider(create: (_) => di.sl<NotificationProvider>()),
        ChangeNotifierProvider(create: (_) => di.sl<LevelProvider>()),
        ChangeNotifierProvider(create: (_) => di.sl<ProficiencyProvider>()),
        ChangeNotifierProvider(create: (_) => di.sl<SettingsProvider>()),
        ChangeNotifierProvider(create: (_) => di.sl<SocialProvider>()),
        // Phase 6: AI Tutor Chat — Story Adventure
        ChangeNotifierProvider(create: (_) => di.sl<AiTutorChatProvider>()),
      ],
      child: Consumer2<SettingsProvider, AuthProvider>(
        builder: (context, settings, auth, child) {
          // Reset sync state on logout so the next login re-syncs the locale.
          if (auth.currentUser == null) {
            _lastSyncedLanguage = null;
          }

          // Sync locale from settings only when the language value actually
          // changes (initial load or explicit language switch). Running this on
          // every Consumer2 rebuild (e.g. theme changes) caused a Flutter web
          // race condition where the async setLocale() call interfered with the
          // pending theme repaint, leaving the UI in the old theme until an
          // unrelated AuthProvider notification triggered another rebuild.
          final currentLanguage =
              (auth.currentUser != null && settings.settings != null)
              ? settings.language
              : null;
          if (currentLanguage != null &&
              currentLanguage != _lastSyncedLanguage) {
            _lastSyncedLanguage = currentLanguage;
            final langToSync = currentLanguage;
            WidgetsBinding.instance.addPostFrameCallback((_) async {
              if (!mounted) return;
              final savedLocale = await LocaleService.getSavedLocale();
              if (!mounted || !context.mounted) return;
              if (savedLocale != langToSync) {
                await LocaleService.saveLocale(langToSync);
                if (!mounted || !context.mounted) return;
                await context.setLocale(Locale(langToSync));
                debugPrint('Locale synced from settings: $langToSync');
              }
            });
          }

          return MaterialApp(
            title: 'ThinkTutor AI',
            navigatorKey: AppNavigationService.navigatorKey,
            debugShowCheckedModeBanner: false,
            theme: AppTheme.lightTheme,
            darkTheme: AppTheme.darkTheme,
            themeMode: settings.themeMode,
            themeAnimationDuration: Duration.zero,
            builder: (context, child) {
              return AnnotatedRegion<SystemUiOverlayStyle>(
                value: AppTheme.systemUiOverlayStyle(
                  Theme.of(context).brightness,
                ),
                child: child ?? const SizedBox.shrink(),
              );
            },
            // Localization — easy_localization handles locale state
            locale: context.locale,
            supportedLocales: context.supportedLocales,
            localizationsDelegates: context.localizationDelegates,
            home: const AuthWrapper(),
            routes: {
              // Phase 6: AI Tutor Chat
              '/ai_tutor': (context) => const AiTutorChatPage(),
              '/reset-password': (context) {
                final args = ModalRoute.of(context)?.settings.arguments;
                String? token;
                if (args is String) {
                  token = args;
                } else if (args is Map<String, dynamic>) {
                  token = args['token'] as String?;
                }
                token ??= _extractResetTokenFromDeepLink();
                return ResetPasswordPage(initialToken: token);
              },
            },
          );
        },
      ),
    );
  }
}
