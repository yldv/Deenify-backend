from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        abstract = True


class TelegramUser(TimeStampedModel):
    class Language(models.TextChoices):
        UZ = "uz", _("Uzbek")
        UZ_CY = "uz_cy", _("Uzbek Cyrillic")
        RU = "ru", _("Russian")

    FREE_TEST_LIMIT = 10

    telegram_id = models.BigIntegerField(_("telegram id"), unique=True, db_index=True)
    full_name = models.CharField(_("full name"), max_length=255, blank=True)
    username = models.CharField(_("username"), max_length=255, blank=True)
    first_name = models.CharField(_("first name"), max_length=255, blank=True)
    last_name = models.CharField(_("last name"), max_length=255, blank=True)
    language = models.CharField(
        _("language"),
        max_length=5,
        choices=Language.choices,
        default=Language.UZ,
    )
    phone_number = models.CharField(_("phone number"), max_length=50, blank=True)
    is_blocked = models.BooleanField(_("is blocked"), default=False)
    bot_is_active = models.BooleanField(
        _("bot is active"),
        default=True,
        db_index=True,
        help_text=_("False if the user blocked the bot or deleted the chat."),
    )
    free_tests_taken = models.PositiveSmallIntegerField(_("free tests taken"), default=0)
    quiz_round = models.PositiveIntegerField(_("quiz round"), default=1)
    last_seen_at = models.DateTimeField(_("last seen at"), null=True, blank=True)
    offer_message_id = models.BigIntegerField(
        _("offer message id"),
        null=True,
        blank=True,
        help_text=_("Telegram message id of the last subscription catalog message."),
    )
    offer_chat_id = models.BigIntegerField(
        _("offer chat id"),
        null=True,
        blank=True,
        help_text=_("Chat where the last subscription catalog message was sent."),
    )
    offer_prompt_message_id = models.BigIntegerField(
        _("offer prompt message id"),
        null=True,
        blank=True,
        help_text=_("Telegram message id of the 'subscription required' lead-in message."),
    )
    offer_sent_at = models.DateTimeField(
        _("offer sent at"),
        null=True,
        blank=True,
        help_text=_("When the subscription catalog was last sent (for auto-delete after TTL)."),
    )
    referred_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="referrals",
        null=True,
        blank=True,
        verbose_name=_("referred by"),
        help_text=_("User who invited this user via a referral link."),
    )
    referral_rewarded = models.BooleanField(
        _("referral rewarded"),
        default=False,
        help_text=_("Whether this user's first payment already rewarded the inviter."),
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Telegram user")
        verbose_name_plural = _("Telegram users")

    def __str__(self):
        display_name = self.full_name or " ".join(
            filter(None, [self.first_name, self.last_name])
        ).strip()
        return display_name or self.username or str(self.telegram_id)

    def has_active_premium(self):
        now = timezone.now()
        return self.premium_subscriptions.filter(
            is_active=True,
            starts_at__lte=now,
        ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now)).exists()

    def can_take_test(self):
        if self.is_blocked:
            return False
        return self.has_active_premium() or self.free_tests_taken < self.FREE_TEST_LIMIT

    def register_free_test_usage(self):
        if self.has_active_premium():
            return
        if self.free_tests_taken >= self.FREE_TEST_LIMIT:
            raise ValidationError(_("Free test limit has been reached."))
        self.free_tests_taken = models.F("free_tests_taken") + 1
        self.save(update_fields=("free_tests_taken", "updated_at"))
        self.refresh_from_db(fields=("free_tests_taken",))

    def mark_seen(self):
        self.last_seen_at = timezone.now()
        self.save(update_fields=("last_seen_at", "updated_at"))

    @property
    def is_registered(self):
        return bool(self.phone_number)

    def get_content_language(self):
        """Language code used for translated quiz content from the API."""
        if self.language in {self.Language.UZ, self.Language.UZ_CY, self.Language.RU}:
            return self.language
        return self.Language.UZ


class ActiveTelegramUser(TelegramUser):
    """Users who have not blocked the bot and can receive messages."""

    class Meta:
        proxy = True
        verbose_name = _("Active Telegram user")
        verbose_name_plural = _("Active Telegram users")


