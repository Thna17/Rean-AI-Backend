import 'package:flutter/foundation.dart';
import 'package:ai_tutor_app/core/network/api_client.dart';
import 'package:ai_tutor_app/features/learning/presentation/models/tutor_catalog.dart';

class TutorDashboardData {
  const TutorDashboardData({
    required this.studentName,
    required this.streakDays,
    required this.todayCompleted,
    required this.todayTarget,
    required this.continueSubject,
    required this.continueTopic,
    required this.continueProgress,
    required this.weakTopics,
    required this.recommendationSubject,
    required this.recommendationTopic,
    required this.completionPercentage,
    required this.scoreTrend,
    required this.recentMistakes,
  });

  final String studentName;
  final int streakDays;
  final int todayCompleted;
  final int todayTarget;
  final String continueSubject;
  final String continueTopic;
  final double continueProgress;
  final List<Map<String, dynamic>> weakTopics;
  final String recommendationSubject;
  final String recommendationTopic;
  final int completionPercentage;
  final List<Map<String, dynamic>> scoreTrend;
  final List<Map<String, dynamic>> recentMistakes;

  factory TutorDashboardData.fromJson(Map<String, dynamic> json) {
    final todayGoal = Map<String, dynamic>.from(
      (json['today_goal'] as Map?) ?? const <String, dynamic>{},
    );
    final continueLearning = Map<String, dynamic>.from(
      (json['continue_learning'] as Map?) ?? const <String, dynamic>{},
    );
    final recommendation = Map<String, dynamic>.from(
      (json['recommendation'] as Map?) ?? const <String, dynamic>{},
    );
    final weakTopics = (json['weak_topics'] as List<dynamic>? ?? const [])
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList(growable: false);
    final scoreTrend = (json['score_trend'] as List<dynamic>? ?? const [])
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList(growable: false);
    final recentMistakes =
        (json['recent_mistakes'] as List<dynamic>? ?? const [])
            .map((item) => Map<String, dynamic>.from(item as Map))
            .toList(growable: false);

    return TutorDashboardData(
      studentName: json['student_name'] as String? ?? 'Student',
      streakDays: (json['streak_days'] as num?)?.toInt() ?? 0,
      todayCompleted: (todayGoal['completed'] as num?)?.toInt() ?? 0,
      todayTarget: (todayGoal['target'] as num?)?.toInt() ?? 3,
      continueSubject: continueLearning['subject'] as String? ?? 'Mathematics',
      continueTopic: continueLearning['topic'] as String? ?? 'Linear Equations',
      continueProgress: ((continueLearning['progress'] as num?) ?? 0.0)
          .toDouble(),
      weakTopics: weakTopics,
      recommendationSubject:
          recommendation['subject'] as String? ?? 'Mathematics',
      recommendationTopic:
          recommendation['topic'] as String? ?? 'Linear Equations',
      completionPercentage:
          (json['completion_percentage'] as num?)?.toInt() ?? 0,
      scoreTrend: scoreTrend,
      recentMistakes: recentMistakes,
    );
  }
}

class TutorCatalogProvider extends ChangeNotifier {
  TutorCatalogProvider({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  List<TutorSubject> _subjects = TutorCatalog.subjects;
  TutorDashboardData? _dashboard;
  bool _isLoadingSubjects = false;
  bool _isLoadingDashboard = false;
  String? _error;

  List<TutorSubject> get subjects => _subjects;
  TutorDashboardData? get dashboard => _dashboard;
  bool get isLoadingSubjects => _isLoadingSubjects;
  bool get isLoadingDashboard => _isLoadingDashboard;
  String? get error => _error;

  Future<void> loadSubjects() async {
    _isLoadingSubjects = true;
    _error = null;
    notifyListeners();
    try {
      final json = await _apiClient.get('/tutor/subjects');
      final rawSubjects = (json['subjects'] as List<dynamic>? ?? const []);
      if (rawSubjects.isNotEmpty) {
        _subjects = rawSubjects
            .map(
              (item) =>
                  TutorSubject.fromJson(Map<String, dynamic>.from(item as Map)),
            )
            .toList(growable: false);
      }
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoadingSubjects = false;
      notifyListeners();
    }
  }

  Future<void> loadDashboard() async {
    _isLoadingDashboard = true;
    _error = null;
    notifyListeners();
    try {
      final json = await _apiClient.get('/tutor/dashboard');
      _dashboard = TutorDashboardData.fromJson(json);
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoadingDashboard = false;
      notifyListeners();
    }
  }

  TutorSubject subjectById(String subjectId) {
    return _subjects.firstWhere(
      (subject) => subject.id == subjectId,
      orElse: () => TutorCatalog.byId(subjectId),
    );
  }

  Future<String?> createGuidedAttempt({
    required TutorSubject subject,
    required TutorTopic topic,
  }) async {
    try {
      final json = await _apiClient.post(
        '/tutor/guided-attempts',
        body: {
          'subject_id': subject.id,
          'subject_title': subject.title,
          'topic_id': topic.id,
          'topic_title': topic.title,
          'problem_prompt': topic.guidedProblem.prompt,
        },
      );
      return json['id'] as String?;
    } catch (e) {
      _error = e.toString();
      notifyListeners();
      return null;
    }
  }

  Future<void> submitGuidedStep({
    required String attemptId,
    required int stepIndex,
    required String studentAnswer,
    required String expectedStep,
    required String feedback,
    required bool isCorrect,
    bool hintRequested = false,
    bool completeAttempt = false,
  }) async {
    try {
      await _apiClient.post(
        '/tutor/guided-attempts/$attemptId/steps',
        body: {
          'step_index': stepIndex,
          'student_answer': studentAnswer,
          'expected_step': expectedStep,
          'feedback': feedback,
          'is_correct': isCorrect,
          'hint_requested': hintRequested,
          'complete_attempt': completeAttempt,
        },
      );
    } catch (e) {
      _error = e.toString();
      notifyListeners();
    }
  }

  Future<String?> createQuizAttempt({
    required TutorSubject subject,
    required TutorTopic topic,
  }) async {
    try {
      final json = await _apiClient.post(
        '/tutor/quiz-attempts',
        body: {
          'subject_id': subject.id,
          'subject_title': subject.title,
          'topic_id': topic.id,
          'topic_title': topic.title,
          'total_questions': topic.quizQuestions.length,
        },
      );
      return json['id'] as String?;
    } catch (e) {
      _error = e.toString();
      notifyListeners();
      return null;
    }
  }

  Future<void> submitQuizAnswer({
    required String attemptId,
    required int questionIndex,
    required QuizQuestion question,
    required int selectedIndex,
    required bool isCorrect,
  }) async {
    try {
      await _apiClient.post(
        '/tutor/quiz-attempts/$attemptId/answers',
        body: {
          'question_index': questionIndex,
          'question': question.question,
          'selected_index': selectedIndex,
          'correct_index': question.correctIndex,
          'is_correct': isCorrect,
          'explanation': question.explanation,
        },
      );
    } catch (e) {
      _error = e.toString();
      notifyListeners();
    }
  }

  Future<void> completeQuizAttempt({
    required String attemptId,
    required int score,
    required int correctCount,
    required int totalQuestions,
  }) async {
    try {
      final percentage = totalQuestions == 0
          ? 0
          : ((score / totalQuestions) * 100).round();
      await _apiClient.post(
        '/tutor/quiz-attempts/$attemptId/complete',
        body: {'score': percentage, 'correct_count': correctCount},
      );
      await loadDashboard();
    } catch (e) {
      _error = e.toString();
      notifyListeners();
    }
  }
}
