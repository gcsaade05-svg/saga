"""Ao salvar um usuário, ele entra no grupo do seu perfil (aula 5, signup)."""
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .grupos import GRUPO_DO_PERFIL, grupo


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def colocar_no_grupo_do_perfil(sender, instance, raw=False, **kwargs):
    if raw or not instance.perfil:
        return
    certo = grupo(GRUPO_DO_PERFIL[instance.perfil])
    outros = instance.groups.filter(name__in=GRUPO_DO_PERFIL.values()).exclude(pk=certo.pk)
    if outros.exists():
        instance.groups.remove(*outros)
    if not instance.groups.filter(pk=certo.pk).exists():
        instance.groups.add(certo)
