from rest_framework.views import APIView

from core.permissions import BotAPIPermission


class BotProtectedAPIView(APIView):
    authentication_classes = ()
    permission_classes = (BotAPIPermission,)
