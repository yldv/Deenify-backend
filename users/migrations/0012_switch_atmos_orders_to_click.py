"""Atmos -> Click switch.

The tables and their rows are preserved: models are renamed in place and only
the Atmos-specific columns (card token, auto renewal) are dropped.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0011_telegramuser_offer_sent_at'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='AtmosOrder',
            new_name='ClickOrder',
        ),
        migrations.RenameModel(
            old_name='AtmosTransaction',
            new_name='ClickTransaction',
        ),
        migrations.AlterModelOptions(
            name='clickorder',
            options={'ordering': ('-created_at',), 'verbose_name': 'Click order', 'verbose_name_plural': 'Click orders'},
        ),
        migrations.AlterModelOptions(
            name='clicktransaction',
            options={'ordering': ('-created_at',), 'verbose_name': 'Click transaction', 'verbose_name_plural': 'Click transactions'},
        ),
        migrations.RemoveField(
            model_name='clickorder',
            name='expires_at',
        ),
        migrations.RenameField(
            model_name='clickorder',
            old_name='atmos_transaction_id',
            new_name='click_trans_id',
        ),
        migrations.RenameField(
            model_name='clickorder',
            old_name='payment_url',
            new_name='checkout_url',
        ),
        migrations.AlterField(
            model_name='clickorder',
            name='click_trans_id',
            field=models.CharField(blank=True, db_index=True, help_text='click_trans_id returned by Click in the callback.', max_length=128, verbose_name='Click transaction id'),
        ),
        migrations.AlterField(
            model_name='clickorder',
            name='checkout_url',
            field=models.URLField(blank=True, help_text='Our own checkout page that renders the Click payment form.', max_length=500, verbose_name='checkout url'),
        ),
        migrations.AlterField(
            model_name='clickorder',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='click_orders', to='users.telegramuser', verbose_name='user'),
        ),
        migrations.AlterField(
            model_name='clickorder',
            name='plan',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='click_orders', to='users.subscriptionplan', verbose_name='plan'),
        ),
        migrations.AlterField(
            model_name='clicktransaction',
            name='order',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='users.clickorder', verbose_name='order'),
        ),
        migrations.AlterField(
            model_name='userpremiumsubscription',
            name='source_order',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='premium_subscription', to='users.clickorder', verbose_name='source order'),
        ),
        migrations.RemoveField(
            model_name='clickorder',
            name='is_auto_renewal',
        ),
        migrations.RemoveField(
            model_name='clickorder',
            name='bound_card',
        ),
        migrations.RemoveField(
            model_name='userpremiumsubscription',
            name='auto_renew',
        ),
        migrations.RemoveField(
            model_name='userpremiumsubscription',
            name='bound_card',
        ),
        migrations.RemoveIndex(
            model_name='clickorder',
            name='users_atmos_user_id_c90868_idx',
        ),
        migrations.RemoveIndex(
            model_name='clickorder',
            name='users_atmos_order_i_da4ecb_idx',
        ),
        migrations.RemoveIndex(
            model_name='clicktransaction',
            name='users_atmos_transac_d0fae8_idx',
        ),
        migrations.AddIndex(
            model_name='clickorder',
            index=models.Index(fields=['user', 'status'], name='users_click_user_id_474053_idx'),
        ),
        migrations.AddIndex(
            model_name='clickorder',
            index=models.Index(fields=['order_id', 'status'], name='users_click_order_i_fe81c0_idx'),
        ),
        migrations.AddIndex(
            model_name='clicktransaction',
            index=models.Index(fields=['transaction_id', 'status'], name='users_click_transac_84a436_idx'),
        ),
        migrations.RemoveConstraint(
            model_name='clicktransaction',
            name='unique_atmos_transaction_per_order',
        ),
        migrations.AddConstraint(
            model_name='clicktransaction',
            constraint=models.UniqueConstraint(fields=('order', 'transaction_id'), name='unique_click_transaction_per_order'),
        ),
        migrations.DeleteModel(
            name='BoundCard',
        ),
    ]
