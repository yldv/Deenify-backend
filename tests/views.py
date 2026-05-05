from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import translation
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import TelegramUser

from .models import TestCategory, UserTestSession
from .serializers import (
    FinishSessionSerializer,
    StartSessionSerializer,
    SubmitAnswerSerializer,
    TestCategorySerializer,
    TestQuestionSerializer,
)
from .services import (
    PaymentRequired,
    finish_session,
    get_session_stats,
    start_test_session,
    submit_session_answer,
)


def get_requested_language(request, user=None):
    if user and user.language in {"uz", "ru", "en"}:
        return user.language
    language = request.headers.get("Accept-Language", "uz").split(",", 1)[0].split("-", 1)[0]
    return language if language in {"uz", "ru", "en"} else "uz"


def get_user_or_404(telegram_id):
    return TelegramUser.objects.filter(telegram_id=telegram_id).first()


def validation_response(exc):
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class TestCategoryListView(APIView):
    def get(self, request):
        queryset = TestCategory.objects.filter(is_active=True).order_by("sort_order", "name")
        with translation.override(get_requested_language(request)):
            data = TestCategorySerializer(queryset, many=True).data
        return Response(data, status=status.HTTP_200_OK)


class StartTestSessionView(APIView):
    def post(self, request):
        serializer = StartSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = get_user_or_404(serializer.validated_data["telegram_id"])
        if not user:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        if user.is_blocked:
            return Response({"detail": "User is blocked."}, status=status.HTTP_403_FORBIDDEN)

        try:
            session, questions = start_test_session(
                user=user,
                test_type=serializer.validated_data["test_type"],
            )
        except PaymentRequired as exc:
            return Response(
                {"detail": str(exc), "code": "payment_required"},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        except ValidationError as exc:
            return validation_response(exc)

        with translation.override(get_requested_language(request, user)):
            question_data = TestQuestionSerializer(questions, many=True).data
        return Response(
            {
                "session_id": session.id,
                "test_type": serializer.validated_data["test_type"],
                "total_questions": len(questions),
                "questions": question_data,
            },
            status=status.HTTP_201_CREATED,
        )


class SubmitAnswerView(APIView):
    def post(self, request, session_id):
        serializer = SubmitAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = get_user_or_404(serializer.validated_data["telegram_id"])
        if not user:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        session = (
            UserTestSession.objects.filter(id=session_id)
            .select_related("user")
            .prefetch_related("tests", "user_answers")
            .first()
        )
        if not session:
            return Response({"detail": "Session not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            user_answer, correct_answer, updated_session = submit_session_answer(
                session=session,
                user=user,
                test_id=serializer.validated_data["test_id"],
                answer_id=serializer.validated_data["answer_id"],
            )
        except PaymentRequired as exc:
            return Response(
                {"detail": str(exc), "code": "payment_required"},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LookupError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as exc:
            return validation_response(exc)

        with translation.override(get_requested_language(request, user)):
            explanation = user_answer.test.explanation
        return Response(
            {
                "is_correct": user_answer.is_correct,
                "correct_answer_id": correct_answer.id if correct_answer else None,
                "explanation": explanation,
                "session": get_session_stats(updated_session),
            },
            status=status.HTTP_200_OK,
        )


class FinishSessionView(APIView):
    def post(self, request, session_id):
        serializer = FinishSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = get_user_or_404(serializer.validated_data["telegram_id"])
        if not user:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        session = UserTestSession.objects.filter(id=session_id).select_related("user").first()
        if not session:
            return Response({"detail": "Session not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            session = finish_session(session=session, user=user)
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        return Response(
            {
                "session_id": session.id,
                "correct_answers": session.correct_answers,
                "wrong_answers": session.wrong_answers,
                "total_questions": session.total_questions,
                "score_percent": session.score_percent,
            },
            status=status.HTTP_200_OK,
        )
