from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import translation
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api import (
    get_requested_language,
    get_telegram_user,
    user_blocked_response,
    user_not_found_response,
    validation_error_response,
)
from core.constants import API_PAYMENT_REQUIRED, API_ROUND_COMPLETE

from tests.exceptions import PaymentRequired, QuizCompleted
from tests.quiz_services import get_quiz_progress


class TelegramUserMixin:
    def resolve_user(self, telegram_id):
        user = get_telegram_user(telegram_id)
        if not user:
            return None, user_not_found_response()
        return user, None

    def blocked_guard(self, user):
        if user.is_blocked:
            return user_blocked_response()
        return None


class QuizAPIView(TelegramUserMixin, APIView):
    def payment_required_response(self, user, exc):
        return Response(
            {
                "detail": str(exc),
                "code": API_PAYMENT_REQUIRED,
                "progress": get_quiz_progress(user),
            },
            status=status.HTTP_402_PAYMENT_REQUIRED,
        )

    def round_complete_response(self, user):
        return Response(
            {
                "code": API_ROUND_COMPLETE,
                "progress": get_quiz_progress(user),
            },
            status=200,
        )

    def handle_quiz_errors(self, user, exc):
        if isinstance(exc, PaymentRequired):
            return self.payment_required_response(user, exc)
        if isinstance(exc, QuizCompleted):
            return self.round_complete_response(user)
        if isinstance(exc, PermissionDenied):
            return Response({"detail": str(exc)}, status=403)
        if isinstance(exc, ValidationError):
            return validation_error_response(exc)
        if isinstance(exc, LookupError):
            return Response({"detail": str(exc)}, status=404)
        raise exc

    def with_user_language(self, request, user, callback):
        with translation.override(get_requested_language(request, user)):
            return callback()
