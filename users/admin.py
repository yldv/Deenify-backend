from django.contrib import admin
from modeltranslation.admin import TranslationAdmin

from .models import (
    AtmosOrder,
    AtmosTransaction,
    SubscriptionPlan,
    TelegramUser,
    UserPremiumSubscription,
)


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = (
        "telegram_id",
        "username",
        "full_name",
        "first_name",
        "language",
        "free_tests_taken",
        "is_blocked",
        "has_active_premium",
        "created_at",
    )
    list_filter = ("language", "is_blocked", "created_at")
    search_fields = ("telegram_id", "username", "full_name", "first_name", "last_name")
    readonly_fields = ("created_at", "updated_at", "last_seen_at")
    list_select_related = ()

    @admin.display(boolean=True, description="Active premium")
    def has_active_premium(self, obj):
        return obj.has_active_premium()


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(TranslationAdmin):
    list_display = ("name", "price", "currency", "duration", "period", "is_active")
    list_filter = ("period", "is_active", "currency")
    search_fields = ("name",)
    ordering = ("sort_order", "price")


@admin.register(UserPremiumSubscription)
class UserPremiumSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "starts_at", "expires_at", "is_active", "is_current")
    list_filter = ("is_active", "plan", "starts_at")
    search_fields = ("user__telegram_id", "user__username", "plan__name")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("user", "plan", "source_order")

    @admin.display(boolean=True, description="Current")
    def is_current(self, obj):
        return obj.is_current


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
        "paid_at",
    )
    list_filter = ("status", "currency", "created_at", "paid_at")
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
    autocomplete_fields = ("user", "plan")
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
