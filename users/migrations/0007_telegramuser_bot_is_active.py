from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0006_subscriptionplan_description_uz_cy_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="telegramuser",
            name="bot_is_active",
            field=models.BooleanField(
                db_index=True,
                default=True,
                help_text="False if the user blocked the bot or deleted the chat.",
                verbose_name="bot is active",
            ),
        ),
        migrations.CreateModel(
            name="ActiveTelegramUser",
            fields=[],
            options={
                "verbose_name": "Active Telegram user",
                "verbose_name_plural": "Active Telegram users",
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("users.telegramuser",),
        ),
    ]
