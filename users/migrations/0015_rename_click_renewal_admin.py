from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("users", "0014_click_card_checkout")]

    operations = [
        migrations.AlterModelOptions(
            name="clickrenewal",
            options={"verbose_name": "Avtouzaytirish", "verbose_name_plural": "Avtouzaytirish"},
        ),
    ]
