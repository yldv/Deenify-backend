from django.core.management.base import BaseCommand

from users.models import TelegramUser


class Command(BaseCommand):
    help = "List Telegram users who chose a language but have no phone number."

    def handle(self, *args, **options):
        users = TelegramUser.objects.filter(phone_number="").order_by("-created_at")
        count = users.count()
        if not count:
            self.stdout.write(self.style.SUCCESS("All users have a phone number."))
            return

        self.stdout.write(f"Users without phone: {count}")
        for user in users[:50]:
            self.stdout.write(
                f"  id={user.telegram_id} username={user.username or '-'} "
                f"name={user.full_name or '-'} lang={user.language}"
            )
        if count > 50:
            self.stdout.write(f"  ... and {count - 50} more")
