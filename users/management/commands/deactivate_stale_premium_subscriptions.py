from django.core.management.base import BaseCommand
from django.utils import timezone

from users.models import UserPremiumSubscription


class Command(BaseCommand):
    help = "Deactivate premium subscriptions that are no longer current (admin cleanup)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many rows would be deactivated.",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        stale = UserPremiumSubscription.objects.filter(is_active=True).exclude(
            pk__in=UserPremiumSubscription.current_queryset().values("pk")
        )
        count = stale.count()
        if options["dry_run"]:
            self.stdout.write(f"Would deactivate {count} stale subscription(s).")
            for sub in stale.order_by("-starts_at")[:20]:
                self.stdout.write(
                    f"  user={sub.user_id} sub={sub.pk} expires={sub.expires_at}"
                )
            return

        updated = stale.update(
            is_active=False,
            auto_renew=False,
            updated_at=now,
        )
        self.stdout.write(self.style.SUCCESS(f"Deactivated {updated} stale subscription(s)."))
