"""Remove all payment-related test data before prod go-live.

Deletes: premium subscriptions, Atmos orders/transactions, bound cards, feedback.
Telegram users and quiz progress are kept.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from users.models import (
    AtmosOrder,
    AtmosTransaction,
    BoundCard,
    Feedback,
    UserPremiumSubscription,
)


class Command(BaseCommand):
    help = "Delete all payment test data (orders, transactions, cards, subscriptions, feedback)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show row counts only; do not delete.",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Required to actually delete (ignored with --dry-run).",
        )

    def handle(self, *args, **options):
        counts = {
            "premium_subscriptions": UserPremiumSubscription.objects.count(),
            "atmos_orders": AtmosOrder.objects.count(),
            "atmos_transactions": AtmosTransaction.objects.count(),
            "bound_cards": BoundCard.objects.count(),
            "feedback": Feedback.objects.count(),
        }

        self.stdout.write("Payment data to remove:")
        for key, value in counts.items():
            self.stdout.write(f"  {key}: {value}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — nothing deleted."))
            return

        if not options["confirm"]:
            raise CommandError("Pass --confirm to delete, or --dry-run to preview.")

        with transaction.atomic():
            deleted_subs, _ = UserPremiumSubscription.objects.all().delete()
            deleted_tx, _ = AtmosTransaction.objects.all().delete()
            deleted_orders, _ = AtmosOrder.objects.all().delete()
            deleted_cards, _ = BoundCard.objects.all().delete()
            deleted_feedback, _ = Feedback.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(
                "Deleted: "
                f"{deleted_subs} subscription(s), "
                f"{deleted_orders} order(s), "
                f"{deleted_tx} transaction(s), "
                f"{deleted_cards} card(s), "
                f"{deleted_feedback} feedback(s)."
            )
        )
