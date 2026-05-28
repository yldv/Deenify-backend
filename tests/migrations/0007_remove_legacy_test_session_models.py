from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tests", "0006_uz_cy_translation_fields"),
    ]

    operations = [
        migrations.DeleteModel(
            name="UserTestAnswer",
        ),
        migrations.DeleteModel(
            name="UserTestSession",
        ),
    ]
