from django.contrib import admin
from django.utils import timezone

from .models import (
    ActiveTelegramUser,
    AtmosOrder,
    AtmosTransaction,
    BoundCard,
    Feedback,
    SubscriptionPlan,
    TelegramUser,
    UserPremiumSubscription,
)


class TelegramUserAdminBase(admin.ModelAdmin):
    list_display = (
        "telegram_id",
        "username",
        "full_name",
        "phone_number",
        "language",
        "quiz_round",
        "free_tests_taken",
        "bot_is_active",
        "is_blocked",
        "has_active_premium",
        "premium_starts_at",
        "premium_expires_at",
        "last_seen_at",
        "created_at",
    )
    list_filter = ("language", "bot_is_active", "is_blocked", "created_at")
    search_fields = ("telegram_id", "username", "full_name", "first_name", "last_name", "phone_number")
    readonly_fields = ("created_at", "updated_at", "last_seen_at")
    fieldsets = (
        (
            "Telegram",
            {"fields": ("telegram_id", "username", "full_name", "first_name", "last_name", "language")},
        ),
        ("Aloqa", {"fields": ("phone_number",)}),
        (
            "Test va cheklovlar",
            {"fields": ("quiz_round", "free_tests_taken", "bot_is_active", "is_blocked")},
        ),
        ("Vaqt", {"fields": ("created_at", "updated_at", "last_seen_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("premium_subscriptions__plan")

    @admin.display(boolean=True, description="Premium")
    def has_active_premium(self, obj):
        return obj.has_active_premium()

    @admin.display(description="Premium boshlandi")
    def premium_starts_at(self, obj):
        subscription = self._current_subscription(obj)
        if not subscription:
            return "—"
        return timezone.localtime(subscription.starts_at).strftime("%d.%m.%Y %H:%M")

    @admin.display(description="Premium tugaydi")
    def premium_expires_at(self, obj):
        subscription = self._current_subscription(obj)
        if not subscription:
            return "—"
        if subscription.expires_at is None:
            return "∞"
        return timezone.localtime(subscription.expires_at).strftime("%d.%m.%Y %H:%M")

    @staticmethod
    def _current_subscription(obj):
        now = timezone.now()
        for subscription in obj.premium_subscriptions.all():
            if (
                subscription.is_active
                and subscription.starts_at <= now
                and (subscription.expires_at is None or subscription.expires_at > now)
            ):
                return subscription
        return None


@admin.register(TelegramUser)
class TelegramUserAdmin(TelegramUserAdminBase):
    pass


@admin.register(ActiveTelegramUser)
class ActiveTelegramUserAdmin(TelegramUserAdminBase):
    list_display = tuple(
        field for field in TelegramUserAdminBase.list_display if field != "bot_is_active"
    )
    list_filter = ("language", "is_blocked", "created_at")

    def get_queryset(self, request):
        return super().get_queryset(request).filter(bot_is_active=True)

    def has_add_permission(self, request):
        return False


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "currency", "duration", "period", "is_active")
    list_filter = ("period", "is_active", "currency")
    search_fields = ("name", "name_uz", "name_ru")
    ordering = ("sort_order", "price")
    fieldsets = (
        (
            "Narx va muddat",
            {"fields": ("price", "currency", "duration", "period", "is_active", "sort_order")},
        ),
        ("O'zbekcha (lotin)", {"fields": ("name_uz", "description_uz"), "classes": ("deenify-fs-uz",)}),
        ("Ўzbekcha (kirill)", {"fields": ("name_uz_cy", "description_uz_cy"), "classes": ("deenify-fs-uz-cy",)}),
        ("Ruscha", {"fields": ("name_ru", "description_ru"), "classes": ("deenify-fs-ru",)}),
    )

    def save_model(self, request, obj, form, change):
        if obj.name_uz and not obj.name:
            obj.name = obj.name_uz
        if obj.description_uz and not obj.description:
            obj.description = obj.description_uz
        super().save_model(request, obj, form, change)


@admin.register(UserPremiumSubscription)
class UserPremiumSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "source",
        "auto_renew",
        "starts_at",
        "expires_at",
        "is_active",
        "is_current",
    )
    list_filter = ("is_active", "auto_renew", "source", "plan", "starts_at", "expires_at")
    search_fields = ("user__telegram_id", "user__username", "plan__name")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("user", "plan", "source_order", "bound_card")
    ordering = ("-starts_at",)

    @admin.display(boolean=True, description="Joriy")
    def is_current(self, obj):
        return obj.is_current


@admin.register(BoundCard)
class BoundCardAdmin(admin.ModelAdmin):
    list_display = ("user", "masked_pan", "card_id", "expiry", "is_active", "created_at", "removed_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("user__telegram_id", "user__username", "card_id", "masked_pan")
    readonly_fields = ("created_at", "updated_at", "removed_at", "card_token")
    autocomplete_fields = ("user",)
    ordering = ("-created_at",)


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("user", "context", "reason", "short_text", "created_at")
    list_filter = ("context", "reason", "created_at")
    search_fields = ("user__telegram_id", "user__username", "text")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("user",)
    ordering = ("-created_at",)

    @admin.display(description="Text")
    def short_text(self, obj):
        return (obj.text[:60] + "…") if len(obj.text or "") > 60 else (obj.text or "")


class AtmosTransactionInline(admin.TabularInline):
    model = AtmosTransaction
    extra = 0
    readonly_fields = (
        "transaction_id",
        "status",
        "amount",
        "currency",
        "performed_at",
        "created_at",
    )
    can_delete = False


@admin.register(AtmosOrder)
class AtmosOrderAdmin(admin.ModelAdmin):
    list_display = (
        "merchant_order_id",
        "order_id",
        "user",
        "plan",
        "amount",
        "currency",
        "status",
        "is_auto_renewal",
        "paid_at",
    )
    list_filter = ("status", "is_auto_renewal", "currency", "created_at", "paid_at")
    search_fields = (
        "order_id",
        "merchant_order_id",
        "atmos_transaction_id",
        "user__telegram_id",
        "user__username",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "paid_at",
        "payment_url",
        "request_payload",
        "response_payload",
    )
    autocomplete_fields = ("user", "plan", "bound_card")
    inlines = (AtmosTransactionInline,)


@admin.register(AtmosTransaction)
class AtmosTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_id",
        "order",
        "status",
        "amount",
        "currency",
        "performed_at",
    )
    list_filter = ("status", "currency", "created_at", "performed_at")
    search_fields = ("transaction_id", "order__order_id", "order__user__telegram_id")
    readonly_fields = ("created_at", "updated_at", "provider_payload")
    autocomplete_fields = ("order",)
