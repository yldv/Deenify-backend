from django.conf import settings
from django.http import HttpResponseNotFound
from django.shortcuts import render
from django.utils import timezone, translation
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api import get_requested_language, get_telegram_user, user_not_found_response
from core.bot_api import BotProtectedAPIView

from .models import ClickOrder, Feedback, SubscriptionPlan, TelegramUser
from .serializers import (
    ClickOrderCreateResponseSerializer,
    ClickOrderCreateSerializer,
    ClickOrderSerializer,
    FeedbackCreateSerializer,
    SubscriptionPlanSerializer,
    TelegramUserBotActiveSerializer,
    TelegramUserLanguageSerializer,
    TelegramUserOfferMessageSerializer,
    TelegramUserSerializer,
    TelegramUserUpsertSerializer,
)
from .services import (
    ClickPaymentService,
    build_referral_link,
    cancel_subscription,
    click_checkout_context,
    create_click_order,
    get_active_plan,
    get_active_premium_subscription,
    get_admin_statistics,
    get_referral_stats,
    get_user_statistics,
    process_click_callback,
    process_click_complete,
    process_click_prepare,
    set_telegram_user_bot_active,
    upsert_telegram_user,
    verify_payment_start_signature,
)


@extend_schema(
    tags=["bot-users"],
    request=TelegramUserUpsertSerializer,
    responses={200: TelegramUserSerializer},
)
class BotUserView(BotProtectedAPIView):
    def post(self, request):
        serializer = TelegramUserUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = upsert_telegram_user(**serializer.validated_data)
        with translation.override(user.get_content_language()):
            data = TelegramUserSerializer(user).data
        return Response(data, status=status.HTTP_200_OK)


@extend_schema(tags=["bot-users"], responses={200: TelegramUserSerializer})
class BotUserDetailView(BotProtectedAPIView):
    def get(self, request, telegram_id):
        user = get_telegram_user(telegram_id)
        if not user:
            return user_not_found_response()
        with translation.override(user.get_content_language()):
            data = TelegramUserSerializer(user).data
        return Response(data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["bot-users"],
    request=TelegramUserLanguageSerializer,
    responses={200: TelegramUserSerializer},
)
class BotUserLanguageView(BotProtectedAPIView):
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


@extend_schema(
    tags=["bot-users"],
    request=TelegramUserBotActiveSerializer,
    responses={200: TelegramUserSerializer},
)
class BotUserBotActiveView(BotProtectedAPIView):
    def patch(self, request, telegram_id):
        user = get_telegram_user(telegram_id)
        if not user:
            return user_not_found_response()

        serializer = TelegramUserBotActiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = set_telegram_user_bot_active(
            telegram_id=telegram_id,
            bot_is_active=serializer.validated_data["bot_is_active"],
        )
        with translation.override(user.get_content_language()):
            data = TelegramUserSerializer(user).data
        return Response(data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["bot-users"],
    request=TelegramUserOfferMessageSerializer,
    responses={200: OpenApiTypes.OBJECT},
)
class BotUserOfferMessageView(BotProtectedAPIView):
    """Remember the last subscription catalog message so the backend can delete it
    after a successful payment."""

    def patch(self, request, telegram_id):
        user = get_telegram_user(telegram_id)
        if not user:
            return user_not_found_response()

        serializer = TelegramUserOfferMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user.offer_message_id = serializer.validated_data.get("message_id")
        user.offer_chat_id = serializer.validated_data.get("chat_id")
        user.offer_prompt_message_id = serializer.validated_data.get("prompt_message_id")
        if user.offer_message_id and user.offer_chat_id:
            user.offer_sent_at = timezone.now()
        user.save(
            update_fields=(
                "offer_message_id",
                "offer_chat_id",
                "offer_prompt_message_id",
                "offer_sent_at",
                "updated_at",
            )
        )
        return Response({"ok": True}, status=status.HTTP_200_OK)


@extend_schema(tags=["bot-users"], responses={200: OpenApiTypes.OBJECT})
class BotUserStatisticsView(BotProtectedAPIView):
    def get(self, request, telegram_id):
        user = get_telegram_user(telegram_id)
        if not user:
            return user_not_found_response()
        return Response(get_user_statistics(user), status=status.HTTP_200_OK)


