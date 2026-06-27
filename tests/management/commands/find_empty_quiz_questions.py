from django.core.management.base import BaseCommand

from tests.models import Answer, Test
from tests.services.quiz_content import count_poll_ready_answers, resolve_localized_text


class Command(BaseCommand):
    help = "List active quiz questions/answers with empty text (Telegram poll will fail)."

    def handle(self, *args, **options):
        broken_questions = []
        broken_answers = 0

        for test in Test.objects.filter(is_active=True).prefetch_related("answers"):
            question = resolve_localized_text(test, "question")
            ready = count_poll_ready_answers(test)
            if not question or ready < 2:
                broken_questions.append((test, question, ready))
            for answer in test.answers.all():
                if not resolve_localized_text(answer, "text"):
                    broken_answers += 1

        self.stdout.write(
            f"Broken questions (empty text or <2 answers): {len(broken_questions)}"
        )
        self.stdout.write(f"Answers with empty text (all langs): {broken_answers}")

        for test, question, ready in broken_questions[:50]:
            preview = (question or "EMPTY")[:60]
            self.stdout.write(
                f"  test_id={test.pk} sort={test.sort_order} "
                f"answers_ready={ready} question={preview!r}"
            )
        if len(broken_questions) > 50:
            self.stdout.write(f"  ... and {len(broken_questions) - 50} more")
