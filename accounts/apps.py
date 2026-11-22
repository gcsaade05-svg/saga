from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AccountsConfig(AppConfig):
    """
    Cadastro, login e logout (AUT001 e AUT002), no mesmo papel do app
    accounts da aula 5: usa o sistema de autenticação do Django, com sessão,
    e os grupos de usuários para separar os perfis.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Contas e perfis"

    def ready(self):
        from . import grupos, sinais  # noqa: F401  (registra os sinais)

        # Os grupos são criados depois das migrações, quando as permissões
        # padrão (add, change, delete, view) dos models de core já existem.
        post_migrate.connect(grupos.criar_grupos_apos_migrar, dispatch_uid="saga-grupos")
