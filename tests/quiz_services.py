from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Prefetch

from .exceptions import PaymentRequired, QuizCompleted
from .models import Answer, Test, TestCategory, UserAnsweredTest


def _first_round_easy_count():
    return settings.DEENIFY_QUIZ_FIRST_ROUND_EASY_COUNT


def _subscription_required():
    return settings.DEENIFY_QUIZ_SUBSCRIPTION_REQUIRED


def get_default_category():
    return TestCategory.get_default()


def get_active_tests_queryset():
    return Test.objects.filter(
        is_active=True,
        category=get_default_category(),
    )


def get_total_active_questions():
    return get_active_tests_queryset().count()


def get_answered_test_ids(user, round_number=None):
    round_number = round_number or user.quiz_round
    active_test_ids = get_active_tests_queryset().values("id")
    return set(
        UserAnsweredTest.objects.filter(
            user=user,
            round=round_number,
            test_id__in=active_test_ids,
        ).values_list("test_id", flat=True)
    )


def get_quiz_progress(user):
    total = get_total_active_questions()
    answered_ids = get_answered_test_ids(user)
    answered_count = len(answered_ids)
    free_limit = _first_round_easy_count()
    return {
        "quiz_round": user.quiz_round,
        "total_questions": total,
        "answered_count": answered_count,
        "remaining_count": max(total - answered_count, 0),
        "is_round_complete": total > 0 and answered_count >= total,
        "free_limit": free_limit,
        "needs_subscription": _needs_subscription(user, answered_count, free_limit),
        "is_premium": user.has_active_premium(),
    }


def _needs_subscription(user, answered_count, free_limit):
    if not _subscription_required():
        return False
    if user.has_active_premium():
        return False
    if user.quiz_round > 1:
        return True
    return answered_count >= free_limit


def _free_tier_exhausted(user):
    """True when a non-premium user has used all free questions (lifetime)."""
    if not _subscription_required() or user.has_active_premium():
        return False
    free_limit = _first_round_easy_count()
    if user.free_tests_taken >= free_limit:
        return True
    return len(get_answered_test_ids(user)) >= free_limit


def _record_free_question_usage(user):
    if not _subscription_required() or user.has_active_premium():
        return
    user.register_free_test_usage()


def _question_queryset():
    return get_active_tests_queryset().prefetch_related(
        Prefetch("answers", queryset=Answer.objects.order_by("sort_order", "id"))
    )


def get_next_question(user):
    if user.is_blocked:
        raise PermissionDenied("User is blocked.")

    progress = get_quiz_progress(user)
    if progress["is_round_complete"]:
        raise QuizCompleted()

    if progress["needs_subscription"]:
        raise PaymentRequired("Subscription is required to continue.")

    answered_ids = get_answered_test_ids(user)
    queryset = _question_queryset().exclude(id__in=answered_ids)

    if not queryset.exists():
        raise QuizCompleted()

    answered_count = len(answered_ids)
    easy_limit = _first_round_easy_count()
    if user.quiz_round == 1 and answered_count < easy_limit:
        easy_pool = queryset.filter(level=Test.Level.EASY)
        pool = easy_pool if easy_pool.exists() else queryset
    else:
        pool = queryset

    return pool.order_by("?").first()


@transaction.atomic
def submit_quiz_answer(*, user, test_id, answer_id):
    if user.is_blocked:
        raise PermissionDenied("User is blocked.")

    answered_ids = get_answered_test_ids(user)
    if test_id in answered_ids:
        raise ValidationError("This question is already completed.")

    progress = get_quiz_progress(user)
    if progress["needs_subscription"]:
        raise PaymentRequired("Subscription is required to continue.")

    test = _question_queryset().filter(id=test_id).first()
    if not test:
        raise LookupError("Test not found.")

    answer = Answer.objects.filter(id=answer_id, test=test).first()
    if not answer:
        raise ValidationError("Answer does not belong to this test.")

    is_correct = answer.is_correct
    UserAnsweredTest.objects.create(user=user, test=test, round=user.quiz_round)
    _record_free_question_usage(user)
    progress = get_quiz_progress(user)

    return {
        "is_correct": is_correct,
        "explanation": test.explanation,
        "progress": progress,
        "is_round_complete": progress["is_round_complete"],
    }


@transaction.atomic
def reset_quiz_progress(user):
    """Clear all answered questions and start again from question 1."""
    if _free_tier_exhausted(user):
        raise PaymentRequired("Subscription is required to restart.")

    UserAnsweredTest.objects.filter(user=user).delete()
    if user.quiz_round != 1:
        user.quiz_round = 1
        user.save(update_fields=("quiz_round", "updated_at"))
    return get_quiz_progress(user)


@transaction.atomic
def start_new_quiz_round(user):
    if _free_tier_exhausted(user):
        raise PaymentRequired("Subscription is required to start a new round.")

    total = get_total_active_questions()
    answered_count = len(get_answered_test_ids(user))
    if total == 0 or answered_count < total:
        raise ValidationError("Current round is not finished yet.")

    user.quiz_round += 1
    user.save(update_fields=("quiz_round", "updated_at"))
    return get_quiz_progress(user)
