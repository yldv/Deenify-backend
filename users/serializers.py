from rest_framework import serializers

from .models import AtmosOrder, SubscriptionPlan, TelegramUser
from .services import get_user_premium_until


class TelegramUserUpsertSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField()
    full_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    username = serializers.CharField(required=False, allow_blank=True, max_length=255)
    language = serializers.ChoiceField(choices=TelegramUser.Language.choices, default="uz")


class TelegramUserLanguageSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=TelegramUser.Language.choices)


class TelegramUserSerializer(serializers.ModelSerializer):
    free_tests_used = serializers.IntegerField(source="free_tests_taken", read_only=True)
    is_premium = serializers.SerializerMethodField()
    premium_until = serializers.SerializerMethodField()
    can_take_test = serializers.SerializerMethodField()

    class Meta:
        model = TelegramUser
        fields = (
            "id",
            "telegram_id",
            "full_name",
            "username",
            "language",
            "free_tests_used",
            "is_premium",
            "premium_until",
            "can_take_test",
        )

    def get_is_premium(self, obj):
        return obj.has_active_premium()

    def get_premium_until(self, obj):
        return get_user_premium_until(obj)

    def get_can_take_test(self, obj):
        return obj.can_take_test()


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    duration_days = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPlan
        fields = ("id", "name", "duration_days", "price")

    def get_duration_days(self, obj):
        delta = obj.get_duration_delta()
        return None if delta is None else delta.days


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
    class Meta:
        model = AtmosOrder
        fields = ("order_id", "merchant_order_id", "amount", "status", "payment_url")
