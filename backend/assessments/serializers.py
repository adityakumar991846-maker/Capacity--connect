"""
Serializers for the assessments module.

Enforces strict anti-cheat data sanitization:
- Active quiz taking endpoints NEVER expose correct_answer or explanation.
- Grading is calculated and serialized securely upon submission.
"""

from rest_framework import serializers
from .models import (
    Assessment,
    AssessmentAnswer,
    AssessmentAttempt,
    AssessmentStatus,
    Question,
    QuestionOptionChoice,
)


class QuestionTrainerSerializer(serializers.ModelSerializer):
    """Full question serializer for trainers including answers and explanations."""

    class Meta:
        model = Question
        fields = [
            'id',
            'assessment',
            'question_text',
            'option_a',
            'option_b',
            'option_c',
            'option_d',
            'correct_answer',
            'explanation',
            'marks',
            'order',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'assessment', 'created_at', 'updated_at']

    def validate_marks(self, value):
        if value <= 0:
            raise serializers.ValidationError('Marks must be greater than 0.')
        return value

    def validate_order(self, value):
        if value <= 0:
            raise serializers.ValidationError('Order must be greater than 0.')
        return value


class QuestionTraineeTakeSerializer(serializers.ModelSerializer):
    """
    Sanitized question serializer for trainees taking a quiz.
    STRICTLY omits correct_answer and explanation.
    """

    class Meta:
        model = Question
        fields = [
            'id',
            'question_text',
            'option_a',
            'option_b',
            'option_c',
            'option_d',
            'marks',
            'order',
        ]


