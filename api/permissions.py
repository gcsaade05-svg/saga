"""
Permissões da API (aula 5, "Autorização no Django").

- EhPaciente, EhMedico, EhEnfermeiro: o usuário precisa estar no grupo do
  perfil (accounts/grupos.py).
- PermissaoRequerida: a view declara `permission_required`, como no
  PermissionRequiredMixin da aula, e o usuário precisa ter essa permissão
  (recebida pelo grupo). Sem ela, a resposta é 403 Forbidden.
"""
from rest_framework.permissions import BasePermission

from accounts.grupos import ENFERMEIRO, MEDICO, PACIENTE


class _Grupo(BasePermission):
    grupo = None
    message = "Seu perfil não tem acesso a esta funcionalidade."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.groups.filter(name=self.grupo).exists())


class EhPaciente(_Grupo):
    grupo = PACIENTE


class EhMedico(_Grupo):
    grupo = MEDICO


class EhEnfermeiro(_Grupo):
    grupo = ENFERMEIRO


class PermissaoRequerida(BasePermission):
    message = "Você não tem permissão para esta ação."

    def has_permission(self, request, view):
        perms = getattr(view, "permission_required", ())
        if isinstance(perms, str):
            perms = (perms,)
        u = request.user
        return bool(u and u.is_authenticated and u.has_perms(perms))
