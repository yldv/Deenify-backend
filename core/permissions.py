import logging
import secrets

from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)

BOT_API_SECRET_HEADER = "X-Bot-Secret"


class BotAPIPermission(BasePermission):
    """Allow only requests that present the shared BOT_API_SECRET header."""

    def has_permission(self, request, view):
        expected = getattr(settings, "BOT_API_SECRET", "")
        if not expected:
            if settings.DEBUG:
                logger.warning("BOT_API_SECRET is not set; bot API is open in DEBUG mode.")
                return True
            logger.error("BOT_API_SECRET is not configured; bot API access denied.")
            raise AuthenticationFailed("Bot API secret is not configured.")

        provided = request.headers.get(BOT_API_SECRET_HEADER, "")
        if not provided or not secrets.compare_digest(provided, expected):
            raise AuthenticationFailed("Invalid bot API secret.")
        return True
