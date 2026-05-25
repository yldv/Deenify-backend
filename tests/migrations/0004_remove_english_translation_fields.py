from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tests", "0003_useransweredtest"),
    ]

    operations = [
        migrations.RemoveField(model_name="testcategory", name="name_en"),
        migrations.RemoveField(model_name="testcategory", name="description_en"),
        migrations.RemoveField(model_name="test", name="title_en"),
        migrations.RemoveField(model_name="test", name="question_en"),
        migrations.RemoveField(model_name="test", name="explanation_en"),
        migrations.RemoveField(model_name="answer", name="text_en"),
    ]
