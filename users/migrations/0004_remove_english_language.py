from django.db import migrations, models


def convert_english_to_uzbek(apps, schema_editor):
    TelegramUser = apps.get_model("users", "TelegramUser")
    TelegramUser.objects.filter(language="en").update(language="uz")


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_telegramuser_phone_quiz_round_uz_cy"),
    ]

    operations = [
        migrations.RunPython(convert_english_to_uzbek, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="telegramuser",
            name="language",
            field=models.CharField(
                choices=[
                    ("uz", "Uzbek"),
                    ("uz_cy", "Uzbek Cyrillic"),
                    ("ru", "Russian"),
                ],
                default="uz",
                max_length=5,
                verbose_name="language",
            ),
        ),
    ]
