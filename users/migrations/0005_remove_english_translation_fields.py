from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_remove_english_language"),
    ]

    operations = [
        migrations.RemoveField(model_name="subscriptionplan", name="name_en"),
        migrations.RemoveField(model_name="subscriptionplan", name="description_en"),
    ]
