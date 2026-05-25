import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_telegramuser_phone_quiz_round_uz_cy"),
        ("tests", "0002_usertestsession_tests_usertestsession_wrong_answers"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserAnsweredTest",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="created at")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="updated at")),
                ("round", models.PositiveIntegerField(db_index=True, default=1, verbose_name="round")),
                (
                    "test",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_completions",
                        to="tests.test",
                        verbose_name="test",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="answered_tests",
                        to="users.telegramuser",
                        verbose_name="user",
                    ),
                ),
            ],
            options={
                "verbose_name": "user answered test",
                "verbose_name_plural": "user answered tests",
            },
        ),
        migrations.AddIndex(
            model_name="useransweredtest",
            index=models.Index(fields=["user", "round"], name="tests_usera_user_id_6e8f0d_idx"),
        ),
        migrations.AddConstraint(
            model_name="useransweredtest",
            constraint=models.UniqueConstraint(
                fields=("user", "test", "round"),
                name="unique_user_test_per_round",
            ),
        ),
    ]
