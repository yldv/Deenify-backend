from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from users.models import TelegramUser

from .models import Answer, Test, UserTestAnswer, UserTestSession


class PaymentRequired(Exception):
    pass


VALID_TEST_TYPES = {"easy", "medium", "hard", "mixed"}
MAX_SESSION_QUESTIONS = 10


def get_user_by_telegram_id(telegram_id):
    return TelegramUser.objects.filter(telegram_id=telegram_id).first()


def get_session_stats(session):
    return {
        "total_questions": session.total_questions,
        "correct_answers": session.correct_answers,
        "wrong_answers": session.wrong_answers,
        "score_percent": session.score_percent,
    }


def check_user_can_use_tests(user):
    if user.is_blocked:
        raise PermissionDenied("User is blocked.")
    if not user.has_active_premium() and user.free_tests_taken >= user.FREE_TEST_LIMIT:
        raise PaymentRequired("Free test limit has been reached.")


def pick_tests(*, test_type, limit):
    queryset = Test.objects.filter(is_active=True).prefetch_related("answers")
    if test_type != "mixed":
        queryset = queryset.filter(level=test_type)
    return list(queryset.order_by("?")[:limit])


@transaction.atomic
def start_test_session(*, user, test_type):
    if test_type not in VALID_TEST_TYPES:
        raise ValidationError("Invalid test_type.")
    check_user_can_use_tests(user)

    if user.has_active_premium():
        question_limit = MAX_SESSION_QUESTIONS
    else:
        question_limit = min(
            MAX_SESSION_QUESTIONS,
            user.FREE_TEST_LIMIT - user.free_tests_taken,
        )
    selected_tests = pick_tests(test_type=test_type, limit=question_limit)
    session = UserTestSession.objects.create(
        user=user,
        level="" if test_type == "mixed" else test_type,
        total_questions=0,
        correct_answers=0,
        wrong_answers=0,
    )
    session.tests.set(selected_tests)
    return session, selected_tests


@transaction.atomic
def submit_session_answer(*, session, user, test_id, answer_id):
    if session.user_id != user.id:
        raise PermissionDenied("Session does not belong to this user.")
    if session.status != UserTestSession.Status.STARTED:
        raise ValidationError("Session is not active.")
    check_user_can_use_tests(user)

    test = (
        Test.objects.filter(id=test_id)
        .prefetch_related("answers")
        .first()
    )
    if not test:
        raise LookupError("Test not found.")
    if not session.tests.filter(id=test.id).exists():
        raise ValidationError("Test is not part of this session.")

    answer = Answer.objects.filter(id=answer_id, test=test).first()
    if not answer:
        raise ValidationError("Answer does not belong to this test.")
    if UserTestAnswer.objects.filter(session=session, test=test).exists():
        raise ValidationError("This test already has an answer in this session.")

    user_answer = UserTestAnswer.objects.create(
        session=session,
        test=test,
        selected_answer=answer,
    )
    if not user.has_active_premium():
        user.register_free_test_usage()

    answered = session.user_answers.all()
    session.total_questions = answered.count()
    session.correct_answers = answered.filter(is_correct=True).count()
    session.wrong_answers = session.total_questions - session.correct_answers
    session.save(
        update_fields=(
            "total_questions",
            "correct_answers",
            "wrong_answers",
            "updated_at",
        )
    )
    correct_answer = test.get_correct_answer()
    return user_answer, correct_answer, session


@transaction.atomic
def finish_session(*, session, user):
    if session.user_id != user.id:
        raise PermissionDenied("Session does not belong to this user.")
    session.complete()
    session.completed_at = session.completed_at or timezone.now()
    return session
