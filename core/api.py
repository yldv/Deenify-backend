from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.response import Response

from core.constants import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from users.models import TelegramUser


def get_requested_language(request, user=None):
    if user:
        return user.get_content_language()
    language = request.headers.get("Accept-Language", DEFAULT_LANGUAGE).split(",", 1)[0].split("-", 1)[0]
    return language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def get_telegram_user(telegram_id):
    return TelegramUser.objects.filter(telegram_id=telegram_id).first()


def user_not_found_response():
    return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)


def user_blocked_response():
    return Response({"detail": "User is blocked."}, status=status.HTTP_403_FORBIDDEN)


def validation_error_response(exc: ValidationError):
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
