"""
Serializers for assignments, project submissions, and grading reviews.
"""

from rest_framework import serializers
from courses.models import Course, Subject
from .models import (
    Assignment,
    AssignmentSubmission,
    SubmissionReview,
    SubmissionType,
    SubmissionStatus,
)


class SubmissionReviewSerializer(serializers.ModelSerializer):
    reviewer_username = serializers.CharField(source='reviewer.username', read_only=True)

    class Meta:
        model = SubmissionReview
        fields = [
            'id',
            'reviewer',
            'reviewer_username',
            'score',
            'passed',
            'feedback',
            'reviewed_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'reviewer', 'reviewed_at', 'updated_at']


class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    assignment_title = serializers.CharField(source='assignment.title', read_only=True)
    max_score = serializers.IntegerField(source='assignment.max_score', read_only=True)
    passing_score = serializers.IntegerField(source='assignment.passing_score', read_only=True)
    trainee_username = serializers.CharField(source='trainee.username', read_only=True)
    trainee_email = serializers.EmailField(source='trainee.email', read_only=True)
    review = SubmissionReviewSerializer(read_only=True)

    class Meta:
        model = AssignmentSubmission
        fields = [
            'id',
            'assignment',
            'assignment_title',
            'max_score',
            'passing_score',
            'trainee',
            'trainee_username',
            'trainee_email',
            'submission_link',
            'submission_text',
            'submission_file',
            'status',
            'review',
            'submitted_at',
            'created_at',
        ]
        read_only_fields = ['id', 'assignment', 'trainee', 'status', 'submitted_at', 'created_at']


class AssignmentSubmissionCreateSerializer(serializers.ModelSerializer):
    submission_link = serializers.URLField(required=False, allow_blank=True, default='')
    submission_text = serializers.CharField(required=False, allow_blank=True, default='')
    status = serializers.ChoiceField(
        choices=[SubmissionStatus.DRAFT, SubmissionStatus.SUBMITTED],
        default=SubmissionStatus.SUBMITTED,
    )

    class Meta:
        model = AssignmentSubmission
        fields = ['submission_link', 'submission_text', 'submission_file', 'status']

    def validate(self, data):
        assignment = self.context.get('assignment')
        status_val = data.get('status', SubmissionStatus.SUBMITTED)

        # Drafts can be partial, but submitted deliverables must satisfy assignment submission_type
        if status_val == SubmissionStatus.SUBMITTED and assignment:
            sub_type = assignment.submission_type
            link = data.get('submission_link', '').strip()
            text = data.get('submission_text', '').strip()
            has_file = bool(data.get('submission_file'))

            if sub_type == SubmissionType.LINK and not link:
                raise serializers.ValidationError(
                    {"submission_link": "A valid external project/repository URL is required for this assignment."}
                )
            elif sub_type == SubmissionType.TEXT and not text:
                raise serializers.ValidationError(
                    {"submission_text": "Written code or response text is required for this assignment."}
                )
            elif sub_type == SubmissionType.FILE and not has_file:
                raise serializers.ValidationError(
                    {"submission_file": "A file attachment is required for this assignment."}
                )
            elif sub_type == SubmissionType.HYBRID and not (link and text):
                raise serializers.ValidationError(
                    {"non_field_errors": ["Both a project link and written analysis text are required."]}
                )

        return data


class AssignmentListSerializer(serializers.ModelSerializer):
    subject_title = serializers.CharField(source='subject.title', read_only=True, allow_null=True)
    my_submission = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            'id',
            'course',
            'subject',
            'subject_title',
            'title',
            'description',
            'submission_type',
            'max_score',
            'passing_score',
            'due_date',
            'is_mandatory',
            'is_published',
            'my_submission',
            'created_at',
            'updated_at',
        ]

    def get_my_submission(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        submission = obj.submissions.filter(trainee=request.user).select_related('review').first()
        if not submission:
            return None

        review_data = None
        if hasattr(submission, 'review') and submission.review:
            review_data = {
                'score': submission.review.score,
                'passed': submission.review.passed,
                'feedback': submission.review.feedback,
                'reviewed_at': submission.review.reviewed_at,
            }

        return {
            'id': submission.id,
            'status': submission.status,
            'submitted_at': submission.submitted_at,
            'review': review_data,
        }


class AssignmentDetailSerializer(AssignmentListSerializer):
    submissions_count = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = AssignmentListSerializer.Meta.fields + ['submissions_count']

    def get_submissions_count(self, obj):
        request = self.context.get('request')
        if request and (obj.course.trainer == request.user or (hasattr(request.user, 'profile') and request.user.profile.role == 'ADMIN')):
            return obj.submissions.count()
        return None


class AssignmentCreateUpdateSerializer(serializers.ModelSerializer):
    subject_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Assignment
        fields = [
            'title',
            'description',
            'subject_id',
            'submission_type',
            'max_score',
            'passing_score',
            'due_date',
            'is_mandatory',
            'is_published',
        ]

    def validate(self, data):
        course = self.context.get('course')
        max_score = data.get('max_score', 100)
        passing_score = data.get('passing_score', 60)

        if max_score <= 0:
            raise serializers.ValidationError({"max_score": "Maximum score must be greater than 0."})

        if passing_score > max_score:
            raise serializers.ValidationError(
                {"passing_score": "Passing score cannot exceed maximum score."}
            )

        subject_id = data.get('subject_id')
        if subject_id:
            if not Subject.objects.filter(id=subject_id, course=course).exists():
                raise serializers.ValidationError(
                    {"subject_id": "The specified module does not belong to this course."}
                )

        return data


class SubmissionGradeSerializer(serializers.Serializer):
    score = serializers.IntegerField(min_value=0)
    feedback = serializers.CharField(min_length=5, trim_whitespace=True)
    request_resubmission = serializers.BooleanField(default=False)

    def validate_score(self, value):
        assignment = self.context.get('assignment')
        if assignment and value > assignment.max_score:
            raise serializers.ValidationError(
                f"Score cannot exceed the maximum score of {assignment.max_score}."
            )
        return value


class TrainerPendingReviewItemSerializer(serializers.ModelSerializer):
    assignment_title = serializers.CharField(source='assignment.title', read_only=True)
    assignment_id = serializers.IntegerField(source='assignment.id', read_only=True)
    course_id = serializers.IntegerField(source='assignment.course.id', read_only=True)
    course_title = serializers.CharField(source='assignment.course.title', read_only=True)
    subject_title = serializers.CharField(source='assignment.subject.title', read_only=True, allow_null=True)
    trainee_username = serializers.CharField(source='trainee.username', read_only=True)
    trainee_email = serializers.EmailField(source='trainee.email', read_only=True)
    max_score = serializers.IntegerField(source='assignment.max_score', read_only=True)
    passing_score = serializers.IntegerField(source='assignment.passing_score', read_only=True)

    class Meta:
        model = AssignmentSubmission
        fields = [
            'id',
            'assignment_id',
            'assignment_title',
            'course_id',
            'course_title',
            'subject_title',
            'trainee_username',
            'trainee_email',
            'submission_link',
            'submission_text',
            'status',
            'max_score',
            'passing_score',
            'submitted_at',
        ]
