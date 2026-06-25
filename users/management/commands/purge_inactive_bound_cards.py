"""Delete inactive (uzilgan) bound card rows left from older soft-delete logic."""

from django.core.management.base import BaseCommand

from users.models import BoundCard


class Command(BaseCommand):
    help = "Remove all bound cards with is_active=False (admin shows only active cards)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show count only.",
        )

    def handle(self, *args, **options):
        count = BoundCard.objects.filter(is_active=False).count()
        if options["dry_run"]:
            self.stdout.write(f"Would delete {count} inactive bound card(s).")
            return
        deleted, _ = BoundCard.objects.filter(is_active=False).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} inactive bound card(s)."))