class BoundCard(TimeStampedModel):
    """Atmos card token saved only after a successful first charge (apply)."""

    user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name="bound_cards",
        verbose_name=_("user"),
    )
    card_id = models.CharField(_("Atmos card id"), max_length=64, db_index=True)
    card_token = models.CharField(_("card token"), max_length=255)
    masked_pan = models.CharField(_("masked pan"), max_length=32, blank=True)
    expiry = models.CharField(_("expiry"), max_length=8, blank=True)
    card_holder = models.CharField(_("card holder"), max_length=255, blank=True)
    phone = models.CharField(_("phone"), max_length=32, blank=True)
    is_active = models.BooleanField(_("is active"), default=True, db_index=True)
    removed_at = models.DateTimeField(_("removed at"), null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Bound card")
        verbose_name_plural = _("Bound cards")
        indexes = [
            models.Index(fields=("user", "is_active")),
        ]

    def __str__(self):
        return f"{self.masked_pan or self.card_id} ({self.user})"

    def mark_removed(self):
        """Remove card record (only active cards are kept in the database)."""
        self.delete()


class SubscriptionPlan(TimeStampedModel):
    class BillingPeriod(models.TextChoices):
        DAY = "day", _("Day")
        WEEK = "week", _("Week")
        MONTH = "month", _("Month")
        YEAR = "year", _("Year")
        LIFETIME = "lifetime", _("Lifetime")

    name = models.CharField(_("name"), max_length=120)
    description = models.TextField(_("description"), blank=True)
    price = models.DecimalField(_("price"), max_digits=12, decimal_places=2)
    currency = models.CharField(_("currency"), max_length=3, default="UZS")
    duration = models.PositiveIntegerField(_("duration"), help_text=_("Duration units."))
    period = models.CharField(
        _("period"),
        max_length=20,
        choices=BillingPeriod.choices,
        default=BillingPeriod.MONTH,
    )
    is_active = models.BooleanField(_("is active"), default=True)
    sort_order = models.PositiveSmallIntegerField(_("sort order"), default=0)

    class Meta:
        ordering = ("sort_order", "price")
        verbose_name = _("subscription plan")
        verbose_name_plural = _("subscription plans")

    def __str__(self):
        return f"{self.name} - {self.price} {self.currency}"

    def get_duration_delta(self):
        if self.period == self.BillingPeriod.DAY:
            return timedelta(days=self.duration)
        if self.period == self.BillingPeriod.WEEK:
            return timedelta(weeks=self.duration)
        if self.period == self.BillingPeriod.MONTH:
            test_minutes = getattr(settings, "DEENIFY_TEST_MONTHLY_RENEWAL_MINUTES", 0)
            if test_minutes > 0:
                return timedelta(minutes=test_minutes)
            return timedelta(days=30 * self.duration)
        if self.period == self.BillingPeriod.YEAR:
            return timedelta(days=365 * self.duration)
        return None


class UserPremiumSubscription(TimeStampedModel):
    class Source(models.TextChoices):
        PAYMENT = "payment", _("Payment")
        REFERRAL = "referral", _("Referral bonus")
        MANUAL = "manual", _("Manual")

    user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name="premium_subscriptions",
        verbose_name=_("user"),
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="premium_subscriptions",
        verbose_name=_("plan"),
        null=True,
        blank=True,
    )
    starts_at = models.DateTimeField(_("starts at"), default=timezone.now)
    expires_at = models.DateTimeField(_("expires at"), null=True, blank=True)
    is_active = models.BooleanField(_("is active"), default=True)
    auto_renew = models.BooleanField(
        _("auto renew"),
        default=False,
        help_text=_("Charge the bound card automatically when this period ends."),
    )
    bound_card = models.ForeignKey(
        "BoundCard",
        on_delete=models.SET_NULL,
        related_name="subscriptions",
        null=True,
        blank=True,
        verbose_name=_("bound card"),
    )
    source = models.CharField(
        _("source"),
        max_length=20,
        choices=Source.choices,
        default=Source.PAYMENT,
    )
    source_order = models.OneToOneField(
        "AtmosOrder",
        on_delete=models.SET_NULL,
        related_name="premium_subscription",
        null=True,
        blank=True,
        verbose_name=_("source order"),
    )

    class Meta:
        ordering = ("-starts_at",)
        verbose_name = _("premium subscription")
        verbose_name_plural = _("premium subscriptions")
        indexes = [
            models.Index(fields=("user", "is_active", "expires_at")),
        ]

    def __str__(self):
        plan_name = self.plan.name if self.plan else self.get_source_display()
        return f"{self.user} - {plan_name}"

    @property
    def is_current(self):
        now = timezone.now()
        return self.is_active and self.starts_at <= now and (
            self.expires_at is None or self.expires_at > now
        )

    @classmethod
    def current_queryset(cls):
        """Subscriptions that are active right now (same rules as ``is_current``)."""
        now = timezone.now()
        return cls.objects.filter(is_active=True, starts_at__lte=now).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
        )

    @classmethod
    def deactivate_superseded(cls, user, *, keep_pk):
        """Turn off stale rows after a renewal or new purchase extends coverage."""
        cls.objects.filter(user=user).exclude(pk=keep_pk).update(
            is_active=False,
            auto_renew=False,
            updated_at=timezone.now(),
        )


