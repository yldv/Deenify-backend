from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tests", "0008_alter_test_level"),
    ]

    operations = [
        migrations.RemoveField(model_name="test", name="is_premium"),
        migrations.RemoveField(model_name="test", name="explanation"),
        migrations.RemoveField(model_name="test", name="explanation_uz"),
        migrations.RemoveField(model_name="test", name="explanation_ru"),
        migrations.RemoveField(model_name="test", name="explanation_uz_cy"),
    ]
