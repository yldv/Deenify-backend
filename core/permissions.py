import logging

from django.conf import settings
from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)

BOT_API_SECRET_HEADER = "X-Bot-Secret"


class BotAPIPermission(BasePermission):
    """Allow bot service requests authenticated via BotAPISecretAuthentication."""

    def has_permission(self, request, view):
        if not getattr(settings, "BOT_API_SECRET", "") and settings.DEBUG:
            return True
        user = getattr(request, "user", None)
        return bool(user and getattr(user, "is_authenticated", False))
