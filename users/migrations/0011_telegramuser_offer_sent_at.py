from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0010_bound_card_referrals_feedback"),
    ]

    operations = [
        migrations.AddField(
            model_name="telegramuser",
            name="offer_sent_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the subscription catalog was last sent (for auto-delete after TTL).",
                null=True,
                verbose_name="offer sent at",
            ),
        ),
    ]
