from django.contrib import admin
from modeltranslation.admin import TranslationAdmin, TranslationTabularInline

from .models import Answer, Test, UserAnsweredTest, UserTestAnswer, UserTestSession


class AnswerInline(TranslationTabularInline):
    model = Answer
    extra = 4
    fields = ("text", "is_correct", "sort_order")


@admin.register(Test)
class TestAdmin(TranslationAdmin):
    list_display = ("title", "level", "is_active", "is_premium", "sort_order")
    list_filter = ("level", "is_active", "is_premium")
    search_fields = ("title", "question", "description")
    fieldsets = (
        (None, {"fields": ("category", "title", "question", "level", "description", "explanation", "is_active", "is_premium", "sort_order")}),
    )
    inlines = (AnswerInline,)
    ordering = ("sort_order", "id")

    def save_model(self, request, obj, form, change):
        if not obj.category_id:
            from .models import TestCategory

            obj.category = TestCategory.get_default()
        super().save_model(request, obj, form, change)


@admin.register(Answer)
class AnswerAdmin(TranslationAdmin):
    list_display = ("text", "test", "is_correct", "sort_order")
    list_filter = ("is_correct", "test__level")
    search_fields = ("text", "test__title")
    autocomplete_fields = ("test",)


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
        "completed_at",
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


@admin.register(UserAnsweredTest)
class UserAnsweredTestAdmin(admin.ModelAdmin):
    list_display = ("user", "test", "round", "created_at")
    list_filter = ("round",)
    search_fields = ("user__telegram_id", "test__title")
    autocomplete_fields = ("user", "test")


@admin.register(UserTestAnswer)
class UserTestAnswerAdmin(admin.ModelAdmin):
    list_display = ("session", "test", "selected_answer", "is_correct", "answered_at")
    list_filter = ("is_correct", "test__level", "answered_at")
    search_fields = ("session__user__telegram_id", "test__title", "selected_answer__text")
    readonly_fields = ("is_correct", "answered_at", "created_at", "updated_at")
    autocomplete_fields = ("session", "test", "selected_answer")
