from modeltranslation.translator import TranslationOptions, register

from .models import Answer, Test, TestCategory


@register(TestCategory)
class TestCategoryTranslationOptions(TranslationOptions):
    fields = ("name", "description")


@register(Test)
class TestTranslationOptions(TranslationOptions):
    fields = ("title", "question", "description")


@register(Answer)
class AnswerTranslationOptions(TranslationOptions):
    fields = ("text",)
