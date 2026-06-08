from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.response import Response

from core.languages import normalize_language_code
from users.models import TelegramUser


def get_requested_language(request, user=None):
    if user:
        return user.get_content_language()
    return normalize_language_code(request.headers.get("Accept-Language"))


def get_telegram_user(telegram_id):
    return (
        TelegramUser.objects.filter(telegram_id=telegram_id)
        .prefetch_related("premium_subscriptions__plan", "atmos_orders__plan")
        .first()
    )


def user_not_found_response():
    return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)


def user_blocked_response():
    return Response({"detail": "User is blocked."}, status=status.HTTP_403_FORBIDDEN)


def validation_error_response(exc: ValidationError):
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
