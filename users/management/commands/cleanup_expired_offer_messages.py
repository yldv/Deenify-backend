"""Delete subscription catalog bot messages older than OFFER_MESSAGE_TTL_SECONDS (default 1 hour).

Runs every 15 minutes via systemd timer. Paid users have offer refs cleared on success.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from users.services import cleanup_expired_offer_messages


class Command(BaseCommand):
    help = "Remove expired subscription offer messages from Telegram chats."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ttl-seconds",
            type=int,
            default=None,
            help=(
                "Delete offers older than N seconds "
                f"(default: {getattr(settings, 'OFFER_MESSAGE_TTL_SECONDS', 3600)})."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many users would be affected without deleting messages.",
        )

    def handle(self, *args, **options):
        result = cleanup_expired_offer_messages(
            ttl_seconds=options["ttl_seconds"],
            dry_run=options["dry_run"],
        )
        if result.get("dry_run"):
            self.stdout.write(f"Would clear offer messages for {result['users']} user(s).")
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Cleared offer messages for {result.get('cleared', 0)} of "
                f"{result.get('users', 0)} user(s)."
            )
        )
