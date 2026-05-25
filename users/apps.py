from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "users"
    verbose_name = "Bot foydalanuvchilari"

    def ready(self):
        from config.admin_uzbek import apply_uzbek_admin

        apply_uzbek_admin()
