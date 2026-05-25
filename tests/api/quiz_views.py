from django.core.exceptions import PermissionDenied, ValidationError

from rest_framework import status
from rest_framework.response import Response

from tests.exceptions import PaymentRequired, QuizCompleted
from tests.quiz_services import (
    get_next_question,
    get_quiz_progress,
    reset_quiz_progress,
    start_new_quiz_round,
    submit_quiz_answer,
)
from tests.serializers import (
    BotQuizQuestionSerializer,
    QuizAnswerSerializer,
    QuizRestartSerializer,
    QuizTelegramIdSerializer,
)

from .base import QuizAPIView


class QuizProgressView(QuizAPIView):
    def get(self, request):
        serializer = QuizTelegramIdSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        user, error = self.resolve_user(serializer.validated_data["telegram_id"])
        if error:
            return error
        return Response(get_quiz_progress(user), status=status.HTTP_200_OK)


class QuizNextQuestionView(QuizAPIView):
    def get(self, request):
        serializer = QuizTelegramIdSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        user, error = self.resolve_user(serializer.validated_data["telegram_id"])
        if error:
            return error
        blocked = self.blocked_guard(user)
        if blocked:
            return blocked

        try:
            question = get_next_question(user)
        except (PaymentRequired, QuizCompleted, PermissionDenied) as exc:
            return self.handle_quiz_errors(user, exc)

        def build_payload():
            data = BotQuizQuestionSerializer(question).data
            return {
                "question": data,
                "progress": get_quiz_progress(user),
            }

        return Response(
            self.with_user_language(request, user, build_payload),
            status=status.HTTP_200_OK,
        )


class QuizAnswerView(QuizAPIView):
    def post(self, request):
        serializer = QuizAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, error = self.resolve_user(serializer.validated_data["telegram_id"])
        if error:
            return error
        blocked = self.blocked_guard(user)
        if blocked:
            return blocked

        try:
            result = submit_quiz_answer(
                user=user,
                test_id=serializer.validated_data["test_id"],
                answer_id=serializer.validated_data["answer_id"],
            )
        except (PaymentRequired, PermissionDenied, ValidationError, LookupError) as exc:
            return self.handle_quiz_errors(user, exc)

        def build_payload():
            result["explanation"] = result.get("explanation") or ""
            return result

        return Response(
            self.with_user_language(request, user, build_payload),
            status=status.HTTP_200_OK,
        )


class QuizRestartView(QuizAPIView):
    def post(self, request):
        serializer = QuizRestartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, error = self.resolve_user(serializer.validated_data["telegram_id"])
        if error:
            return error

        try:
            progress = start_new_quiz_round(user)
        except ValidationError as exc:
            return self.handle_quiz_errors(user, exc)

        return Response(progress, status=status.HTTP_200_OK)


class QuizResetView(QuizAPIView):
    def post(self, request):
        serializer = QuizRestartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, error = self.resolve_user(serializer.validated_data["telegram_id"])
        if error:
            return error
        blocked = self.blocked_guard(user)
        if blocked:
            return blocked

        return Response(reset_quiz_progress(user), status=status.HTTP_200_OK)
