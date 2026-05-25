from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from modeltranslation.admin import TranslationAdmin, TranslationTabularInline

from tests.models import Answer, Test, TestCategory, UserAnsweredTest, UserTestAnswer, UserTestSession
from tests.services.quiz_import import import_questions_from_payload, parse_json_payload


class DeenifyTranslationAdmin(TranslationAdmin):
    """O'zbekcha (lotin), Ўзбекcha (kirill), Ruscha — uchala til."""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name.endswith("_uz_cy"):
            field.help_text = "Ўзбекcha (kirill). Bo'sh qoldirsangiz, importda lotindan to'ldiriladi."
        return field


class AnswerInline(TranslationTabularInline):
    model = Answer
    extra = 4
    fields = ("text", "is_correct", "sort_order")
    verbose_name = "Javob"
    verbose_name_plural = "Javoblar"


@admin.register(Test)
class TestAdmin(DeenifyTranslationAdmin):
    change_list_template = "admin/tests/test_change_list.html"
    list_display = (
        "title",
        "level_badge",
        "is_active",
        "is_premium",
        "sort_order",
        "answers_count",
    )
    list_filter = ("level", "is_active", "is_premium")
    search_fields = ("title", "question", "description")
    list_editable = ("is_active", "sort_order")
    ordering = ("sort_order", "id")
    inlines = (AnswerInline,)
    fieldsets = (
        (
            "Asosiy",
            {
                "description": (
                    "Yuqoridagi tillar: <strong>O'zbekcha (lotin)</strong>, "
                    "<strong>Ўзбекcha (kirill)</strong>, <strong>Ruscha</strong>. "
                    "Bot foydalanuvchi tiliga qarab shu matnlarni yuboradi."
                ),
                "fields": (
                    "title",
                    "question",
                    "level",
                    "sort_order",
                    "is_active",
                    "is_premium",
                ),
            },
        ),
        (
            "Manba va tushuntirish",
            {
                "description": (
                    "«Tavsif» — Telegram poll ostidagi Manba matni. "
                    "«Tushuntirish» — javobdan keyin (botda alohida ko'rsatilmaydi)."
                ),
                "fields": ("description", "explanation"),
            },
        ),
    )

    @admin.display(description="Daraja")
    def level_badge(self, obj):
        colors = {
            Test.Level.EASY: "success",
            Test.Level.MEDIUM: "warning",
            Test.Level.HARD: "danger",
        }
        color = colors.get(obj.level, "secondary")
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color,
            obj.get_level_display(),
        )

    @admin.display(description="Javoblar")
    def answers_count(self, obj):
        return obj.answers.count()

    def save_model(self, request, obj, form, change):
        obj.category = TestCategory.get_default()
        super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "import-json/",
                self.admin_site.admin_view(self.import_json_view),
                name="tests_test_import_json",
            ),
        ]
        return custom + urls

    def import_json_view(self, request):
        from django.conf import settings

        example_path = (
            settings.BASE_DIR / "static" / "admin" / "examples" / "quiz_import_example.json"
        )
        example_json = example_path.read_text(encoding="utf-8") if example_path.exists() else "{}"
        default_slug = getattr(settings, "DEENIFY_QUIZ_DEFAULT_CATEGORY_SLUG", "islam")

        if request.method == "POST":
            upload = request.FILES.get("json_file")
            if not upload:
                messages.error(request, "JSON fayl tanlanmadi.")
                return redirect(request.path)

            try:
                raw = upload.read()
                data = parse_json_payload(raw)
                result = import_questions_from_payload(
                    data,
                    category_slug=default_slug,
                    deactivate_others=False,
                )
                messages.success(
                    request,
                    f"Muvaffaqiyatli: {result['imported']} ta savol yuklandi. "
                    f"Jami faol savollar: {result['active_questions']}.",
                )
                return redirect("admin:tests_test_changelist")
            except ValidationError as exc:
                messages.error(request, str(exc))
            except Exception as exc:
                messages.error(request, f"Xatolik: {exc}")

        return render(
            request,
            "admin/tests/import_questions.html",
            {
                **self.admin_site.each_context(request),
                "title": "JSON dan savollar yuklash",
                "example_json": example_json,
                "opts": self.model._meta,
            },
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["import_json_url"] = reverse("admin:tests_test_import_json")
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(Answer)
class AnswerAdmin(DeenifyTranslationAdmin):
    list_display = ("text_short", "test", "is_correct", "sort_order")
    list_filter = ("is_correct", "test__level")
    search_fields = ("text", "test__title")
    autocomplete_fields = ("test",)

    @admin.display(description="Matn")
    def text_short(self, obj):
        text = obj.text or ""
        return text[:80] + "…" if len(text) > 80 else text


@admin.register(UserAnsweredTest)
class UserAnsweredTestAdmin(admin.ModelAdmin):
    list_display = ("user", "test", "round", "created_at")
    list_filter = ("round", "created_at")
    search_fields = ("user__telegram_id", "test__title")
    autocomplete_fields = ("user", "test")
    readonly_fields = ("created_at", "updated_at")


class UserTestAnswerInline(admin.TabularInline):
    model = UserTestAnswer
    extra = 0
    readonly_fields = ("test", "selected_answer", "is_correct", "answered_at")
    can_delete = False


@admin.register(UserTestSession)
class UserTestSessionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "level",
        "status",
        "total_questions",
        "correct_answers",
        "wrong_answers",
        "score_percent",
        "started_at",
    )
    list_filter = ("status", "level", "started_at")
    search_fields = ("user__telegram_id", "user__username")
    readonly_fields = (
        "total_questions",
        "correct_answers",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("user",)
    inlines = (UserTestAnswerInline,)


@admin.register(UserTestAnswer)
class UserTestAnswerAdmin(admin.ModelAdmin):
    list_display = ("session", "test", "selected_answer", "is_correct", "answered_at")
    list_filter = ("is_correct", "test__level", "answered_at")
    search_fields = ("session__user__telegram_id", "test__title")
    readonly_fields = ("is_correct", "answered_at", "created_at", "updated_at")
    autocomplete_fields = ("session", "test", "selected_answer")
