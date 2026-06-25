import time

from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone, translation
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api import get_requested_language, get_telegram_user, user_not_found_response
from core.bot_api import BotProtectedAPIView

from .models import AtmosOrder, Feedback, SubscriptionPlan, TelegramUser
from .serializers import (
    AtmosOrderCreateResponseSerializer,
    AtmosOrderCreateSerializer,
    AtmosOrderSerializer,
    FeedbackCreateSerializer,
    SubscriptionPlanSerializer,
    TelegramUserBotActiveSerializer,
    TelegramUserLanguageSerializer,
    TelegramUserOfferMessageSerializer,
    TelegramUserSerializer,
    TelegramUserUpsertSerializer,
)
from .services import (
    CARD_SESSION_TOKEN_TTL,
    AtmosPaymentService,
    build_card_session_token,
    build_referral_link,
    charge_subscription,
    confirm_card_binding,
    create_atmos_order,
    get_active_plan,
    get_active_premium_subscription,
    get_admin_statistics,
    get_referral_stats,
    get_user_statistics,
    process_atmos_callback,
    parse_atmos_callback_payload,
    remove_bound_card,
    set_telegram_user_bot_active,
    start_card_binding,
    sync_atmos_order_payment,
    upsert_telegram_user,
    verify_card_session_token,
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
    """Cancel auto-renewal and unlink the card (Atmos remove-card). Premium stays
    active until the end of the already paid period."""

    def post(self, request, telegram_id):
        user = get_telegram_user(telegram_id)
        if not user:
            return user_not_found_response()

        active = get_active_premium_subscription(user)
        result = remove_bound_card(user)
        expires_at = active.expires_at if active else None
        return Response(
            {
                "ok": result.get("ok", True),
                "removed": result.get("removed", False),
                "had_premium": bool(active),
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


@extend_schema(
    tags=["payments"],
    request=AtmosOrderCreateSerializer,
    responses={201: AtmosOrderCreateResponseSerializer},
)
class AtmosOrderCreateView(BotProtectedAPIView):
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
        data = AtmosOrderCreateResponseSerializer(order).data
        if not order.payment_url:
            return Response(
                data,
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["payments"],
    request=OpenApiTypes.OBJECT,
    responses={200: OpenApiTypes.OBJECT},
)
class AtmosPaymentStartView(APIView):
    """One-tap plan button: render the card payment form (create -> pre-apply -> apply)."""

    authentication_classes = ()
    permission_classes = ()

    def get(self, request):
        try:
            telegram_id = int(request.GET.get("telegram_id", ""))
            plan_id = int(request.GET.get("plan_id", ""))
            exp = int(request.GET.get("exp", ""))
        except (TypeError, ValueError):
            return render(request, "payments/atmos_card.html", {"error": "Invalid payment link."}, status=403)

        signature = (request.GET.get("sig") or "").strip()
        if not verify_payment_start_signature(
            telegram_id=telegram_id,
            plan_id=plan_id,
            exp=exp,
            signature=signature,
        ):
            return render(
                request,
                "payments/atmos_card.html",
                {"error": "Payment link is invalid or expired."},
                status=403,
            )

        user = get_telegram_user(telegram_id)
        if not user:
            return render(request, "payments/atmos_card.html", {"error": "User not found."}, status=404)
        if user.is_blocked:
            return render(request, "payments/atmos_card.html", {"error": "User is blocked."}, status=403)

        plan = get_active_plan(plan_id)
        if not plan:
            return render(request, "payments/atmos_card.html", {"error": "Subscription plan not found."}, status=404)

        lang = (getattr(user, "language", "") or "uz").strip()
        if lang not in ("uz", "uz_cy", "ru"):
            lang = "uz"
        context = {
            "telegram_id": telegram_id,
            "plan_id": plan_id,
            "exp": exp,
            "sig": signature,
            "plan_name": plan.name,
            "amount": int(plan.price),
            "currency": plan.currency or "UZS",
            "lang": lang,
            "preapply_url": reverse("atmos-card-preapply"),
            "apply_url": reverse("atmos-card-apply"),
            "set_language_url": reverse("atmos-card-set-language"),
            "bot_url": settings.ATMOS_SUCCESS_REDIRECT_URL or "https://t.me/DeenifyUzBot",
        }
        return render(request, "payments/atmos_card.html", context)


class AtmosCardPreApplyView(APIView):
    """Start Atmos card binding (/partner/bind-card/init). Atmos sends the SMS code."""

    authentication_classes = ()
    permission_classes = ()

    def post(self, request):
        data = request.data
        try:
            telegram_id = int(data.get("telegram_id"))
            plan_id = int(data.get("plan_id"))
            exp = int(data.get("exp"))
        except (TypeError, ValueError):
            return Response({"ok": False, "error": "Invalid request."}, status=400)

        if not verify_payment_start_signature(
            telegram_id=telegram_id, plan_id=plan_id, exp=exp, signature=(data.get("sig") or "").strip()
        ):
            return Response({"ok": False, "error": "Invalid or expired link."}, status=403)

        card_number = (data.get("card_number") or "").replace(" ", "").strip()
        expiry = (data.get("expiry") or "").strip()
        if len(card_number) < 16 or len(expiry) != 4:
            return Response({"ok": False, "error": "Karta raqami yoki amal qilish muddati noto'g'ri."}, status=400)

        user = get_telegram_user(telegram_id)
        if not user or user.is_blocked:
            return Response({"ok": False, "error": "User not available."}, status=403)
        plan = get_active_plan(plan_id)
        if not plan:
            return Response({"ok": False, "error": "Plan not found."}, status=404)

        result = start_card_binding(card_number=card_number, expiry=expiry)
        if not result.get("ok"):
            return Response({"ok": False, "error": result.get("error") or "Bind init failed."}, status=502)

        bind_transaction_id = result["transaction_id"]
        token_exp = int(time.time()) + CARD_SESSION_TOKEN_TTL
        token = build_card_session_token(order_id=bind_transaction_id, exp=token_exp)
        return Response(
            {
                "ok": True,
                "bind_transaction_id": bind_transaction_id,
                "phone": result.get("phone", ""),
                "token": token,
                "token_exp": token_exp,
            }
        )


def _subscription_summary(order):
    """Plan + duration info for the success screen."""
    plan = order.plan
    subscription = getattr(order, "premium_subscription", None)
    expires_at = subscription.expires_at if subscription else None
    return {
        "plan_name": plan.name if plan else "Premium",
        "period": plan.period if plan else "month",
        "duration": plan.duration if plan else 1,
        "is_lifetime": bool(plan and plan.period == "lifetime") or (subscription is not None and expires_at is None),
        "expires_at": expires_at.strftime("%d.%m.%Y") if expires_at else "",
    }


class AtmosCardApplyView(APIView):
    """Confirm card binding with the SMS code, then charge the first period by token."""

    authentication_classes = ()
    permission_classes = ()

    def post(self, request):
        data = request.data
        bind_transaction_id = (str(data.get("bind_transaction_id") or "")).strip()
        otp = (str(data.get("otp")) or "").strip()
        try:
            telegram_id = int(data.get("telegram_id"))
            plan_id = int(data.get("plan_id"))
            exp = int(data.get("exp"))
            token_exp = int(data.get("token_exp"))
        except (TypeError, ValueError):
            return Response({"ok": False, "error": "Invalid session."}, status=400)

        if not verify_payment_start_signature(
            telegram_id=telegram_id, plan_id=plan_id, exp=exp, signature=(data.get("sig") or "").strip()
        ):
            return Response({"ok": False, "error": "Invalid or expired link."}, status=403)

        if not verify_card_session_token(
            order_id=bind_transaction_id, exp=token_exp, token=(data.get("token") or "").strip()
        ):
            return Response({"ok": False, "error": "Sessiya muddati tugagan. Qaytadan urinib ko'ring."}, status=403)

        if not otp.isdigit():
            return Response({"ok": False, "error": "SMS kodni to'g'ri kiriting."}, status=400)

        user = get_telegram_user(telegram_id)
        if not user or user.is_blocked:
            return Response({"ok": False, "error": "User not available."}, status=403)
        plan = get_active_plan(plan_id)
        if not plan:
            return Response({"ok": False, "error": "Plan not found."}, status=404)

        bind_result = confirm_card_binding(
            user=user, transaction_id=bind_transaction_id, otp=otp
        )
        if not bind_result.get("ok"):
            return Response(
                {"ok": False, "error": bind_result.get("error") or "Kartani bog'lab bo'lmadi."},
                status=502,
            )

        charge = charge_subscription(
            user=user,
            plan=plan,
            card_data=bind_result["card_data"],
            is_auto_renewal=False,
        )
        if not charge.get("ok"):
            return Response(
                {"ok": False, "error": charge.get("error") or "To'lov amalga oshmadi."},
                status=502,
            )

        return Response(
            {
                "ok": True,
                "redirect": settings.ATMOS_SUCCESS_REDIRECT_URL or "https://t.me/DeenifyUzBot",
                "subscription": _subscription_summary(charge["order"]),
            }
        )


class AtmosCardSetLanguageView(APIView):
    """Persist the language chosen on the payment page to the user's profile so the
    bot (and all backend messages) switch to it too."""

    authentication_classes = ()
    permission_classes = ()

    def post(self, request):
        data = request.data
        try:
            telegram_id = int(data.get("telegram_id"))
            plan_id = int(data.get("plan_id"))
            exp = int(data.get("exp"))
        except (TypeError, ValueError):
            return Response({"ok": False, "error": "Invalid request."}, status=400)

        if not verify_payment_start_signature(
            telegram_id=telegram_id, plan_id=plan_id, exp=exp, signature=(data.get("sig") or "").strip()
        ):
            return Response({"ok": False, "error": "Invalid or expired link."}, status=403)

        language = (data.get("language") or "").strip()
        valid_languages = {choice[0] for choice in TelegramUser.Language.choices}
        if language not in valid_languages:
            return Response({"ok": False, "error": "Unsupported language."}, status=400)

        user = get_telegram_user(telegram_id)
        if not user:
            return user_not_found_response()
        if user.language != language:
            user.language = language
            user.save(update_fields=("language", "updated_at"))
        return Response({"ok": True})


class AtmosCheckoutRedirectView(APIView):
    authentication_classes = ()
    permission_classes = ()

    def get(self, request, order_id):
        order = AtmosOrder.objects.filter(order_id=order_id).first()
        if not order or not order.payment_url:
            return HttpResponseNotFound("Payment link not found.")

        target = AtmosPaymentService.client_checkout_url(order.payment_url)
        return redirect(target)


class AtmosCallbackView(APIView):
    authentication_classes = ()
    permission_classes = ()

    def post(self, request):
        payload = parse_atmos_callback_payload(request)
        result = process_atmos_callback(payload)
        return Response(
            {
                "status": result.get("atmos_status", 0),
                "message": result.get("message", "Error"),
            },
            status=result.get("http_status", 200),
        )


class AtmosReturnView(APIView):
    """Redirect after payment on test-checkout.pays.uz / checkout.pays.uz."""

    authentication_classes = ()
    permission_classes = ()

    def get(self, request):
        transaction_id = (
            request.query_params.get("transactionId")
            or request.query_params.get("transaction_id")
        )
        if transaction_id:
            order = AtmosOrder.objects.filter(
                atmos_transaction_id=str(transaction_id)
            ).first()
            if order:
                sync_atmos_order_payment(order)

        return_url = (
            settings.ATMOS_SUCCESS_REDIRECT_URL or "https://t.me/DeenifyUzBot"
        ).strip()
        return redirect(return_url)


@extend_schema(tags=["bot-users"], responses={200: AtmosOrderSerializer(many=True)})
class BotUserOrdersView(BotProtectedAPIView):
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


@extend_schema(tags=["admin"], responses={200: OpenApiTypes.OBJECT})
class AdminStatisticsView(APIView):
    permission_classes = (IsAdminUser,)

    def get(self, request):
        return Response(get_admin_statistics(), status=status.HTTP_200_OK)
