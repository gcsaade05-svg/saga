"""
Grupos de usuários e permissões (aula 5, "Usando grupos para segmentar
usuários").

Cada perfil do SAGA é um grupo do Django. O Django cria sozinho quatro
permissões por model (add, change, delete, view), no formato
<app>.<operação>_<model>; aqui definimos quais delas cada grupo recebe.
A API confere o grupo do usuário e, nas ações de escrita, a permissão
(api/permissions.py), como o PermissionRequiredMixin da aula.
"""
from django.contrib.auth.models import Group, Permission

PACIENTE, MEDICO, ENFERMEIRO = "Paciente", "Medico", "Enfermeiro"

# Nome do grupo para cada valor de Usuario.perfil.
GRUPO_DO_PERFIL = {"PACIENTE": PACIENTE, "MEDICO": MEDICO, "ENFERMEIRO": ENFERMEIRO}

PERMISSOES = {
    PACIENTE: [
        "view_especialidade", "view_tipoprocedimento", "view_unidade",
        "view_agendamento", "add_agendamento", "change_agendamento",
        "view_solicitacaoprocedimento", "view_registroclinico",
    ],
    MEDICO: [
        "view_especialidade", "view_tipoprocedimento", "view_unidade", "view_recurso",
        "view_agendamento", "change_agendamento", "view_paciente", "view_triagem",
        "view_registroclinico", "add_registroclinico", "change_registroclinico",
        "view_solicitacaoprocedimento", "add_solicitacaoprocedimento",
        "view_requisitoprocedimento", "add_requisitoprocedimento", "change_requisitoprocedimento",
        "view_diadisponibilidade", "add_diadisponibilidade", "delete_diadisponibilidade",
    ],
    ENFERMEIRO: [
        "view_especialidade", "view_tipoprocedimento", "view_unidade",
        "view_recurso", "add_recurso", "change_recurso",
        "view_agendamento", "add_agendamento", "view_paciente",
        "view_triagem", "add_triagem",
        "view_alocacaorecurso", "change_alocacaorecurso",
        "view_solicitacaoprocedimento", "change_solicitacaoprocedimento",
    ],
}


def grupo(nome):
    """Devolve o grupo; se ele ainda não existir, cria (como no signup da aula 5)."""
    g, _ = Group.objects.get_or_create(name=nome)
    return g


def criar_grupos():
    from django.contrib.auth import get_user_model

    Usuario = get_user_model()
    for nome, codigos in PERMISSOES.items():
        perms = Permission.objects.filter(content_type__app_label="core", codename__in=codigos)
        g = grupo(nome)
        g.permissions.set(perms)
    # Usuários criados antes dos grupos (bancos de versões anteriores) entram agora.
    for perfil, nome in GRUPO_DO_PERFIL.items():
        sem_grupo = Usuario.objects.filter(perfil=perfil).exclude(groups__name=nome)
        if sem_grupo.exists():
            grupo(nome).user_set.add(*sem_grupo)


def criar_grupos_apos_migrar(sender, **kwargs):
    # O sinal é enviado uma vez por app; as permissões de core são criadas
    # pelo app auth no sinal do próprio core, logo antes deste receptor.
    if sender.name == "core":
        criar_grupos()
