"""
Endpoints da API (aula 5). Prefixo /api/v1/ definido em saga/urls.py.

Como na aula: uma rota para a coleção (/agendamentos/) e outra para o
detalhe (/agendamentos/<id>/), cada uma ligada a uma view genérica, e
rotas próprias para as ações (/agendamentos/<id>/confirmar/).
"""
from django.urls import path

from . import views

urlpatterns = [
    # Catálogo
    path("especialidades/", views.EspecialidadeList.as_view(), name="especialidades"),
    path("unidades/", views.UnidadeList.as_view(), name="unidades"),
    path("tipos-procedimento/", views.TipoProcedimentoList.as_view(), name="tipos-procedimento"),
    path("salas/", views.SalaList.as_view(), name="salas"),
    # Paciente: PAC001 a PAC004
    path("janelas/", views.JanelaList.as_view(), name="janelas"),
    path("agendamentos/", views.AgendamentoList.as_view(), name="agendamentos"),
    path("agendamentos/<int:pk>/", views.AgendamentoDetail.as_view(), name="agendamento"),
    path("agendamentos/<int:pk>/confirmar/", views.ConfirmarAgendamento.as_view(), name="confirmar"),
    path("agendamentos/<int:pk>/cancelar/", views.CancelarAgendamento.as_view(), name="cancelar"),
    path("agendamentos/<int:pk>/remarcar/", views.RemarcarAgendamento.as_view(), name="remarcar"),
    path("resultados/", views.ResultadoList.as_view(), name="resultados"),
    # Médico: MED001 a MED004
    path("disponibilidades/", views.DisponibilidadeList.as_view(), name="disponibilidades"),
    path("disponibilidades/<int:pk>/encerrar/", views.EncerrarDisponibilidade.as_view(), name="encerrar-disponibilidade"),
    path("agendamentos/<int:pk>/atendimento/", views.RegistrarAtendimento.as_view(), name="atendimento"),
    path("agendamentos/<int:pk>/registros/", views.RegistrosDoAgendamento.as_view(), name="registros"),
    path("agendamentos/<int:pk>/triagem/", views.TriagemDoAgendamento.as_view(), name="triagem-do-agendamento"),
    path("solicitacoes/", views.SolicitacaoList.as_view(), name="solicitacoes"),
    path("prontuario/<int:paciente_id>/", views.Prontuario.as_view(), name="prontuario"),
    path("registros/<int:pk>/liberar/", views.LiberarRegistro.as_view(), name="liberar-registro"),
    # Enfermeiro: aprovação, ENF001 a ENF004
    path("solicitacoes/<int:pk>/aprovar/", views.AprovarSolicitacao.as_view(), name="aprovar"),
    path("solicitacoes/<int:pk>/recusar/", views.RecusarSolicitacao.as_view(), name="recusar"),
    path("triagem/fila/", views.FilaTriagem.as_view(), name="fila-triagem"),
    path("triagem/sugerir/", views.SugerirRisco.as_view(), name="sugerir-risco"),
    path("triagens/", views.TriagemCreate.as_view(), name="triagens"),
    path("alocacoes/", views.AlocacaoList.as_view(), name="alocacoes"),
    path("alocacoes/<int:pk>/abrir/", views.AbrirOcupacao.as_view(), name="abrir-ocupacao"),
    path("alocacoes/<int:pk>/encerrar/", views.EncerrarOcupacao.as_view(), name="encerrar-ocupacao"),
    path("recursos/", views.RecursoList.as_view(), name="recursos"),
    path("recursos/<int:pk>/", views.RecursoDetail.as_view(), name="recurso"),
    path("painel/", views.Painel.as_view(), name="painel"),
    path("encaixe/", views.Encaixe.as_view(), name="encaixe"),
]
