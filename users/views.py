from django.utils import translation
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api import get_requested_language, get_telegram_user, user_not_found_response

from .models import AtmosOrder, SubscriptionPlan, TelegramUser
from .serializers import (
    AtmosOrderCreateResponseSerializer,
    AtmosOrderCreateSerializer,
    AtmosOrderSerializer,
    SubscriptionPlanSerializer,
    TelegramUserLanguageSerializer,
    TelegramUserSerializer,
    TelegramUserUpsertSerializer,
)
from .services import (
    create_atmos_order,
    get_active_plan,
    get_admin_statistics,
    get_user_statistics,
    process_atmos_callback,
    upsert_telegram_user,
)


class BotUserView(APIView):
    def post(self, request):
        serializer = TelegramUserUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = upsert_telegram_user(**serializer.validated_data)
        with translation.override(user.get_content_language()):
            data = TelegramUserSerializer(user).data
        return Response(data, status=status.HTTP_200_OK)


class BotUserDetailView(APIView):
    def get(self, request, telegram_id):
        user = get_telegram_user(telegram_id)
        if not user:
            return user_not_found_response()
        with translation.override(user.get_content_language()):
            data = TelegramUserSerializer(user).data
        return Response(data, status=status.HTTP_200_OK)


class BotUserLanguageView(APIView):
    def patch(self, request, telegram_id):
        user = get_telegram_user(telegram_id)
        if not user:
            return user_not_found_response()

        serializer = TelegramUserLanguageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user.language = serializer.validated_data["language"]
        user.save(update_fields=("language", "updated_at"))
        with translation.override(user.get_content_language()):
            data = TelegramUserSerializer(user).data
        return Response(data, status=status.HTTP_200_OK)


class BotUserStatisticsView(APIView):
    def get(self, request, telegram_id):
        user = get_telegram_user(telegram_id)
        if not user:
            return user_not_found_response()
        return Response(get_user_statistics(user), status=status.HTTP_200_OK)


class SubscriptionPlanListView(APIView):
    def get(self, request):
        telegram_id = request.query_params.get("telegram_id")
        user = get_telegram_user(telegram_id) if telegram_id else None
        queryset = SubscriptionPlan.objects.filter(is_active=True).order_by("sort_order", "price")
        with translation.override(get_requested_language(request, user)):
            data = SubscriptionPlanSerializer(queryset, many=True).data
        return Response(data, status=status.HTTP_200_OK)


class AtmosOrderCreateView(APIView):
    def post(self, request):
        serializer = AtmosOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = get_telegram_user(serializer.validated_data["telegram_id"])
        if not user:
            return user_not_found_response()
        if user.is_blocked:
            return Response({"detail": "User is blocked."}, status=status.HTTP_403_FORBIDDEN)

        plan = get_active_plan(serializer.validated_data["plan_id"])
        if not plan:
            return Response({"detail": "Subscription plan not found."}, status=status.HTTP_404_NOT_FOUND)

        order = create_atmos_order(user=user, plan=plan)
        return Response(
            AtmosOrderCreateResponseSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )


class AtmosCallbackView(APIView):
    authentication_classes = ()
    permission_classes = ()

    def post(self, request):
        result = process_atmos_callback(request.data)
        response_status = result.get("status", 200)
        if not result.get("ok"):
            return Response(
                {"success": False, "error": result.get("error")},
                status=response_status,
            )
        return Response({"success": True}, status=status.HTTP_200_OK)


class BotUserOrdersView(APIView):
    def get(self, request, telegram_id):
        user = get_telegram_user(telegram_id)
        if not user:
            return user_not_found_response()
        orders = (
            AtmosOrder.objects.filter(user=user)
            .select_related("plan")
            .order_by("-created_at")
        )
        with translation.override(get_requested_language(request, user)):
            data = AtmosOrderSerializer(orders, many=True).data
        return Response(data, status=status.HTTP_200_OK)


class AdminStatisticsView(APIView):
    permission_classes = (IsAdminUser,)

    def get(self, request):
        return Response(get_admin_statistics(), status=status.HTTP_200_OK)
