"""Recurring billing: charge bound cards for subscriptions that are about to expire.

Atmos token charges are merchant-initiated (pull model), so this command should run
on a daily schedule (systemd timer or cron). It renews each user's latest auto-renew
subscription a few days before it expires, using the stored card token.

Idempotency / no double-charge: a successful renewal extends the current active
subscription in place (its ``expires_at`` moves forward by one period), so it falls
outside the renewal window and is not picked up again. If a subscription is renewed
only after it already expired, ``mark_as_paid`` starts a fresh period and disables
auto-renew on the stale row, so each user keeps at most one auto-renewing subscription.
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from users.models import AtmosOrder, UserPremiumSubscription
from users.services import charge_subscription

# Skip a new renewal charge while another auto-renewal order is still in flight.
RENEWAL_IN_FLIGHT_HOURS = 6


class Command(BaseCommand):
    help = "Charge bound cards to renew subscriptions that are about to expire."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List due subscriptions without charging.",
        )
        parser.add_argument(
            "--lead-days",
            type=int,
            default=getattr(settings, "ATMOS_RENEW_LEAD_DAYS", 1),
            help="Renew this many days before the subscription expires.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        lead_days = options["lead_days"]
        fail_grace = getattr(settings, "ATMOS_RENEW_FAIL_GRACE_DAYS", 3)
        now = timezone.now()
        threshold = now + timedelta(days=lead_days)
        in_flight_since = now - timedelta(hours=RENEWAL_IN_FLIGHT_HOURS)

        due_ids = list(
            UserPremiumSubscription.objects.filter(
                is_active=True,
                auto_renew=True,
                plan__isnull=False,
                expires_at__isnull=False,
                expires_at__lte=threshold,
            )
            .order_by("expires_at")
            .values_list("pk", flat=True)
        )

        self.stdout.write(
            f"Found {len(due_ids)} subscription(s) due for renewal (<= {threshold:%Y-%m-%d %H:%M})."
        )
        charged = failed = skipped = 0

        for subscription_id in due_ids:
            charge_target = None
            label = ""

            with transaction.atomic():
                subscription = (
                    UserPremiumSubscription.objects.select_for_update()
                    .select_related("user", "plan", "bound_card")
                    .filter(
                        pk=subscription_id,
                        is_active=True,
                        auto_renew=True,
                        plan__isnull=False,
                        expires_at__isnull=False,
                        expires_at__lte=threshold,
                    )
                    .first()
                )
                if not subscription:
                    continue

                user = subscription.user
                card = subscription.bound_card
                label = f"user={user.telegram_id} sub={subscription.pk}"

                if not card or not card.is_active or not card.card_token:
                    self.stdout.write(f"  SKIP {label}: no active bound card; disabling auto-renew.")
                    if not dry_run:
                        subscription.auto_renew = False
                        subscription.save(update_fields=("auto_renew", "updated_at"))
                    skipped += 1
                    continue

                in_flight = AtmosOrder.objects.filter(
                    user=user,
                    is_auto_renewal=True,
                    status__in=(AtmosOrder.Status.CREATED, AtmosOrder.Status.PENDING),
                    created_at__gte=in_flight_since,
                ).exists()
                if in_flight:
                    self.stdout.write(f"  SKIP {label}: renewal payment already in progress.")
                    skipped += 1
                    continue

                if dry_run:
                    self.stdout.write(
                        f"  DUE  {label} plan={subscription.plan_id} "
                        f"expires={subscription.expires_at:%Y-%m-%d}"
                    )
                    continue

                charge_target = (user, subscription.plan, card, subscription)

            if not charge_target:
                continue

            user, plan, card, subscription = charge_target
            result = charge_subscription(
                user=user,
                plan=plan,
                bound_card=card,
                is_auto_renewal=True,
            )

            if result.get("ok"):
                charged += 1
                self.stdout.write(self.style.SUCCESS(f"  OK   {label}: renewed."))
                continue

            failed += 1
            error = result.get("error") or "unknown error"
            expired_for = now - subscription.expires_at
            if expired_for > timedelta(days=fail_grace):
                self.stdout.write(
                    self.style.ERROR(f"  FAIL {label}: {error}; grace exceeded, disabling auto-renew.")
                )
                subscription.auto_renew = False
                subscription.save(update_fields=("auto_renew", "updated_at"))
                self._notify_failure(user)
            else:
                self.stdout.write(
                    self.style.WARNING(f"  FAIL {label}: {error}; will retry next run.")
                )

        self.stdout.write(
            f"Done. charged={charged} failed={failed} skipped={skipped} dry_run={dry_run}."
        )

    def _notify_failure(self, user):
        try:
            from bot.texts import get_text
            from users.notifications import send_telegram_message

            language = user.get_content_language()
            send_telegram_message(
                chat_id=user.telegram_id,
                text=get_text(language, "subscription_renewal_failed"),
            )
        except Exception:  # noqa: BLE001
            pass
