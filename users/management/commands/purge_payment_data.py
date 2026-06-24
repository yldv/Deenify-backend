"""Remove test/sandbox data before prod go-live.

Deletes payment records, quiz questions/answers, and user quiz progress.
Keeps: Telegram users, subscription plans, test categories.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from tests.models import Answer, Test, UserAnsweredTest
from users.models import (
    AtmosOrder,
    AtmosTransaction,
    BoundCard,
    Feedback,
    TelegramUser,
    UserPremiumSubscription,
)


class Command(BaseCommand):
    help = (
        "Delete payment + quiz sandbox data "
        "(orders, subscriptions, cards, feedback, questions, answers, user progress)."
    )

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
            "user_answered_tests": UserAnsweredTest.objects.count(),
            "answers": Answer.objects.count(),
            "tests": Test.objects.count(),
            "users_with_quiz_round_gt_1": TelegramUser.objects.filter(quiz_round__gt=1).count(),
        }

        self.stdout.write("Rows to remove / reset:")
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

            deleted_progress, _ = UserAnsweredTest.objects.all().delete()
            deleted_answers, _ = Answer.objects.all().delete()
            deleted_tests, _ = Test.objects.all().delete()

            users_reset = TelegramUser.objects.update(quiz_round=1, free_tests_taken=0)

        self.stdout.write(
            self.style.SUCCESS(
                "Deleted: "
                f"{deleted_subs} subscription(s), "
                f"{deleted_orders} order(s), "
                f"{deleted_tx} transaction(s), "
                f"{deleted_cards} card(s), "
                f"{deleted_feedback} feedback(s), "
                f"{deleted_progress} user answer(s), "
                f"{deleted_tests} question(s), "
                f"{deleted_answers} answer option(s). "
                f"Reset quiz_round for {users_reset} user(s)."
            )
        )