class AssessmentTrainerDetailSerializer(serializers.ModelSerializer):
    """Detailed view for trainers including all questions with answers."""
    questions = QuestionTrainerSerializer(many=True, read_only=True)
    total_marks = serializers.IntegerField(read_only=True)
    question_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Assessment
        fields = [
            'id',
            'course',
            'subject',
            'title',
            'description',
            'passing_percentage',
            'duration_minutes',
            'status',
            'total_marks',
            'question_count',
            'questions',
            'created_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class AssessmentTrainerListSerializer(serializers.ModelSerializer):
    """Compact summary of an assessment for trainer dashboard."""
    total_marks = serializers.IntegerField(read_only=True)
    question_count = serializers.IntegerField(read_only=True)
    attempt_count = serializers.SerializerMethodField()
    pass_count = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = [
            'id',
            'course',
            'subject',
            'title',
            'description',
            'passing_percentage',
            'duration_minutes',
            'status',
            'total_marks',
            'question_count',
            'attempt_count',
            'pass_count',
            'created_at',
            'updated_at',
        ]

    def get_attempt_count(self, obj):
        return obj.attempts.count()

    def get_pass_count(self, obj):
        return obj.attempts.filter(passed=True).count()


class AssessmentCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating assessments."""

    class Meta:
        model = Assessment
        fields = [
            'id',
            'course',
            'subject',
            'title',
            'description',
            'passing_percentage',
            'duration_minutes',
            'status',
        ]
        read_only_fields = ['id', 'course']

    def validate_passing_percentage(self, value):
        if not (1 <= value <= 100):
            raise serializers.ValidationError('Passing percentage must be between 1 and 100.')
        return value

    def validate_duration_minutes(self, value):
        if value <= 0:
            raise serializers.ValidationError('Duration in minutes must be greater than 0.')
        return value

    def validate(self, attrs):
        course = (
            attrs.get('course')
            or (self.instance.course if self.instance else None)
            or self.context.get('course')
        )
        subject = attrs.get('subject') or (self.instance.subject if self.instance else None)

        if subject and course and subject.course_id != course.id:
            raise serializers.ValidationError({'subject': 'Selected subject does not belong to this course.'})

        return attrs


class AssessmentTraineeTakeSerializer(serializers.ModelSerializer):
    """Sanitized assessment serializer for an active quiz attempt."""
    questions = QuestionTraineeTakeSerializer(many=True, read_only=True)
    total_marks = serializers.IntegerField(read_only=True)
    question_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Assessment
        fields = [
            'id',
            'course',
            'subject',
            'title',
            'description',
            'passing_percentage',
            'duration_minutes',
            'total_marks',
            'question_count',
            'questions',
        ]


class AssessmentTraineeListSerializer(serializers.ModelSerializer):
    """List of available assessments for enrolled trainees with user's best score."""
    total_marks = serializers.IntegerField(read_only=True)
    question_count = serializers.IntegerField(read_only=True)
    has_attempted = serializers.SerializerMethodField()
    best_score = serializers.SerializerMethodField()
    best_percentage = serializers.SerializerMethodField()
    passed = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = [
            'id',
            'course',
            'subject',
            'title',
            'description',
            'passing_percentage',
            'duration_minutes',
            'total_marks',
            'question_count',
            'has_attempted',
            'best_score',
            'best_percentage',
            'passed',
        ]

    def _get_user_attempts(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return []
        if not hasattr(obj, '_cached_user_attempts'):
            obj._cached_user_attempts = list(obj.attempts.filter(trainee=request.user))
        return obj._cached_user_attempts

    def get_has_attempted(self, obj):
        return len(self._get_user_attempts(obj)) > 0

    def get_best_score(self, obj):
        attempts = self._get_user_attempts(obj)
        return max((a.score for a in attempts), default=0)

    def get_best_percentage(self, obj):
        attempts = self._get_user_attempts(obj)
        return max((a.percentage for a in attempts), default=0.0)

    def get_passed(self, obj):
        attempts = self._get_user_attempts(obj)
        return any(a.passed for a in attempts)


class SubmitAnswerItemSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    selected_option = serializers.ChoiceField(
        choices=QuestionOptionChoice.choices,
        allow_null=True,
        required=False,
    )


class AssessmentSubmitSerializer(serializers.Serializer):
    answers = SubmitAnswerItemSerializer(many=True, required=True)


class AssessmentAnswerDetailSerializer(serializers.ModelSerializer):
    """Detailed answer record revealed only after submission."""
    question_text = serializers.CharField(source='question.question_text', read_only=True)
    option_a = serializers.CharField(source='question.option_a', read_only=True)
    option_b = serializers.CharField(source='question.option_b', read_only=True)
    option_c = serializers.CharField(source='question.option_c', read_only=True)
    option_d = serializers.CharField(source='question.option_d', read_only=True)
    correct_answer = serializers.CharField(source='question.correct_answer', read_only=True)
    explanation = serializers.CharField(source='question.explanation', read_only=True)
    max_marks = serializers.IntegerField(source='question.marks', read_only=True)
    order = serializers.IntegerField(source='question.order', read_only=True)

    class Meta:
        model = AssessmentAnswer
        fields = [
            'id',
            'question_id',
            'order',
            'question_text',
            'option_a',
            'option_b',
            'option_c',
            'option_d',
            'selected_option',
            'correct_answer',
            'explanation',
            'is_correct',
            'marks_obtained',
            'max_marks',
        ]


class AssessmentAttemptDetailSerializer(serializers.ModelSerializer):
    """Complete attempt review with detailed answers and scores."""
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)
    passing_percentage = serializers.IntegerField(source='assessment.passing_percentage', read_only=True)
    answers = AssessmentAnswerDetailSerializer(many=True, read_only=True)

    class Meta:
        model = AssessmentAttempt
        fields = [
            'id',
            'assessment_id',
            'assessment_title',
            'passing_percentage',
            'score',
            'total_marks',
            'percentage',
            'passed',
            'started_at',
            'submitted_at',
            'answers',
        ]


class AssessmentAttemptRosterSerializer(serializers.ModelSerializer):
    """Roster item for trainer viewing student attempts."""
    trainee_id = serializers.IntegerField(source='trainee.id', read_only=True)
    trainee_username = serializers.CharField(source='trainee.username', read_only=True)
    trainee_email = serializers.EmailField(source='trainee.email', read_only=True)

    class Meta:
        model = AssessmentAttempt
        fields = [
            'id',
            'trainee_id',
            'trainee_username',
            'trainee_email',
            'score',
            'total_marks',
            'percentage',
            'passed',
            'started_at',
            'submitted_at',
        ]


class AdminAssessmentListSerializer(serializers.ModelSerializer):
    """Platform-wide assessment overview for Admin governance."""
    course_id = serializers.IntegerField(source='course.id', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    trainer_username = serializers.CharField(source='created_by.username', read_only=True)
    subject_title = serializers.CharField(source='subject.title', read_only=True, default=None)
    questions_count = serializers.SerializerMethodField()
    attempts_count = serializers.SerializerMethodField()
    pass_count = serializers.SerializerMethodField()
    pass_rate = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = [
            'id',
            'title',
            'course_id',
            'course_title',
            'subject_title',
            'trainer_username',
            'status',
            'duration_minutes',
            'passing_percentage',
            'questions_count',
            'attempts_count',
            'pass_count',
            'pass_rate',
            'created_at',
            'updated_at',
        ]

    def get_questions_count(self, obj):
        return obj.questions.count()

    def get_attempts_count(self, obj):
        return obj.attempts.count()

    def get_pass_count(self, obj):
        return obj.attempts.filter(passed=True).count()

    def get_pass_rate(self, obj):
        total = obj.attempts.count()
        if total == 0:
            return 0.0
        passed = obj.attempts.filter(passed=True).count()
        return round((passed / total) * 100, 1)
