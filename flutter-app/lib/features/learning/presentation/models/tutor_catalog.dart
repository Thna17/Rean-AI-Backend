import 'package:flutter/material.dart';

class TutorSubject {
  const TutorSubject({
    required this.id,
    required this.title,
    required this.icon,
    required this.color,
    required this.description,
    required this.topics,
  });

  final String id;
  final String title;
  final IconData icon;
  final Color color;
  final String description;
  final List<TutorTopic> topics;

  factory TutorSubject.fromJson(Map<String, dynamic> json) {
    final rawTopics = (json['topics'] as List<dynamic>? ?? const []);
    return TutorSubject(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      icon: _iconFromName(json['icon'] as String?),
      color: _colorFromHex(json['color'] as String?),
      description: json['description'] as String? ?? '',
      topics: rawTopics
          .map(
            (topic) => TutorTopic.fromJson(
              Map<String, dynamic>.from(topic as Map)
                ..putIfAbsent('subject_id', () => json['id']),
            ),
          )
          .toList(growable: false),
    );
  }
}

class TutorTopic {
  const TutorTopic({
    required this.id,
    required this.subjectId,
    required this.title,
    required this.subtitle,
    required this.progress,
    required this.guidedProblem,
    required this.quizQuestions,
  });

  final String id;
  final String subjectId;
  final String title;
  final String subtitle;
  final double progress;
  final GuidedProblem guidedProblem;
  final List<QuizQuestion> quizQuestions;

  factory TutorTopic.fromJson(Map<String, dynamic> json) {
    final rawQuiz = (json['quiz_questions'] as List<dynamic>? ?? const []);
    return TutorTopic(
      id: json['id'] as String? ?? '',
      subjectId: json['subject_id'] as String? ?? '',
      title: json['title'] as String? ?? '',
      subtitle: json['subtitle'] as String? ?? '',
      progress: ((json['progress'] as num?) ?? 0).toDouble(),
      guidedProblem: GuidedProblem.fromJson(
        Map<String, dynamic>.from(
          (json['guided_problem'] as Map?) ?? const <String, dynamic>{},
        ),
      ),
      quizQuestions: rawQuiz
          .map(
            (item) =>
                QuizQuestion.fromJson(Map<String, dynamic>.from(item as Map)),
          )
          .toList(growable: false),
    );
  }
}

class GuidedProblem {
  const GuidedProblem({
    required this.prompt,
    required this.coachIntro,
    required this.steps,
    required this.expectedNextStep,
  });

  final String prompt;
  final String coachIntro;
  final List<GuidedStep> steps;
  final String expectedNextStep;

  factory GuidedProblem.fromJson(Map<String, dynamic> json) {
    final rawSteps = (json['steps'] as List<dynamic>? ?? const []);
    return GuidedProblem(
      prompt: json['prompt'] as String? ?? '',
      coachIntro:
          json['coach_intro'] as String? ?? json['coachIntro'] as String? ?? '',
      steps: rawSteps
          .map(
            (item) =>
                GuidedStep.fromJson(Map<String, dynamic>.from(item as Map)),
          )
          .toList(growable: false),
      expectedNextStep:
          json['expected_next_step'] as String? ??
          json['expectedNextStep'] as String? ??
          '',
    );
  }
}

class GuidedStep {
  const GuidedStep({
    required this.title,
    required this.explanation,
    required this.hint,
  });

  final String title;
  final String explanation;
  final String hint;

  factory GuidedStep.fromJson(Map<String, dynamic> json) {
    return GuidedStep(
      title: json['title'] as String? ?? '',
      explanation: json['explanation'] as String? ?? '',
      hint: json['hint'] as String? ?? '',
    );
  }
}

class QuizQuestion {
  const QuizQuestion({
    required this.question,
    required this.options,
    required this.correctIndex,
    required this.explanation,
  });

  final String question;
  final List<String> options;
  final int correctIndex;
  final String explanation;

