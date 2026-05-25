from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tests", "0004_remove_english_translation_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="test",
            name="description",
            field=models.TextField(
                blank=True,
                help_text="Source citation shown in Telegram quiz poll (not the answer explanation).",
                verbose_name="description",
            ),
        ),
        migrations.AddField(
            model_name="test",
            name="description_uz",
            field=models.TextField(blank=True, null=True, verbose_name="description"),
        ),
        migrations.AddField(
            model_name="test",
            name="description_ru",
            field=models.TextField(blank=True, null=True, verbose_name="description"),
        ),
        migrations.AddField(
            model_name="test",
            name="description_uz_cy",
            field=models.TextField(blank=True, null=True, verbose_name="description"),
        ),
    ]
