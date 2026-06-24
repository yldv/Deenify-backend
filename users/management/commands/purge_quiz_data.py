"""Delete all quiz questions, answer options, and user quiz progress."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from tests.models import Answer, Test, UserAnsweredTest
from users.models import TelegramUser


class Command(BaseCommand):
    help = "Delete ALL test questions (Test savollari), answers (Javob variantlari), user progress."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--confirm", action="store_true")

    def handle(self, *args, **options):
        counts = {
            "tests": Test.objects.count(),
            "answers": Answer.objects.count(),
            "user_answered_tests": UserAnsweredTest.objects.count(),
        }
        self.stdout.write("Quiz data:")
        for key, value in counts.items():
            self.stdout.write(f"  {key}: {value}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — nothing deleted."))
            return
        if not options["confirm"]:
            raise CommandError("Pass --confirm to delete.")

        with transaction.atomic():
            n_progress, _ = UserAnsweredTest.objects.all().delete()
            n_answers, _ = Answer.objects.all().delete()
            n_tests, _ = Test.objects.all().delete()
            n_users = TelegramUser.objects.update(quiz_round=1, free_tests_taken=0)

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {n_tests} question(s), {n_answers} answer(s), "
                f"{n_progress} user progress row(s). "
                f"Reset {n_users} user(s) (quiz_round, free_tests_taken)."
            )
        )
