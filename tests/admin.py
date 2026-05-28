from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from tests.models import Answer, Test, TestCategory, UserAnsweredTest
from tests.services.quiz_import import import_questions_from_payload, parse_json_payload

TRANSLATED_TEST_FIELDS = ("title", "question", "description", "explanation")


def _language_fieldset(label: str, css_class: str, suffix: str) -> tuple:
    return (
        label,
        {
            "classes": (css_class,),
            "fields": tuple(f"{name}_{suffix}" for name in TRANSLATED_TEST_FIELDS),
        },
    )


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 4
    fields = ("sort_order", "is_correct", "text_uz", "text_uz_cy", "text_ru")
    verbose_name = "Javob"
    verbose_name_plural = "Javoblar (lotin, kirill, rus — bitta to'g'ri belgilang)"


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
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
    search_fields = (
        "title",
        "title_uz",
        "title_uz_cy",
        "title_ru",
        "question",
        "question_uz",
        "description",
        "description_uz",
    )
    list_editable = ("is_active", "sort_order")
    ordering = ("sort_order", "id")
    inlines = (AnswerInline,)
    fieldsets = (
        (
            "Sozlamalar",
            {
                "fields": ("level", "sort_order", "is_active", "is_premium"),
            },
        ),
        _language_fieldset("O'zbekcha (lotin)", "deenify-fs-uz", "uz"),
        _language_fieldset("Ўzbekcha (kirill)", "deenify-fs-uz-cy", "uz_cy"),
        _language_fieldset("Ruscha", "deenify-fs-ru", "ru"),
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
        for field in TRANSLATED_TEST_FIELDS:
            uz_value = getattr(obj, f"{field}_uz", None) or ""
            if uz_value and not getattr(obj, field, None):
                setattr(obj, field, uz_value)
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, Answer):
                if instance.text_uz and not instance.text:
                    instance.text = instance.text_uz
            instance.save()
        for obj in formset.deleted_objects:
            obj.delete()
        formset.save_m2m()

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
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("text_short", "test", "is_correct", "sort_order")
    list_filter = ("is_correct", "test__level")
    search_fields = ("text", "text_uz", "test__title")
    autocomplete_fields = ("test",)
    fieldsets = (
        ("Savol", {"fields": ("test", "sort_order", "is_correct")}),
        ("O'zbekcha (lotin)", {"fields": ("text_uz",)}),
        ("Ўzbekcha (kirill)", {"fields": ("text_uz_cy",)}),
        ("Ruscha", {"fields": ("text_ru",)}),
    )

    def save_model(self, request, obj, form, change):
        if obj.text_uz and not obj.text:
            obj.text = obj.text_uz
        super().save_model(request, obj, form, change)

    @admin.display(description="Matn")
    def text_short(self, obj):
        text = obj.text_uz or obj.text or ""
        return text[:80] + "…" if len(text) > 80 else text


@admin.register(UserAnsweredTest)
class UserAnsweredTestAdmin(admin.ModelAdmin):
    list_display = ("user", "test", "round", "created_at")
    list_filter = ("round", "created_at")
    search_fields = ("user__telegram_id", "test__title")
    autocomplete_fields = ("user", "test")
    readonly_fields = ("created_at", "updated_at")
