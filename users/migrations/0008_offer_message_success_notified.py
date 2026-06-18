from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0007_telegramuser_bot_is_active"),
    ]

    operations = [
        migrations.AddField(
            model_name="telegramuser",
            name="offer_message_id",
            field=models.BigIntegerField(
                blank=True,
                help_text="Telegram message id of the last subscription catalog message.",
                null=True,
                verbose_name="offer message id",
            ),
        ),
        migrations.AddField(
            model_name="telegramuser",
            name="offer_chat_id",
            field=models.BigIntegerField(
                blank=True,
                help_text="Chat where the last subscription catalog message was sent.",
                null=True,
                verbose_name="offer chat id",
            ),
        ),
        migrations.AddField(
            model_name="atmosorder",
            name="success_notified",
            field=models.BooleanField(default=False, verbose_name="success notified"),
        ),
    ]
