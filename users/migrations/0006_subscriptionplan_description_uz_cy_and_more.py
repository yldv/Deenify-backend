from django.db import migrations, models


def _subscriptionplan_columns(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(
            cursor, "users_subscriptionplan"
        )
    return {col.name for col in description}


def add_uz_cy_fields_if_missing(apps, schema_editor):
    existing = _subscriptionplan_columns(schema_editor)
    model = apps.get_model("users", "SubscriptionPlan")

    fields = (
        (
            "description_uz_cy",
            models.TextField(blank=True, null=True, verbose_name="description"),
        ),
        (
            "name_uz_cy",
            models.CharField(max_length=120, null=True, verbose_name="name"),
        ),
    )
    for name, field in fields:
        if name in existing:
            continue
        field.set_attributes_from_name(name)
        schema_editor.add_field(model, field)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_remove_english_translation_fields"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="subscriptionplan",
                    name="description_uz_cy",
                    field=models.TextField(
                        blank=True, null=True, verbose_name="description"
                    ),
                ),
                migrations.AddField(
                    model_name="subscriptionplan",
                    name="name_uz_cy",
                    field=models.CharField(
                        max_length=120, null=True, verbose_name="name"
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    add_uz_cy_fields_if_missing,
                    migrations.RunPython.noop,
                ),
            ],
        ),
    ]
