import json
from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from tests.models import Test, UserAnsweredTest
from users.models import AtmosOrder, TelegramUser
from users.services import get_admin_statistics


def _last_n_days_labels(n: int = 7) -> list[str]:
    today = timezone.localdate()
    return [
        (today - timedelta(days=n - 1 - offset)).strftime("%d.%m")
        for offset in range(n)
    ]


def _series_for_days(queryset, date_field: str, days: int = 7) -> list[int]:
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    rows = (
        queryset.filter(**{f"{date_field}__date__gte": start})
        .annotate(day=TruncDate(date_field))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    by_day = {row["day"]: row["count"] for row in rows}
    return [
        by_day.get(start + timedelta(days=offset), 0)
        for offset in range(days)
    ]


def get_chart_data() -> dict:
    labels = _last_n_days_labels()
    order_status = {
        AtmosOrder.Status.PAID: "To'langan",
        AtmosOrder.Status.PENDING: "Kutilmoqda",
        AtmosOrder.Status.CREATED: "Yaratilgan",
        AtmosOrder.Status.FAILED: "Xato",
        AtmosOrder.Status.CANCELED: "Bekor",
        AtmosOrder.Status.EXPIRED: "Muddati o'tgan",
    }
    order_counts = []
    order_labels = []
    for code, label in order_status.items():
        count = AtmosOrder.objects.filter(status=code).count()
        if count or code in (AtmosOrder.Status.PAID, AtmosOrder.Status.PENDING):
            order_labels.append(label)
            order_counts.append(count)

    active = Test.objects.filter(is_active=True)
    return {
        "answers": {
            "labels": labels,
            "data": _series_for_days(UserAnsweredTest.objects.all(), "created_at"),
            "label": "Kunlik javoblar",
        },
        "users": {
            "labels": labels,
            "data": _series_for_days(TelegramUser.objects.all(), "created_at"),
            "label": "Yangi foydalanuvchilar",
        },
        "levels": {
            "labels": ["Oson", "O'rta", "Qiyin"],
            "data": [
                active.filter(level=Test.Level.EASY).count(),
                active.filter(level=Test.Level.MEDIUM).count(),
                active.filter(level=Test.Level.HARD).count(),
            ],
            "label": "Savollar darajasi",
        },
        "orders": {
            "labels": order_labels or ["Ma'lumot yo'q"],
            "data": order_counts or [0],
            "label": "Buyurtmalar holati",
        },
    }


def get_dashboard_statistics() -> dict:
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    stats = get_admin_statistics()
    active_tests = Test.objects.filter(is_active=True)
    stats.update(
        {
            "active_questions": active_tests.count(),
            "easy_questions": active_tests.filter(level=Test.Level.EASY).count(),
            "medium_questions": active_tests.filter(level=Test.Level.MEDIUM).count(),
            "hard_questions": active_tests.filter(level=Test.Level.HARD).count(),
            "quiz_answers_today": UserAnsweredTest.objects.filter(
                created_at__gte=today_start
            ).count(),
            "quiz_answers_total": UserAnsweredTest.objects.count(),
            "charts": get_chart_data(),
        }
    )
    stats["charts_json"] = json.dumps(stats["charts"])
    return stats


def patch_admin_index():
    from django.contrib.admin.sites import AdminSite

    if getattr(AdminSite, "_deenify_index_patched", False):
        return

    original_index = AdminSite.index

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["dashboard_stats"] = get_dashboard_statistics()
        return original_index(self, request, extra_context)

    AdminSite.index = index
    AdminSite._deenify_index_patched = True