  factory QuizQuestion.fromJson(Map<String, dynamic> json) {
    return QuizQuestion(
      question: json['question'] as String? ?? '',
      options: (json['options'] as List<dynamic>? ?? const [])
          .map((item) => item.toString())
          .toList(growable: false),
      correctIndex: (json['correct_index'] as num?)?.toInt() ?? 0,
      explanation: json['explanation'] as String? ?? '',
    );
  }
}

IconData _iconFromName(String? name) {
  switch ((name ?? '').toLowerCase()) {
    case 'science':
      return Icons.science_rounded;
    case 'menu_book':
      return Icons.menu_book_rounded;
    case 'calculate':
    default:
      return Icons.calculate_rounded;
  }
}

Color _colorFromHex(String? hex) {
  final normalized = (hex ?? '').replaceFirst('#', '');
  if (normalized.length == 6) {
    return Color(int.parse('FF$normalized', radix: 16));
  }
  return const Color(0xFF2563EB);
}

class TutorCatalog {
  static const List<TutorSubject> subjects = [
    TutorSubject(
      id: 'math',
      title: 'Mathematics',
      icon: Icons.calculate_rounded,
      color: Color(0xFF2563EB),
      description: 'Step-by-step problem solving and practice.',
      topics: [
        TutorTopic(
          id: 'linear_equations',
          subjectId: 'math',
          title: 'Linear Equations',
          subtitle: 'Solving one-variable equations',
          progress: 0.65,
          guidedProblem: GuidedProblem(
            prompt: 'Solve: 2x + 5 = 15',
            coachIntro: 'Let\'s isolate x one step at a time.',
            expectedNextStep: 'Subtract 5 from both sides',
            steps: [
              GuidedStep(
                title: 'Step 1',
                explanation:
                    'Subtract 5 from both sides to isolate the term with x.',
                hint: 'What operation undoes +5?',
              ),
              GuidedStep(
                title: 'Step 2',
                explanation: 'Now divide both sides by 2 to solve for x.',
                hint: 'Once you have 2x = 10, what should you do next?',
              ),
              GuidedStep(
                title: 'Step 3',
                explanation:
                    'Check your answer by substituting x back into the equation.',
                hint: 'Does 2(5) + 5 equal 15?',
              ),
            ],
          ),
          quizQuestions: [
            QuizQuestion(
              question:
                  'Which equation is equivalent to 3(x - 2) + 5 = 2x + 11?',
              options: [
                'x + 1 = 2x + 11',
                '3x - 1 = 2x + 11',
                '3x - 6 + 5 = 2x + 11',
                '3x + 5 = 2x + 11',
              ],
              correctIndex: 2,
              explanation:
                  'Distribute 3 to both x and -2 first, then combine constants.',
            ),
            QuizQuestion(
              question: 'Solve 5x + 3 = 18.',
              options: ['x = 3', 'x = 4', 'x = 5', 'x = 15'],
              correctIndex: 0,
              explanation: 'Subtract 3 to get 5x = 15, then divide by 5.',
            ),
          ],
        ),
        TutorTopic(
          id: 'geometry',
          subjectId: 'math',
          title: 'Geometry',
          subtitle: 'Triangles, circles, and theorems',
          progress: 0.40,
          guidedProblem: GuidedProblem(
            prompt:
                'Find the area of a triangle with base 8 cm and height 5 cm.',
            coachIntro: 'Use the area formula for triangles.',
            expectedNextStep: 'Multiply the base and height',
            steps: [
              GuidedStep(
                title: 'Step 1',
                explanation: 'Recall the formula: Area = 1/2 × base × height.',
                hint: 'What values are base and height here?',
              ),
              GuidedStep(
                title: 'Step 2',
                explanation: 'Multiply 8 by 5 before taking half.',
                hint: 'What is 8 × 5?',
              ),
              GuidedStep(
                title: 'Step 3',
                explanation: 'Take half of the product to get the final area.',
                hint: 'Half of 40 is what?',
              ),
            ],
          ),
          quizQuestions: [
            QuizQuestion(
              question:
                  'What is the area of a triangle with base 10 and height 6?',
              options: ['16', '30', '60', '20'],
              correctIndex: 1,
              explanation: 'Area = 1/2 × 10 × 6 = 30.',
            ),
          ],
        ),
        TutorTopic(
          id: 'functions',
          subjectId: 'math',
          title: 'Functions',
          subtitle: 'Relations and mappings',
          progress: 0.25,
          guidedProblem: GuidedProblem(
            prompt: 'Evaluate f(x) = 2x + 1 when x = 4.',
            coachIntro: 'We only need substitution.',
            expectedNextStep: 'Replace x with 4',
            steps: [
              GuidedStep(
                title: 'Step 1',
                explanation: 'Substitute x = 4 into 2x + 1.',
                hint: 'What expression do you get after substitution?',
              ),
              GuidedStep(
                title: 'Step 2',
                explanation: 'Multiply 2 by 4.',
                hint: 'What is 2 × 4?',
              ),
              GuidedStep(
                title: 'Step 3',
                explanation: 'Add 1 to the result.',
                hint: 'What is 8 + 1?',
              ),
            ],
          ),
          quizQuestions: [
            QuizQuestion(
              question: 'If f(x) = x + 7, what is f(3)?',
              options: ['4', '7', '10', '21'],
              correctIndex: 2,
              explanation: 'Replace x with 3: 3 + 7 = 10.',
            ),
          ],
        ),
        TutorTopic(
          id: 'trigonometry',
          subjectId: 'math',
          title: 'Trigonometry',
          subtitle: 'Angles and trigonometric ratios',
          progress: 0.10,
          guidedProblem: GuidedProblem(
            prompt:
                'In a right triangle, if opposite = 3 and hypotenuse = 5, find sin θ.',
            coachIntro: 'Use the sine ratio.',
            expectedNextStep: 'Write opposite / hypotenuse',
            steps: [
              GuidedStep(
                title: 'Step 1',
                explanation: 'Recall sin θ = opposite / hypotenuse.',
                hint: 'Which two sides do you need?',
              ),
              GuidedStep(
                title: 'Step 2',
                explanation: 'Substitute the values 3 and 5.',
                hint: 'What fraction do you get?',
              ),
            ],
          ),
          quizQuestions: [
            QuizQuestion(
              question: 'sin θ equals which ratio in a right triangle?',
              options: [
                'adjacent / hypotenuse',
                'opposite / adjacent',
                'opposite / hypotenuse',
                'hypotenuse / opposite',
              ],
              correctIndex: 2,
              explanation:
                  'Sine compares the opposite side with the hypotenuse.',
            ),
          ],
        ),
      ],
    ),
    TutorSubject(
      id: 'physics',
      title: 'Physics',
      icon: Icons.science_rounded,
      color: Color(0xFF0F766E),
      description: 'Conceptual explanations with applied problem solving.',
      topics: [
        TutorTopic(
          id: 'motion',
          subjectId: 'physics',
          title: 'Motion',
          subtitle: 'Distance, speed, and time',
          progress: 0.52,
          guidedProblem: GuidedProblem(
            prompt: 'A car travels 120 km in 2 hours. Find its speed.',
            coachIntro: 'Use the speed formula.',
            expectedNextStep: 'Divide distance by time',
            steps: [
              GuidedStep(
                title: 'Step 1',
                explanation: 'Recall speed = distance ÷ time.',
                hint: 'What is the distance? What is the time?',
              ),
              GuidedStep(
                title: 'Step 2',
                explanation: 'Divide 120 by 2 to get the speed.',
                hint: 'What is 120 ÷ 2?',
              ),
            ],
          ),
          quizQuestions: [
            QuizQuestion(
              question: 'If distance is 150 m and time is 10 s, what is speed?',
              options: ['15 m/s', '1500 m/s', '140 m/s', '16 m/s'],
              correctIndex: 0,
              explanation: 'Speed = 150 ÷ 10 = 15 m/s.',
            ),
          ],
        ),
        TutorTopic(
          id: 'forces',
          subjectId: 'physics',
          title: 'Forces',
          subtitle: 'Newton\'s laws and net force',
          progress: 0.33,
          guidedProblem: GuidedProblem(
            prompt: 'A 2 kg object accelerates at 3 m/s². Find the force.',
            coachIntro: 'This is a direct F = ma problem.',
            expectedNextStep: 'Multiply mass by acceleration',
            steps: [
              GuidedStep(
                title: 'Step 1',
                explanation: 'Use Newton\'s second law: F = m × a.',
                hint: 'Which values represent mass and acceleration?',
              ),
              GuidedStep(
                title: 'Step 2',
                explanation: 'Multiply 2 by 3 to get force in newtons.',
                hint: 'What is 2 × 3?',
              ),
            ],
          ),
          quizQuestions: [
            QuizQuestion(
              question:
                  'What is the net force on a 4 kg object accelerating at 2 m/s²?',
              options: ['2 N', '6 N', '8 N', '12 N'],
              correctIndex: 2,
              explanation: 'F = ma = 4 × 2 = 8 N.',
            ),
          ],
        ),
        TutorTopic(
          id: 'energy',
          subjectId: 'physics',
          title: 'Energy',
          subtitle: 'Work, power, and conservation',
          progress: 0.21,
          guidedProblem: GuidedProblem(
            prompt: 'If work done is 60 J in 3 seconds, find power.',
            coachIntro: 'Power tells us how quickly work is done.',
            expectedNextStep: 'Divide work by time',
            steps: [
              GuidedStep(
                title: 'Step 1',
                explanation: 'Use P = W ÷ t.',
                hint: 'What two values are given?',
              ),
              GuidedStep(
                title: 'Step 2',
                explanation: 'Compute 60 ÷ 3.',
                hint: 'What is the result in watts?',
              ),
            ],
          ),
          quizQuestions: [
            QuizQuestion(
              question: 'Power is defined as:',
              options: [
                'force × distance',
                'work ÷ time',
                'mass × acceleration',
                'distance ÷ speed',
              ],
              correctIndex: 1,
              explanation: 'Power measures the rate of doing work.',
            ),
          ],
        ),
        TutorTopic(
          id: 'waves',
          subjectId: 'physics',
          title: 'Waves',
          subtitle: 'Frequency, wavelength, and sound',
          progress: 0.14,
          guidedProblem: GuidedProblem(
            prompt:
                'A wave has speed 20 m/s and frequency 4 Hz. Find wavelength.',
            coachIntro: 'Use the wave equation.',
            expectedNextStep: 'Rearrange v = fλ to λ = v/f',
            steps: [
              GuidedStep(
                title: 'Step 1',
                explanation: 'Start from v = fλ and solve for λ.',
                hint: 'How do you isolate λ?',
              ),
              GuidedStep(
                title: 'Step 2',
                explanation: 'Divide 20 by 4 to find the wavelength.',
                hint: 'What is 20 ÷ 4?',
              ),
            ],
          ),
          quizQuestions: [
            QuizQuestion(
              question: 'If v = 30 m/s and f = 5 Hz, then λ = ?',
              options: ['6 m', '25 m', '35 m', '150 m'],
              correctIndex: 0,
              explanation: 'λ = v/f = 30/5 = 6 m.',
            ),
          ],
        ),
      ],
    ),
    TutorSubject(
      id: 'english',
      title: 'English',
      icon: Icons.menu_book_rounded,
      color: Color(0xFF0891B2),
      description: 'Grammar, vocabulary, reading, and writing practice.',
      topics: [
        TutorTopic(
          id: 'grammar',
          subjectId: 'english',
          title: 'Grammar',
          subtitle: 'Sentence structure and accuracy',
          progress: 0.58,
          guidedProblem: GuidedProblem(
            prompt: 'Correct this sentence: "She go to school every day."',
            coachIntro: 'Think about subject-verb agreement.',
            expectedNextStep: 'Change "go" to "goes"',
            steps: [
              GuidedStep(
                title: 'Step 1',
                explanation:
                    'The subject "She" takes a singular verb in present simple.',
                hint: 'What verb form matches "she"?',
              ),
              GuidedStep(
                title: 'Step 2',
                explanation: 'Rewrite the sentence with the corrected verb.',
                hint: 'Read it aloud and check if it sounds natural.',
              ),
            ],
          ),
          quizQuestions: [
            QuizQuestion(
              question: 'Choose the correct sentence.',
              options: [
                'He go to work at 8.',
                'He goes to work at 8.',
                'He going to work at 8.',
                'He gone to work at 8.',
              ],
              correctIndex: 1,
              explanation: 'Third-person singular uses goes in present simple.',
            ),
          ],
        ),
        TutorTopic(
          id: 'vocabulary',
          subjectId: 'english',
          title: 'Vocabulary',
          subtitle: 'Word meaning and usage',
          progress: 0.42,
          guidedProblem: GuidedProblem(
            prompt: 'Use the word "curious" in a sentence.',
            coachIntro: 'Show the meaning through context.',
            expectedNextStep:
                'Write a sentence that shows interest or wanting to know',
            steps: [
              GuidedStep(
                title: 'Step 1',
                explanation:
                    'Curious describes someone who wants to know more.',
                hint: 'Think of a student asking many questions.',
              ),
              GuidedStep(
                title: 'Step 2',
                explanation:
                    'Write a complete sentence using the word naturally.',
                hint: 'Start with "The student was curious..."',
              ),
            ],
          ),
          quizQuestions: [
            QuizQuestion(
              question: 'Which word is closest in meaning to "curious"?',
              options: ['bored', 'interested', 'angry', 'silent'],
              correctIndex: 1,
              explanation: 'Curious means interested and eager to learn.',
            ),
          ],
        ),
        TutorTopic(
          id: 'reading',
          subjectId: 'english',
          title: 'Reading',
          subtitle: 'Comprehension and inference',
          progress: 0.36,
          guidedProblem: GuidedProblem(
            prompt: 'Read a paragraph and identify the main idea.',
            coachIntro: 'Focus on what the whole paragraph is mostly about.',
            expectedNextStep: 'Summarize the central message in one sentence',
            steps: [
              GuidedStep(
                title: 'Step 1',
                explanation: 'Look for repeated ideas or details.',
                hint: 'What point connects most of the sentences?',
              ),
              GuidedStep(
                title: 'Step 2',
                explanation:
                    'State the main idea without copying every detail.',
                hint: 'Keep your answer broad but accurate.',
              ),
            ],
          ),
          quizQuestions: [
            QuizQuestion(
              question: 'The main idea of a paragraph is:',
              options: [
                'a random detail',
                'the central message',
                'the first word',
                'the punctuation',
              ],
              correctIndex: 1,
              explanation:
                  'The main idea captures what the paragraph is mostly about.',
            ),
          ],
        ),
        TutorTopic(
          id: 'writing',
          subjectId: 'english',
          title: 'Writing',
          subtitle: 'Paragraph building and clarity',
          progress: 0.29,
          guidedProblem: GuidedProblem(
            prompt: 'Write a topic sentence about healthy habits.',
            coachIntro: 'A topic sentence introduces the paragraph clearly.',
            expectedNextStep: 'Write one clear sentence that previews the idea',
            steps: [
              GuidedStep(
                title: 'Step 1',
                explanation:
                    'Choose the main point you want the paragraph to discuss.',
                hint: 'Think about sleep, food, or exercise.',
              ),
              GuidedStep(
                title: 'Step 2',
                explanation:
                    'Write a clear sentence that introduces that point.',
                hint:
                    'Example frame: "Healthy habits are important because..."',
              ),
            ],
          ),
          quizQuestions: [
            QuizQuestion(
              question: 'What does a topic sentence do?',
              options: [
                'ends a paragraph',
                'introduces the main idea',
                'adds punctuation',
                'lists every detail',
              ],
              correctIndex: 1,
              explanation:
                  'A topic sentence presents the paragraph\'s main focus.',
            ),
          ],
        ),
      ],
    ),
  ];

  static TutorSubject byId(String id) =>
      subjects.firstWhere((subject) => subject.id == id);

  static TutorTopic topicByIds(String subjectId, String topicId) =>
      byId(subjectId).topics.firstWhere((topic) => topic.id == topicId);
}
