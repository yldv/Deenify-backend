from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0008_offer_message_success_notified"),
    ]

    operations = [
        migrations.AddField(
            model_name="telegramuser",
            name="offer_prompt_message_id",
            field=models.BigIntegerField(
                blank=True,
                help_text="Telegram message id of the 'subscription required' lead-in message.",
                null=True,
                verbose_name="offer prompt message id",
            ),
        ),
    ]
