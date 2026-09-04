"""
Views for Course Reviews (Step 14).
"""

from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.models import Course, CourseStatus
from .models import CourseReview
from .permissions import IsEnrolledTrainee, IsReviewOwnerOrAdmin, IsAdmin, IsTrainer
from .serializers import (
    CourseReviewListSerializer,
    CourseReviewCreateUpdateSerializer,
    TrainerFeedbackItemSerializer,
)


class CourseReviewListCreateView(APIView):
    """
    List visible reviews and rating distribution or create/update review.
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsEnrolledTrainee()]
        return [AllowAny()]

    def get(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id)
        reviews_qs = CourseReview.objects.filter(course=course, is_visible=True).select_related('trainee')

        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        ratings_counts = (
            reviews_qs.values('rating')
            .annotate(count=Count('rating'))
            .order_by('rating')
        )
        for entry in ratings_counts:
            r = entry['rating']
            if r in distribution:
                distribution[r] = entry['count']

        serializer = CourseReviewListSerializer(reviews_qs, many=True)

        return Response({
            'course_id': course.id,
            'average_rating': float(course.average_rating),
            'review_count': course.review_count,
            'rating_distribution': distribution,
            'reviews': serializer.data,
        })

    def post(self, request, course_id):
        course = get_object_or_404(Course, pk=course_id)

        if course.trainer == request.user:
            return Response(
                {'detail': 'Trainers cannot review their own course.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CourseReviewCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        review, created = CourseReview.objects.update_or_create(
            course=course,
            trainee=request.user,
            defaults={
                'rating': serializer.validated_data['rating'],
                'title': serializer.validated_data.get('title', ''),
                'comment': serializer.validated_data['comment'],
                'is_visible': True,
            }
        )

        course.update_rating_stats()

        out_serializer = CourseReviewListSerializer(review)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(out_serializer.data, status=status_code)


class CourseMyReviewView(APIView):
    """
    Fetch trainee own review for course.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        review = CourseReview.objects.filter(
            course_id=course_id,
            trainee=request.user
        ).first()

        if not review:
            return Response(None, status=status.HTTP_200_OK)

        return Response(CourseReviewListSerializer(review).data)


class CourseReviewDetailView(APIView):
    """
    Delete review (Owner or Admin).
    """
    permission_classes = [IsAuthenticated, IsReviewOwnerOrAdmin]

    def delete(self, request, pk):
        review = get_object_or_404(CourseReview, pk=pk)
        self.check_object_permissions(request, review)
        course = review.course
        review.delete()
        course.update_rating_stats()
        return Response({'detail': 'Review deleted successfully.'}, status=status.HTTP_200_OK)


class CourseReviewModerateView(APIView):
    """
    Toggle visibility flag (Admin only).
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        review = get_object_or_404(CourseReview, pk=pk)
        review.is_visible = not review.is_visible
        review.save(update_fields=['is_visible', 'updated_at'])
        review.course.update_rating_stats()
        return Response({
            'detail': f'Review visibility set to {review.is_visible}.',
            'is_visible': review.is_visible,
        })


class TrainerFeedbackListView(APIView):
    """
    All reviews across authenticated trainer courses.
    """
    permission_classes = [IsAuthenticated, IsTrainer]

    def get(self, request):
        trainer_courses = Course.objects.filter(trainer=request.user)
        reviews = CourseReview.objects.filter(
            course__in=trainer_courses,
            is_visible=True
        ).select_related('trainee', 'course').order_by('-created_at')

        avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0.0

        serializer = TrainerFeedbackItemSerializer(reviews, many=True)
        return Response({
            'trainer_average_rating': round(float(avg_rating), 2),
            'total_reviews': reviews.count(),
            'reviews': serializer.data,
        })
