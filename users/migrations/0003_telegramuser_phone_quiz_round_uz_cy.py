from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_atmosorder_merchant_order_id_atmosorder_payment_url_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="telegramuser",
            name="phone_number",
            field=models.CharField(blank=True, max_length=50, verbose_name="phone number"),
        ),
        migrations.AddField(
            model_name="telegramuser",
            name="quiz_round",
            field=models.PositiveIntegerField(default=1, verbose_name="quiz round"),
        ),
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