class AtmosOrder(TimeStampedModel):
    class Status(models.TextChoices):
        CREATED = "created", _("Created")
        PENDING = "pending", _("Pending")
        PAID = "paid", _("Paid")
        CANCELED = "canceled", _("Canceled")
        FAILED = "failed", _("Failed")
        EXPIRED = "expired", _("Expired")

    user = models.ForeignKey(
        TelegramUser,
        on_delete=models.PROTECT,
        related_name="atmos_orders",
        verbose_name=_("user"),
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="atmos_orders",
        verbose_name=_("plan"),
    )
    order_id = models.CharField(_("order id"), max_length=64, unique=True)
    merchant_order_id = models.CharField(
        _("merchant order id"),
        max_length=64,
        unique=True,
        blank=True,
        null=True,
    )
    atmos_transaction_id = models.CharField(
        _("Atmos transaction id"),
        max_length=128,
        blank=True,
        db_index=True,
    )
    amount = models.DecimalField(_("amount"), max_digits=12, decimal_places=2)
    currency = models.CharField(_("currency"), max_length=3, default="UZS")
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.CREATED,
        db_index=True,
    )
    paid_at = models.DateTimeField(_("paid at"), null=True, blank=True)
    expires_at = models.DateTimeField(_("expires at"), null=True, blank=True)
    success_notified = models.BooleanField(_("success notified"), default=False)
    is_auto_renewal = models.BooleanField(
        _("is auto renewal"),
        default=False,
        help_text=_("Charge created automatically by the recurring billing scheduler."),
    )
    bound_card = models.ForeignKey(
        "BoundCard",
        on_delete=models.SET_NULL,
        related_name="orders",
        null=True,
        blank=True,
        verbose_name=_("bound card"),
    )
    payment_url = models.URLField(_("payment url"), max_length=500, blank=True)
    request_payload = models.JSONField(_("request payload"), default=dict, blank=True)
    response_payload = models.JSONField(_("response payload"), default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Atmos order")
        verbose_name_plural = _("Atmos orders")
        indexes = [
            models.Index(fields=("user", "status")),
            models.Index(fields=("order_id", "status")),
        ]

    def __str__(self):
        return f"{self.merchant_order_id or self.order_id} - {self.amount} {self.currency}"

    def save(self, *args, **kwargs):
        if not self.order_id:
            self.order_id = uuid4().hex
        if not self.merchant_order_id:
            self.merchant_order_id = self.order_id
        super().save(*args, **kwargs)

    @property
    def is_paid(self):
        return self.status == self.Status.PAID

    def mark_as_paid(self, atmos_transaction_id="", payload=None):
        with transaction.atomic():
            now = timezone.now()
            order = type(self).objects.select_for_update().get(pk=self.pk)
            if order.status == order.Status.PAID:
                return order.premium_subscription

            order.status = order.Status.PAID
            order.paid_at = now
            if atmos_transaction_id:
                order.atmos_transaction_id = atmos_transaction_id
            if payload:
                order.response_payload = payload
            order.save(
                update_fields=(
                    "status",
                    "paid_at",
                    "atmos_transaction_id",
                    "response_payload",
                    "updated_at",
                )
            )

            duration_delta = order.plan.get_duration_delta() if order.plan else None

            def _apply_payment_extension(subscription):
                if subscription.expires_at is None:
                    UserPremiumSubscription.deactivate_superseded(
                        order.user, keep_pk=subscription.pk
                    )
                    return subscription
                if duration_delta is None:
                    subscription.expires_at = None
                elif subscription.expires_at <= now:
                    subscription.expires_at = now + duration_delta
                else:
                    subscription.expires_at = subscription.expires_at + duration_delta
                if order.plan_id:
                    subscription.plan = order.plan
                if order.bound_card_id:
                    subscription.bound_card = order.bound_card
                    subscription.auto_renew = True
                subscription.source = UserPremiumSubscription.Source.PAYMENT
                subscription.source_order = order
                subscription.is_active = True
                subscription.save(
                    update_fields=(
                        "expires_at",
                        "plan",
                        "bound_card",
                        "auto_renew",
                        "source",
                        "source_order",
                        "is_active",
                        "updated_at",
                    )
                )
                UserPremiumSubscription.deactivate_superseded(
                    order.user, keep_pk=subscription.pk
                )
                return subscription

            # Extend the user's CURRENT active subscription in place so repeated
            # purchases (and renewals) accumulate onto one row instead of creating
            # separate, future-dated periods that the status view would ignore.
            active_subscription = (
                UserPremiumSubscription.objects.select_for_update()
                .filter(user=order.user, is_active=True, starts_at__lte=now)
                .filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now))
                .order_by("-expires_at")
                .first()
            )
            if active_subscription:
                return _apply_payment_extension(active_subscription)

            # Late auto-renewal: extend the expired period row instead of duplicating.
            if order.is_auto_renewal:
                renewal_target = (
                    UserPremiumSubscription.objects.select_for_update()
                    .filter(user=order.user, is_active=True, expires_at__lte=now)
                    .order_by("-expires_at")
                    .first()
                )
                if renewal_target:
                    return _apply_payment_extension(renewal_target)

            # No active coverage: start a fresh period from now.
            UserPremiumSubscription.objects.filter(
                user=order.user, is_active=True, auto_renew=True
            ).update(auto_renew=False)
            starts_at = now
            expires_at = None if duration_delta is None else starts_at + duration_delta
            subscription = UserPremiumSubscription.objects.create(
                user=order.user,
                plan=order.plan,
                starts_at=starts_at,
                expires_at=expires_at,
                is_active=True,
                auto_renew=bool(order.bound_card_id),
                bound_card=order.bound_card,
                source=UserPremiumSubscription.Source.PAYMENT,
                source_order=order,
            )
            UserPremiumSubscription.deactivate_superseded(order.user, keep_pk=subscription.pk)
            return subscription

    @classmethod
    def create_for_plan(cls, user, plan):
        return cls.objects.create(
            user=user,
            plan=plan,
            order_id=uuid4().hex,
            merchant_order_id=uuid4().hex,
            amount=plan.price,
            currency=plan.currency,
        )