@extend_schema(tags=["bot-users"], responses={200: OpenApiTypes.OBJECT})
class BotUserReferralView(BotProtectedAPIView):
    """Referral link + stats for the 'invite friends' panel."""

    def get(self, request, telegram_id):
        user = get_telegram_user(telegram_id)
        if not user:
            return user_not_found_response()
        stats = get_referral_stats(user)
        return Response(
            {"link": build_referral_link(user), **stats},
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["bot-users"], responses={200: OpenApiTypes.OBJECT})
class BotUserCancelSubscriptionView(BotProtectedAPIView):
    """Close the current premium period. Click charges per purchase, so there is
    no stored card or auto-renewal to switch off."""

    def post(self, request, telegram_id):
        user = get_telegram_user(telegram_id)
        if not user:
            return user_not_found_response()

        active = get_active_premium_subscription(user)
        result = cancel_subscription(user)
        expires_at = active.expires_at if active else None
        return Response(
            {
                "ok": result.get("ok", True),
                "had_premium": bool(result.get("had_premium")),
                "expires_at": expires_at.strftime("%d.%m.%Y") if expires_at else "",
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["bot-users"],
    request=FeedbackCreateSerializer,
    responses={201: OpenApiTypes.OBJECT},
)
class BotUserFeedbackView(BotProtectedAPIView):
    """Store user feedback collected when a user declines or cancels premium."""

    def post(self, request, telegram_id):
        user = get_telegram_user(telegram_id)
        if not user:
            return user_not_found_response()

        serializer = FeedbackCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        feedback = Feedback.objects.create(
            user=user,
            context=serializer.validated_data.get("context", Feedback.Context.DECLINED),
            reason=serializer.validated_data.get("reason", ""),
            text=serializer.validated_data.get("text", ""),
        )
        return Response({"ok": True, "id": feedback.id}, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["subscriptions"],
    parameters=[
        OpenApiParameter(
            "telegram_id",
            OpenApiTypes.INT,
            OpenApiParameter.QUERY,
            required=False,
        ),
    ],
    responses={200: SubscriptionPlanSerializer(many=True)},
)
class SubscriptionPlanListView(BotProtectedAPIView):
    def get(self, request):
        telegram_id = request.query_params.get("telegram_id")
        user = get_telegram_user(telegram_id) if telegram_id else None
        queryset = SubscriptionPlan.objects.filter(is_active=True).order_by("sort_order", "price")
        with translation.override(get_requested_language(request, user)):
            serializer = SubscriptionPlanSerializer(
                queryset,
                many=True,
                context={"telegram_id": telegram_id},
            )
            data = serializer.data
        return Response(data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Click payments
# ---------------------------------------------------------------------------

CHECKOUT_TEMPLATE = "payments/click_checkout.html"
RETURN_TEMPLATE = "payments/click_return.html"


def _bot_url() -> str:
    return (settings.CLICK_BOT_URL or "https://t.me/DeenifyUzBot").strip()


def _render_checkout(request, order, *, status_code=200):
    return render(
        request,
        CHECKOUT_TEMPLATE,
        click_checkout_context(order),
        status=status_code,
    )


def _render_checkout_error(request, message, *, status_code=403):
    return render(
        request,
        CHECKOUT_TEMPLATE,
        {"error": message, "bot_url": _bot_url()},
        status=status_code,
    )


@extend_schema(
    tags=["payments"],
    request=ClickOrderCreateSerializer,
    responses={201: ClickOrderCreateResponseSerializer},
)
class ClickOrderCreateView(BotProtectedAPIView):
    """Bot-facing endpoint: create a Click order and get the checkout page link."""

    def post(self, request):
        serializer = ClickOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = get_telegram_user(serializer.validated_data["telegram_id"])
        if not user:
            return user_not_found_response()
        if user.is_blocked:
            return Response({"detail": "User is blocked."}, status=status.HTTP_403_FORBIDDEN)

        plan = get_active_plan(serializer.validated_data["plan_id"])
        if not plan:
            return Response({"detail": "Subscription plan not found."}, status=status.HTTP_404_NOT_FOUND)

        order = create_click_order(user=user, plan=plan)
        data = ClickOrderCreateResponseSerializer(order).data
        if not order.checkout_url:
            return Response(data, status=status.HTTP_502_BAD_GATEWAY)
        return Response(data, status=status.HTTP_201_CREATED)


class ClickPaymentStartView(APIView):
    """Entry point of the bot's plan buttons: verify the signed link, create one
    Click order and render our own checkout page."""

    authentication_classes = ()
    permission_classes = ()

    def get(self, request):
        try:
            telegram_id = int(request.GET.get("telegram_id", ""))
            plan_id = int(request.GET.get("plan_id", ""))
            exp = int(request.GET.get("exp", ""))
        except (TypeError, ValueError):
            return _render_checkout_error(request, "Invalid payment link.", status_code=403)

        if not verify_payment_start_signature(
            telegram_id=telegram_id,
            plan_id=plan_id,
            exp=exp,
            signature=(request.GET.get("sig") or "").strip(),
        ):
            return _render_checkout_error(
                request, "Payment link is invalid or expired.", status_code=403
            )

        user = get_telegram_user(telegram_id)
        if not user:
            return _render_checkout_error(request, "User not found.", status_code=404)
        if user.is_blocked:
            return _render_checkout_error(request, "User is blocked.", status_code=403)

        plan = get_active_plan(plan_id)
        if not plan:
            return _render_checkout_error(request, "Subscription plan not found.", status_code=404)

        order = create_click_order(user=user, plan=plan)
        if not order.checkout_url:
            error = (order.response_payload or {}).get("error")
            return _render_checkout_error(
                request, error or "Click payment is unavailable.", status_code=503
            )
        return _render_checkout(request, order)


class ClickOrderCheckoutView(APIView):
    """Reopen the checkout page of an order created through the bot API."""

    authentication_classes = ()
    permission_classes = ()

    def get(self, request, order_id):
        order = (
            ClickOrder.objects.select_related("plan")
            .filter(order_id=order_id)
            .first()
        )
        if not order:
            return HttpResponseNotFound("Payment link not found.")
        if order.status == ClickOrder.Status.PAID:
            return render(
                request,
                RETURN_TEMPLATE,
                {"paid": True, "bot_url": _bot_url()},
            )
        try:
            return _render_checkout(request, order)
        except ValueError as exc:
            return _render_checkout_error(request, str(exc), status_code=503)


class ClickCallbackView(APIView):
    """Click Merchant API callback (register this exact URL in the Click cabinet).

    Note: prefer separate prepare/complete endpoints. This view remains
    for backward compatibility.
    """

    authentication_classes = ()
    permission_classes = ()

    def post(self, request):
        return Response(process_click_callback(request.data), status=status.HTTP_200_OK)


class ClickPrepareCallbackView(APIView):
    """Click Prepare callback (action=0)."""

    authentication_classes = ()
    permission_classes = ()

    def post(self, request):
        return Response(process_click_prepare(request.data), status=status.HTTP_200_OK)


class ClickCompleteCallbackView(APIView):
    """Click Complete callback (action=1)."""

    authentication_classes = ()
    permission_classes = ()

    def post(self, request):
        return Response(process_click_complete(request.data), status=status.HTTP_200_OK)


class ClickReturnView(APIView):
    """Click sends the customer back here after the payment page."""

    authentication_classes = ()
    permission_classes = ()

    def get(self, request):
        service = ClickPaymentService()
        return render(
            request,
            RETURN_TEMPLATE,
            {
                "bot_url": _bot_url(),
                "service_id": settings.CLICK_SERVICE_ID,
                "merchant_id": settings.CLICK_MERCHANT_ID,
                "configured": service.is_configured(),
            },
        )


@extend_schema(tags=["bot-users"], responses={200: ClickOrderSerializer(many=True)})
class BotUserOrdersView(BotProtectedAPIView):
    def get(self, request, telegram_id):
        user = get_telegram_user(telegram_id)
        if not user:
            return user_not_found_response()
        orders = (
            ClickOrder.objects.filter(user=user)
            .select_related("plan")
            .order_by("-created_at")
        )
        with translation.override(get_requested_language(request, user)):
            data = ClickOrderSerializer(orders, many=True).data
        return Response(data, status=status.HTTP_200_OK)


@extend_schema(tags=["admin"], responses={200: OpenApiTypes.OBJECT})
class AdminStatisticsView(APIView):
    permission_classes = (IsAdminUser,)

    def get(self, request):
        return Response(get_admin_statistics(), status=status.HTTP_200_OK)
