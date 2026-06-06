import logging
import secrets

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from core.permissions import BOT_API_SECRET_HEADER

logger = logging.getLogger(__name__)


class BotServiceUser:
    is_authenticated = True
    is_anonymous = False


class BotAPISecretAuthentication(BaseAuthentication):
    """Shared-secret auth for Telegram bot -> backend API calls."""

    def authenticate(self, request):
        expected = getattr(settings, "BOT_API_SECRET", "")
        if not expected:
            if settings.DEBUG:
                logger.warning("BOT_API_SECRET is not set; bot API is open in DEBUG mode.")
                return (BotServiceUser(), None)
            logger.error("BOT_API_SECRET is not configured; bot API access denied.")
            raise AuthenticationFailed("Bot API secret is not configured.")

        try:
            provided = request.headers.get(BOT_API_SECRET_HEADER, "") or ""
            if not provided or not secrets.compare_digest(provided, expected):
                raise AuthenticationFailed("Invalid bot API secret.")
        except AuthenticationFailed:
            raise
        except Exception:
            logger.exception("Bot API secret validation failed.")
            raise AuthenticationFailed("Invalid bot API secret.") from None

        return (BotServiceUser(), None)