class AtmosTransaction(TimeStampedModel):
    class Status(models.TextChoices):
        INITIATED = "initiated", _("Initiated")
        SUCCESS = "success", _("Success")
        FAILED = "failed", _("Failed")
        CANCELED = "canceled", _("Canceled")
        REVERSED = "reversed", _("Reversed")

    order = models.ForeignKey(
        AtmosOrder,
        on_delete=models.CASCADE,
        related_name="transactions",
        verbose_name=_("order"),
    )
    transaction_id = models.CharField(_("transaction id"), max_length=128, db_index=True)
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.INITIATED,
        db_index=True,
    )
    amount = models.DecimalField(_("amount"), max_digits=12, decimal_places=2)
    currency = models.CharField(_("currency"), max_length=3, default="UZS")
    provider_payload = models.JSONField(_("provider payload"), default=dict, blank=True)
    performed_at = models.DateTimeField(_("performed at"), null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Atmos transaction")
        verbose_name_plural = _("Atmos transactions")
        constraints = [
            models.UniqueConstraint(
                fields=("order", "transaction_id"),
                name="unique_atmos_transaction_per_order",
            ),
        ]
        indexes = [
            models.Index(fields=("transaction_id", "status")),
        ]

    def __str__(self):
        return f"{self.transaction_id} - {self.status}"

    def mark_as_success(self, payload=None):
        self.status = self.Status.SUCCESS
        self.performed_at = timezone.now()
        if payload:
            self.provider_payload = payload
        self.save(
            update_fields=("status", "performed_at", "provider_payload", "updated_at")
        )
        return self.order.mark_as_paid(
            atmos_transaction_id=self.transaction_id,
            payload=payload or self.provider_payload,
        )


class Feedback(TimeStampedModel):
    """User feedback collected when a user declines or cancels premium."""

    class Reason(models.TextChoices):
        EXPENSIVE = "expensive", _("Too expensive")
        NOT_NOW = "not_now", _("Not needed now")
        TRUST = "trust", _("Trust / security")
        HARD_PAYMENT = "hard_payment", _("Payment was difficult")
        OTHER = "other", _("Other")

    class Context(models.TextChoices):
        DECLINED = "declined", _("Declined the offer")
        CANCELED = "canceled", _("Canceled subscription")

    user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name="feedbacks",
        verbose_name=_("user"),
    )
    context = models.CharField(
        _("context"),
        max_length=20,
        choices=Context.choices,
        default=Context.DECLINED,
        db_index=True,
    )
    reason = models.CharField(
        _("reason"),
        max_length=20,
        choices=Reason.choices,
        blank=True,
    )
    text = models.TextField(_("text"), blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Feedback")
        verbose_name_plural = _("Feedback")

    def __str__(self):
        return f"{self.user} - {self.get_context_display()} - {self.reason or 'text'}"


def get_atmos_config():
    return {
        "store_id": settings.ATMOS_STORE_ID,
        "consumer_key": settings.ATMOS_CONSUMER_KEY,
        "consumer_secret": settings.ATMOS_CONSUMER_SECRET,
        "callback_url": settings.ATMOS_CALLBACK_URL,
        "return_url": settings.ATMOS_RETURN_URL,
        "base_url": settings.ATMOS_BASE_URL,
    }
