from rest_framework.views import APIView

from core.authentication import BotAPISecretAuthentication
from core.permissions import BotAPIPermission


class BotProtectedAPIView(APIView):
    authentication_classes = (BotAPISecretAuthentication,)
    permission_classes = (BotAPIPermission,)
