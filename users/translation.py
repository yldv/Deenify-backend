from modeltranslation.translator import TranslationOptions, register

from .models import SubscriptionPlan


@register(SubscriptionPlan)
class SubscriptionPlanTranslationOptions(TranslationOptions):
    fields = ("name", "description")
