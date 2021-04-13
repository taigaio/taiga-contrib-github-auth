from django.apps import AppConfig


class TaigaContribGithubAuthAppConfig(AppConfig):
    name = "taiga_contrib_github_auth"
    verbose_name = "Taiga contrib github auth App Config"

    def ready(self):
        from taiga.auth.services import register_auth_plugin
        from . import services
        register_auth_plugin("github", services.github_login_func)

