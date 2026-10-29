from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from users.models import ClickRenewal
from users.recurring import available, charge_due


class Command(BaseCommand):
    help = "Process due, consented Click renewals. Uncertain debits are never resubmitted."

    def handle(self, *args, **options):
        if not available():
            raise CommandError("Click renewals are disabled or credentials/encryption key are missing.")
        ids = ClickRenewal.objects.filter(enabled=True, verified=True, next_charge_at__lte=timezone.now()).values_list("pk", flat=True)
        for renewal_id in ids.iterator():
            self.stdout.write(f"Renewal {renewal_id}: {charge_due(renewal_id)}")
