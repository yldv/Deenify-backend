from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        abstract = True


class TestCategory(TimeStampedModel):
    name = models.CharField(_("name"), max_length=160)
    description = models.TextField(_("description"), blank=True)
    slug = models.SlugField(_("slug"), max_length=180, unique=True)
    is_active = models.BooleanField(_("is active"), default=True)
    sort_order = models.PositiveSmallIntegerField(_("sort order"), default=0)

    class Meta:
        ordering = ("sort_order", "name")
        verbose_name = _("test category")
        verbose_name_plural = _("test categories")

    def __str__(self):
        return self.name

    @classmethod
    def get_default(cls):
        slug = settings.DEENIFY_QUIZ_DEFAULT_CATEGORY_SLUG
        category, _ = cls.objects.get_or_create(
            slug=slug,
            defaults={
                "name": "Islom savollari",
                "name_uz": "Islom savollari",
                "name_ru": "Исламские вопросы",
                "description": "",
                "is_active": True,
                "sort_order": 0,
            },
        )
        return category


class Test(TimeStampedModel):
    class Level(models.TextChoices):
        EASY = "easy", "Oson"
        MEDIUM = "medium", "O'rta"
        HARD = "hard", "Qiyin"

    category = models.ForeignKey(
        TestCategory,
        on_delete=models.PROTECT,
        related_name="tests",
        verbose_name=_("category"),
    )
    title = models.CharField(_("title"), max_length=255)
    question = models.TextField(_("question"))
    description = models.TextField(
        _("description"),
        blank=True,
        help_text=_("Source citation shown in Telegram quiz poll on wrong answers."),
    )
    level = models.CharField(
        _("level"),
        max_length=10,
        choices=Level.choices,
        default=Level.EASY,
        db_index=True,
    )
    is_active = models.BooleanField(_("is active"), default=True)
    sort_order = models.PositiveSmallIntegerField(_("sort order"), default=0)

    class Meta:
        ordering = ("category", "sort_order", "id")
        verbose_name = _("test")
        verbose_name_plural = _("tests")
        indexes = [
            models.Index(fields=("category", "level", "is_active")),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.category_id:
            self.category = TestCategory.get_default()
        super().save(*args, **kwargs)

    def get_correct_answer(self):
        return self.answers.filter(is_correct=True).first()

    def can_be_taken_by(self, user):
        if not self.is_active:
            return False
        return user.can_take_test()


class Answer(TimeStampedModel):
    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name="answers",
        verbose_name=_("test"),
    )
    text = models.CharField(_("text"), max_length=500)
    is_correct = models.BooleanField(_("is correct"), default=False, db_index=True)
    sort_order = models.PositiveSmallIntegerField(_("sort order"), default=0)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = _("answer")
        verbose_name_plural = _("answers")
        constraints = [
            models.UniqueConstraint(
                fields=("test",),
                condition=Q(is_correct=True),
                name="unique_correct_answer_per_test",
            ),
        ]

    def __str__(self):
        return self.text


class UserAnsweredTest(TimeStampedModel):
    user = models.ForeignKey(
        "users.TelegramUser",
        on_delete=models.CASCADE,
        related_name="answered_tests",
        verbose_name=_("user"),
    )
    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name="user_completions",
        verbose_name=_("test"),
    )
    round = models.PositiveIntegerField(_("round"), default=1, db_index=True)

    class Meta:
        verbose_name = _("user answered test")
        verbose_name_plural = _("user answered tests")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "test", "round"),
                name="unique_user_test_per_round",
            ),
        ]
        indexes = [
            models.Index(fields=("user", "round")),
        ]

    def __str__(self):
        return f"{self.user} - {self.test} (round {self.round})"
