from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
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
        EASY = "easy", _("Easy")
        MEDIUM = "medium", _("Medium")
        HARD = "hard", _("Hard")

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
        help_text=_("Source citation shown in Telegram quiz poll (not the answer explanation)."),
    )
    explanation = models.TextField(
        _("explanation"),
        blank=True,
        help_text=_("Short feedback after the user answers (not shown in the poll)."),
    )
    level = models.CharField(
        _("level"),
        max_length=10,
        choices=Level.choices,
        default=Level.EASY,
        db_index=True,
    )
    is_active = models.BooleanField(_("is active"), default=True)
    is_premium = models.BooleanField(_("is premium"), default=False)
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
        if self.is_premium and not user.has_active_premium():
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


class UserTestSession(TimeStampedModel):
    class Status(models.TextChoices):
        STARTED = "started", _("Started")
        COMPLETED = "completed", _("Completed")
        CANCELED = "canceled", _("Canceled")

    user = models.ForeignKey(
        "users.TelegramUser",
        on_delete=models.CASCADE,
        related_name="test_sessions",
        verbose_name=_("user"),
    )
    tests = models.ManyToManyField(
        Test,
        related_name="test_sessions",
        blank=True,
        verbose_name=_("tests"),
    )
    category = models.ForeignKey(
        TestCategory,
        on_delete=models.PROTECT,
        related_name="sessions",
        verbose_name=_("category"),
        null=True,
        blank=True,
    )
    level = models.CharField(
        _("level"),
        max_length=10,
        choices=Test.Level.choices,
        blank=True,
        db_index=True,
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.STARTED,
        db_index=True,
    )
    total_questions = models.PositiveSmallIntegerField(_("total questions"), default=0)
    correct_answers = models.PositiveSmallIntegerField(_("correct answers"), default=0)
    wrong_answers = models.PositiveSmallIntegerField(_("wrong answers"), default=0)
    started_at = models.DateTimeField(_("started at"), default=timezone.now)
    completed_at = models.DateTimeField(_("completed at"), null=True, blank=True)

    class Meta:
        ordering = ("-started_at",)
        verbose_name = _("user test session")
        verbose_name_plural = _("user test sessions")
        indexes = [
            models.Index(fields=("user", "status")),
            models.Index(fields=("category", "level")),
        ]

    def __str__(self):
        return f"{self.user} - {self.status}"

    @property
    def score_percent(self):
        if not self.total_questions:
            return 0
        return round((self.correct_answers / self.total_questions) * 100)

    def complete(self):
        answers = self.user_answers.all()
        self.total_questions = answers.count()
        self.correct_answers = answers.filter(is_correct=True).count()
        self.wrong_answers = self.total_questions - self.correct_answers
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(
            update_fields=(
                "total_questions",
                "correct_answers",
                "wrong_answers",
                "status",
                "completed_at",
                "updated_at",
            )
        )

    @classmethod
    def start_for_user(cls, user, category=None, level=""):
        if not user.can_take_test():
            raise ValidationError(_("User cannot take more tests."))

        session = cls.objects.create(user=user, category=category, level=level)
        user.register_free_test_usage()
        return session


class UserTestAnswer(TimeStampedModel):
    session = models.ForeignKey(
        UserTestSession,
        on_delete=models.CASCADE,
        related_name="user_answers",
        verbose_name=_("session"),
    )
    test = models.ForeignKey(
        Test,
        on_delete=models.PROTECT,
        related_name="user_answers",
        verbose_name=_("test"),
    )
    selected_answer = models.ForeignKey(
        Answer,
        on_delete=models.PROTECT,
        related_name="user_answers",
        verbose_name=_("selected answer"),
    )
    is_correct = models.BooleanField(_("is correct"), default=False, db_index=True)
    answered_at = models.DateTimeField(_("answered at"), default=timezone.now)

    class Meta:
        ordering = ("answered_at",)
        verbose_name = _("user test answer")
        verbose_name_plural = _("user test answers")
        constraints = [
            models.UniqueConstraint(
                fields=("session", "test"),
                name="unique_answer_per_test_in_session",
            ),
        ]

    def __str__(self):
        return f"{self.session} - {self.test}"

    def clean(self):
        if self.selected_answer_id and self.test_id:
            if self.selected_answer.test_id != self.test_id:
                raise ValidationError(
                    _("Selected answer does not belong to this test.")
                )

    def save(self, *args, **kwargs):
        self.is_correct = bool(self.selected_answer and self.selected_answer.is_correct)
        super().save(*args, **kwargs)


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
