from rest_framework import serializers

from .models import AtmosOrder, SubscriptionPlan, TelegramUser
from .services import (
    get_active_premium_subscription,
    get_user_premium_until,
    get_user_subscription_snapshot,
)


class TelegramUserUpsertSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()
    full_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    username = serializers.CharField(required=False, allow_blank=True, max_length=255)
    language = serializers.ChoiceField(choices=TelegramUser.Language.choices, default="uz")
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=50)


class TelegramUserLanguageSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=TelegramUser.Language.choices)


class TelegramUserSerializer(serializers.ModelSerializer):
    free_tests_used = serializers.IntegerField(source="free_tests_taken", read_only=True)
    is_premium = serializers.SerializerMethodField()
    premium_starts_at = serializers.SerializerMethodField()
    premium_until = serializers.SerializerMethodField()
    premium_plan = serializers.SerializerMethodField()
    can_take_test = serializers.SerializerMethodField()
    is_registered = serializers.BooleanField(read_only=True)
    is_blocked = serializers.BooleanField(read_only=True)
    subscription = serializers.SerializerMethodField()

    class Meta:
        model = TelegramUser
        fields = (
            "id",
            "telegram_id",
            "full_name",
            "username",
            "phone_number",
            "language",
            "quiz_round",
            "free_tests_used",
            "is_premium",
            "premium_starts_at",
            "premium_until",
            "premium_plan",
            "can_take_test",
            "is_registered",
            "is_blocked",
            "subscription",
        )

    def get_is_premium(self, obj):
        return obj.has_active_premium()

    def get_premium_starts_at(self, obj):
        subscription = get_active_premium_subscription(obj)
        return subscription.starts_at if subscription else None

    def get_premium_until(self, obj):
        return get_user_premium_until(obj)

    def get_premium_plan(self, obj):
        subscription = get_active_premium_subscription(obj)
        return subscription.plan.name if subscription else ""

    def get_can_take_test(self, obj):
        return obj.can_take_test()

    def get_subscription(self, obj):
        return get_user_subscription_snapshot(obj)


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    duration_days = serializers.SerializerMethodField()
    payment_start_url = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPlan
        fields = (
            "id",
            "name",
            "duration_days",
            "price",
            "period",
            "duration",
            "payment_start_url",
        )

    def get_duration_days(self, obj):
        delta = obj.get_duration_delta()
        return None if delta is None else delta.days

    def get_payment_start_url(self, obj):
        telegram_id = self.context.get("telegram_id")
        if not telegram_id:
            return ""
        from .services import build_payment_start_url

        return build_payment_start_url(telegram_id=int(telegram_id), plan_id=obj.id)


class AtmosOrderCreateSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()
    plan_id = serializers.IntegerField()


class AtmosOrderSerializer(serializers.ModelSerializer):
    merchant_order_id = serializers.CharField()
    plan = SubscriptionPlanSerializer(read_only=True)

    class Meta:
        model = AtmosOrder
        fields = (
            "id",
            "order_id",
            "merchant_order_id",
            "plan",
            "amount",
            "status",
            "payment_url",
            "paid_at",
            "created_at",
        )


class AtmosOrderCreateResponseSerializer(serializers.ModelSerializer):
    payment_error = serializers.SerializerMethodField()
    payment_url = serializers.SerializerMethodField()

    class Meta:
        model = AtmosOrder
        fields = (
            "order_id",
            "merchant_order_id",
            "amount",
            "status",
            "payment_url",
            "payment_error",
        )

    def get_payment_url(self, obj):
        from .services import build_bot_payment_url

        return build_bot_payment_url(obj)

    def get_payment_error(self, obj):
        if obj.payment_url:
            return ""
        payload = obj.response_payload or {}
        return (
            payload.get("error")
            or payload.get("detail")
            or self._extract_result_error(payload)
            or "Payment URL was not created."
        )

    @staticmethod
    def _extract_result_error(payload):
        result = payload.get("result") or {}
        code = result.get("code")
        if code and str(code).upper() != "OK":
            return result.get("description") or result.get("message") or str(code)
        return ""
