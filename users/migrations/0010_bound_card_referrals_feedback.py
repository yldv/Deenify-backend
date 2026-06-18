import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0009_telegramuser_offer_prompt_message_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="BoundCard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="created at")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="updated at")),
                ("card_id", models.CharField(db_index=True, max_length=64, verbose_name="Atmos card id")),
                ("card_token", models.CharField(max_length=255, verbose_name="card token")),
                ("masked_pan", models.CharField(blank=True, max_length=32, verbose_name="masked pan")),
                ("expiry", models.CharField(blank=True, max_length=8, verbose_name="expiry")),
                ("card_holder", models.CharField(blank=True, max_length=255, verbose_name="card holder")),
                ("phone", models.CharField(blank=True, max_length=32, verbose_name="phone")),
                ("is_active", models.BooleanField(db_index=True, default=True, verbose_name="is active")),
                ("removed_at", models.DateTimeField(blank=True, null=True, verbose_name="removed at")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bound_cards",
                        to="users.telegramuser",
                        verbose_name="user",
                    ),
                ),
            ],
            options={
                "verbose_name": "Bound card",
                "verbose_name_plural": "Bound cards",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="boundcard",
            index=models.Index(fields=["user", "is_active"], name="users_bound_user_id_1f4c4b_idx"),
        ),
        migrations.AddField(
            model_name="telegramuser",
            name="referred_by",
            field=models.ForeignKey(
                blank=True,
                help_text="User who invited this user via a referral link.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="referrals",
                to="users.telegramuser",
                verbose_name="referred by",
            ),
        ),
        migrations.AddField(
            model_name="telegramuser",
            name="referral_rewarded",
            field=models.BooleanField(
                default=False,
                help_text="Whether this user's first payment already rewarded the inviter.",
                verbose_name="referral rewarded",
            ),
        ),
        migrations.AddField(
            model_name="userpremiumsubscription",
            name="auto_renew",
            field=models.BooleanField(
                default=False,
                help_text="Charge the bound card automatically when this period ends.",
                verbose_name="auto renew",
            ),
        ),
        migrations.AddField(
            model_name="userpremiumsubscription",
            name="bound_card",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="subscriptions",
                to="users.boundcard",
                verbose_name="bound card",
            ),
        ),
        migrations.AddField(
            model_name="userpremiumsubscription",
            name="source",
            field=models.CharField(
                choices=[("payment", "Payment"), ("referral", "Referral bonus"), ("manual", "Manual")],
                default="payment",
                max_length=20,
                verbose_name="source",
            ),
        ),
        migrations.AlterField(
            model_name="userpremiumsubscription",
            name="plan",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="premium_subscriptions",
                to="users.subscriptionplan",
                verbose_name="plan",
            ),
        ),
        migrations.AddField(
            model_name="atmosorder",
            name="is_auto_renewal",
            field=models.BooleanField(
                default=False,
                help_text="Charge created automatically by the recurring billing scheduler.",
                verbose_name="is auto renewal",
            ),
        ),
        migrations.AddField(
            model_name="atmosorder",
            name="bound_card",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="orders",
                to="users.boundcard",
                verbose_name="bound card",
            ),
        ),
        migrations.CreateModel(
            name="Feedback",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="created at")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="updated at")),
                (
                    "context",
                    models.CharField(
                        choices=[("declined", "Declined the offer"), ("canceled", "Canceled subscription")],
                        db_index=True,
                        default="declined",
                        max_length=20,
                        verbose_name="context",
                    ),
                ),
                (
                    "reason",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("expensive", "Too expensive"),
                            ("not_now", "Not needed now"),
                            ("trust", "Trust / security"),
                            ("hard_payment", "Payment was difficult"),
                            ("other", "Other"),
                        ],
                        max_length=20,
                        verbose_name="reason",
                    ),
                ),
                ("text", models.TextField(blank=True, verbose_name="text")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="feedbacks",
                        to="users.telegramuser",
                        verbose_name="user",
                    ),
                ),
            ],
            options={
                "verbose_name": "Feedback",
                "verbose_name_plural": "Feedback",
                "ordering": ("-created_at",),
            },
        ),
    ]
