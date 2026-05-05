from django.contrib import admin
from modeltranslation.admin import TranslationAdmin, TranslationTabularInline

from .models import Answer, Test, TestCategory, UserTestAnswer, UserTestSession


class AnswerInline(TranslationTabularInline):
    model = Answer
    extra = 4
    fields = ("text", "is_correct", "sort_order")


@admin.register(TestCategory)
class TestCategoryAdmin(TranslationAdmin):
    list_display = ("name", "slug", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("sort_order", "name")


@admin.register(Test)
class TestAdmin(TranslationAdmin):
    list_display = ("title", "category", "level", "is_active", "is_premium", "sort_order")
    list_filter = ("category", "level", "is_active", "is_premium")
    search_fields = ("title", "question")
    autocomplete_fields = ("category",)
    inlines = (AnswerInline,)
    ordering = ("category", "sort_order")


@admin.register(Answer)
class AnswerAdmin(TranslationAdmin):
    list_display = ("text", "test", "is_correct", "sort_order")
    list_filter = ("is_correct", "test__category")
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
        "category",
        "level",
        "status",
        "total_questions",
        "correct_answers",
        "wrong_answers",
        "score_percent",
        "started_at",
        "completed_at",
    )
    list_filter = ("status", "category", "level", "started_at")
    search_fields = ("user__telegram_id", "user__username")
    readonly_fields = (
        "total_questions",
        "correct_answers",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("user", "category")
    inlines = (UserTestAnswerInline,)


@admin.register(UserTestAnswer)
class UserTestAnswerAdmin(admin.ModelAdmin):
    list_display = ("session", "test", "selected_answer", "is_correct", "answered_at")
    list_filter = ("is_correct", "test__category", "test__level", "answered_at")
    search_fields = ("session__user__telegram_id", "test__title", "selected_answer__text")
    readonly_fields = ("is_correct", "answered_at", "created_at", "updated_at")
    autocomplete_fields = ("session", "test", "selected_answer")
