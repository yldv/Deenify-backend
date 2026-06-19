"""Delete unpaid Atmos orders older than the retention window.

Paid orders are kept forever. Transactions are removed via CASCADE.
Run daily via systemd timer, or once before prod with --all-unpaid.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from users.services import cleanup_stale_atmos_orders


class Command(BaseCommand):
    help = "Remove stale unpaid Atmos orders and their transactions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help=(
                "Delete unpaid orders older than N days "
                f"(default: {getattr(settings, 'ATMOS_STALE_ORDER_RETENTION_DAYS', 1)})."
            ),
        )
        parser.add_argument(
            "--all-unpaid",
            action="store_true",
            help="Delete ALL unpaid orders regardless of age (one-time prod cleanup).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many rows would be deleted without deleting.",
        )

    def handle(self, *args, **options):
        result = cleanup_stale_atmos_orders(
            days=options["days"],
            all_unpaid=options["all_unpaid"],
            dry_run=options["dry_run"],
        )
        if result.get("dry_run"):
            self.stdout.write(
                f"Would delete {result['orders']} order(s) "
                f"and {result['transactions']} transaction(s)."
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {result['orders']} order(s) "
                f"and {result['transactions']} transaction(s)."
            )
        )
