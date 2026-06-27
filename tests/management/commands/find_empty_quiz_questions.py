from django.core.management.base import BaseCommand

from tests.models import Test
from tests.services.quiz_content import (
    answers_with_empty_text,
    count_poll_ready_answers,
    is_test_poll_ready,
    resolve_localized_text,
)


class Command(BaseCommand):
    help = (
        "List quiz answers with no text in any language (uz/ru/uz_cy). "
        "Russian is optional — empty rows are usually ghost variants from admin."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Delete incorrect answers with empty text when the test still has >=2 filled answers.",
        )

    def handle(self, *args, **options):
        broken_questions = []
        empty_answer_rows = []
        deleted = 0
        skipped = []

        for test in Test.objects.filter(is_active=True).prefetch_related("answers"):
            question = resolve_localized_text(test, "question")
            empty_answers = answers_with_empty_text(test)
            if not question or len(test.answers.all()) < 2 or empty_answers:
                broken_questions.append((test, question, empty_answers))
            for answer in empty_answers:
                empty_answer_rows.append((test, answer))
                if not options["fix"]:
                    continue
                if answer.is_correct:
                    skipped.append(
                        f"answer_id={answer.pk} test_id={test.pk} (correct answer — fill in admin)"
                    )
                    continue
                remaining = test.answers.exclude(pk=answer.pk)
                if remaining.count() < 2:
                    skipped.append(
                        f"answer_id={answer.pk} test_id={test.pk} (would leave <2 answers)"
                    )
                    continue
                if count_poll_ready_answers(test) < 2:
                    skipped.append(
                        f"answer_id={answer.pk} test_id={test.pk} (would leave <2 non-empty answers)"
                    )
                    continue
                answer_id = answer.pk
                test_id = test.pk
                answer.delete()
                deleted += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Deleted answer_id={answer_id} from test_id={test_id}"
                    )
                )

        if options["fix"] and deleted:
            broken_questions = []
            empty_answer_rows = []
            for test in Test.objects.filter(is_active=True).prefetch_related("answers"):
                question = resolve_localized_text(test, "question")
                empty_answers = answers_with_empty_text(test)
                if not question or len(test.answers.all()) < 2 or empty_answers:
                    broken_questions.append((test, question, empty_answers))
                for answer in empty_answers:
                    empty_answer_rows.append((test, answer))

        poll_ready = sum(
            1
            for test in Test.objects.filter(is_active=True).prefetch_related("answers")
            if is_test_poll_ready(test)
        )

        self.stdout.write(
            f"Broken questions (will fail or skip in bot): {len(broken_questions)}"
        )
        self.stdout.write(f"Poll-ready active questions: {poll_ready}")
        self.stdout.write(f"Answers with empty text (all langs): {len(empty_answer_rows)}")

        for test, question, empty_answers in broken_questions[:50]:
            preview = (question or "EMPTY")[:60]
            empty_ids = ", ".join(str(answer.pk) for answer in empty_answers) or "-"
            self.stdout.write(
                f"  test_id={test.pk} sort={test.sort_order} "
                f"answers_ready={count_poll_ready_answers(test)}/"
                f"{test.answers.count()} empty_answer_ids=[{empty_ids}] "
                f"question={preview!r}"
            )
        if len(broken_questions) > 50:
            self.stdout.write(f"  ... and {len(broken_questions) - 50} more")

        if empty_answer_rows:
            self.stdout.write("")
            self.stdout.write(
                "Empty answer variants (no lotin/kirill/rus — not 'missing Russian'):"
            )
            for test, answer in empty_answer_rows:
                self.stdout.write(
                    f"  answer_id={answer.pk} test_id={test.pk} "
                    f"is_correct={answer.is_correct} sort={answer.sort_order}"
                )

        if options["fix"]:
            self.stdout.write("")
            self.stdout.write(f"Deleted: {deleted}")
            for line in skipped:
                self.stdout.write(self.style.WARNING(f"Skipped: {line}"))
