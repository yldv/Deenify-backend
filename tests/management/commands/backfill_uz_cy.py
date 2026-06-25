from django.core.management.base import BaseCommand
from django.db import transaction

from bot.uz_cyrillic import latin_to_cyrillic
from tests.models import Answer, Test


class Command(BaseCommand):
    help = "Fill empty uz_cy fields from uz (latin → cyrillic) for tests and answers."

    @transaction.atomic
    def handle(self, *args, **options):
        test_fields = ("title", "question", "description")
        answer_fields = ("text",)
        tests_updated = 0
        answers_updated = 0

        for test in Test.objects.all():
            changed = []
            for base in test_fields:
                cy_field = f"{base}_uz_cy"
                uz_field = f"{base}_uz"
                if not hasattr(test, cy_field):
                    continue
                cy_val = (getattr(test, cy_field) or "").strip()
                uz_val = (getattr(test, uz_field) or getattr(test, base) or "").strip()
                if cy_val or not uz_val:
                    continue
                setattr(test, cy_field, latin_to_cyrillic(uz_val))
                changed.append(cy_field)
            if changed:
                test.save(update_fields=changed + ["updated_at"])
                tests_updated += 1

        for answer in Answer.objects.all():
            uz_val = (answer.text_uz or answer.text or "").strip()
            cy_val = (answer.text_uz_cy or "").strip()
            if cy_val or not uz_val:
                continue
            answer.text_uz_cy = latin_to_cyrillic(uz_val)
            answer.save(update_fields=("text_uz_cy", "updated_at"))
            answers_updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill done: {tests_updated} tests, {answers_updated} answers updated."
            )
        )
