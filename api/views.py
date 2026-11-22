"""
API REST do SAGA. Cada view indica o caso de uso que atende.

Segue o padrão da aula 5: views genéricas do Django REST Framework
(ListAPIView, ListCreateAPIView, RetrieveAPIView, CreateAPIView...) com
`queryset`/`get_queryset` e `serializer_class`, e APIView para as ações que
não são um CRUD simples (confirmar, cancelar, abrir ocupação...).

As regras de negócio ficam em core/servicos.py; aqui ficam permissão por
perfil (grupos) e tradução de entrada e saída.
"""
from datetime import date, datetime, timedelta

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core import servicos
from core.models import (
    Agendamento,
    AlocacaoRecurso,
    Especialidade,
    HabilitacaoMedico,
    Paciente,
    Recurso,
    RegistroClinico,
    RequisitoProcedimento,
    SolicitacaoProcedimento,
    TipoProcedimento,
    Triagem,
    Unidade,
    Usuario,
)
from core.utils import sugerir_classificacao

from .permissions import EhEnfermeiro, EhMedico, EhPaciente, PermissaoRequerida
from .serializers import (
    AberturaSerializer,
    AgendamentoDetalheSerializer,
    AgendamentoSerializer,
    AlocacaoSerializer,
    AtendimentoSerializer,
    CancelamentoSerializer,
    DisponibilidadeSerializer,
    EncaixeSerializer,
    EspecialidadeSerializer,
    NovoAgendamentoSerializer,
    RecursoSerializer,
    RegistroClinicoSerializer,
    RemarcacaoSerializer,
    SolicitacaoSerializer,
    TipoProcedimentoSerializer,
    TriagemSerializer,
    UnidadeSerializer,
)


def _data(request, nome, padrao=None):
    valor = request.query_params.get(nome)
    if not valor:
        return padrao
    try:
        return date.fromisoformat(valor)
    except ValueError:
        raise ValidationError({nome: "Use o formato AAAA-MM-DD."})


def _inicio_do_dia(dia):
    return datetime.combine(dia, datetime.min.time(), tzinfo=timezone.get_current_timezone())


# ---------------------------------------------------------------------------
# Catálogo (listas de valores das telas)
# ---------------------------------------------------------------------------
class EspecialidadeList(generics.ListAPIView):
    """Especialidades com ao menos um médico habilitado ativo (PAC001, campo 1)."""

    serializer_class = EspecialidadeSerializer
    pagination_class = None

    def get_queryset(self):
        u = self.request.user
        if self.request.query_params.get("minhas") == "1" and u.perfil == Usuario.Perfil.MEDICO:
            return u.medico.especialidades_ativas()  # MED001, RN12
        qs = Especialidade.objects.all()
        if self.request.query_params.get("todas") != "1":
            qs = qs.filter(habilitacoes__situacao=HabilitacaoMedico.Situacao.ATIVA).distinct()
        return qs


class UnidadeList(generics.ListAPIView):
    queryset = Unidade.objects.all()
    serializer_class = UnidadeSerializer
    pagination_class = None


class TipoProcedimentoList(generics.ListAPIView):
    serializer_class = TipoProcedimentoSerializer
    pagination_class = None

    def get_queryset(self):
        qs = TipoProcedimento.objects.select_related("especialidade")
        modalidade = self.request.query_params.get("modalidade")
        if modalidade:
            qs = qs.filter(modalidade__in=modalidade.upper().split(","))
        return qs


class SalaList(generics.ListAPIView):
    """Lista de valores de MED001: salas ativas de uma unidade."""

    serializer_class = RecursoSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Recurso.objects.filter(tipo=Recurso.Tipo.SALA, ativo=True).select_related("unidade")
        unidade = self.request.query_params.get("unidade")
        if unidade:
            qs = qs.filter(unidade_id=unidade)
        return qs


# ---------------------------------------------------------------------------
# PAC001: busca de janelas (calculadas, não gravadas)
# ---------------------------------------------------------------------------
class JanelaList(APIView):
    permission_classes = [EhPaciente]

    def get(self, request):
        especialidade = get_object_or_404(Especialidade, pk=request.query_params.get("especialidade"))
        hoje = timezone.localdate()
        de = _data(request, "de", hoje)
        ate = _data(request, "ate", de + timedelta(days=14))
        if de < hoje:
            raise ValidationError({"de": "Igual ou posterior à data corrente."})
        if ate < de:
            raise ValidationError({"ate": "Igual ou posterior a 'A partir de'."})
        resultado = servicos.buscar_janelas_consulta(especialidade, de, ate)
        return Response(
            [
                {
                    "requisito": j["requisito"].pk,
                    "inicio": j["inicio"],
                    "fim": j["fim"],
                    "medico": str(j["medico"]),
                    "unidade": j["unidade"].nome,
                    "sala": j["sala"].nome,
                    "duracao_min": j["duracao_min"],
                    "procedimento": j["tipo"].nome,
                }
                for j in resultado
            ]
        )


# ---------------------------------------------------------------------------
# Agendamentos (PAC001 a PAC003, MED002, ENF001)
# ---------------------------------------------------------------------------
def agendamentos_visiveis(usuario):
    """
    Paciente vê os próprios; médico vê os que são de sua responsabilidade;
    enfermeiro vê os da unidade em que está lotado.
    """
    qs = Agendamento.objects.select_related(
        "paciente__usuario", "tipo_procedimento", "medico_responsavel__usuario"
    ).prefetch_related("alocacoes__recurso__unidade")
    if usuario.perfil == Usuario.Perfil.PACIENTE:
        return qs.filter(paciente__usuario=usuario)
    if usuario.perfil == Usuario.Perfil.MEDICO:
        return qs.filter(medico_responsavel__usuario=usuario)
    if usuario.perfil == Usuario.Perfil.ENFERMEIRO:
        return qs.filter(alocacoes__recurso__unidade=usuario.enfermeiro.unidade).distinct()
    return qs.none()


class AgendamentoDoUsuario:
    """Mixin: busca o agendamento só entre os que o usuário pode ver (senão, 404)."""

    def agendamento(self, pk):
        return get_object_or_404(agendamentos_visiveis(self.request.user), pk=pk)


class AgendamentoList(generics.ListCreateAPIView):
    """GET: agendamentos do usuário, com filtros. POST: PAC001 passos 6 e 7."""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        return NovoAgendamentoSerializer if self.request.method == "POST" else AgendamentoSerializer

    def get_queryset(self):
        qs = agendamentos_visiveis(self.request.user)
        dia = _data(self.request, "data")
        if dia:
            ini = _inicio_do_dia(dia)
            qs = qs.filter(inicio_planejado__gte=ini, inicio_planejado__lt=ini + timedelta(days=1))
        quando = self.request.query_params.get("quando")
        if quando == "futuros":
            qs = qs.filter(inicio_planejado__gte=timezone.now())
        elif quando == "passados":
            qs = qs.filter(inicio_planejado__lt=timezone.now()).order_by("-inicio_planejado")
        situacao = self.request.query_params.get("status")
        if situacao:
            qs = qs.filter(status__in=situacao.upper().split(","))
        return qs

    def create(self, request, *args, **kwargs):
        # Só o paciente agenda, e só consultas (RN01).
        if not EhPaciente().has_permission(request, self):
            return Response({"detail": "Apenas pacientes agendam consultas."}, status=403)
        dados = NovoAgendamentoSerializer(data=request.data)
        dados.is_valid(raise_exception=True)
        requisito = dados.validated_data["requisito"]
        ag = servicos.criar_agendamento(
            request.user.paciente, requisito.tipo_procedimento, dados.validated_data["inicio"],
            requisito=requisito,
        )
        return Response(AgendamentoDetalheSerializer(ag).data, status=status.HTTP_201_CREATED)


class AgendamentoDetail(generics.RetrieveAPIView):
    """Resumo do agendamento (PAC001 passo 8): recursos alocados e totais."""

    serializer_class = AgendamentoDetalheSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return agendamentos_visiveis(self.request.user)


class ConfirmarAgendamento(AgendamentoDoUsuario, APIView):
    """PAC002."""

    permission_classes = [EhPaciente, PermissaoRequerida]
    permission_required = "core.change_agendamento"

    def post(self, request, pk):
        ag = servicos.confirmar_presenca(self.agendamento(pk))
        return Response(AgendamentoSerializer(ag).data)


class CancelarAgendamento(AgendamentoDoUsuario, APIView):
    """PAC003, ação Cancelar."""

    permission_classes = [EhPaciente, PermissaoRequerida]
    permission_required = "core.change_agendamento"

    def post(self, request, pk):
        dados = CancelamentoSerializer(data=request.data)
        dados.is_valid(raise_exception=True)
        ag = servicos.cancelar_agendamento(self.agendamento(pk), dados.validated_data["motivo"])
        return Response(AgendamentoSerializer(ag).data)


class RemarcarAgendamento(AgendamentoDoUsuario, APIView):
    """PAC003, ação Remarcar."""

    permission_classes = [EhPaciente, PermissaoRequerida]
    permission_required = ("core.change_agendamento", "core.add_agendamento")

    def post(self, request, pk):
        dados = RemarcacaoSerializer(data=request.data)
        dados.is_valid(raise_exception=True)
        novo = servicos.remarcar_agendamento(
            self.agendamento(pk),
            dados.validated_data["inicio"],
            dados.validated_data["motivo"],
            requisito=dados.validated_data["requisito"],
        )
        return Response(AgendamentoDetalheSerializer(novo).data, status=status.HTTP_201_CREATED)


class RegistrarAtendimento(AgendamentoDoUsuario, APIView):
    """MED002: grava evolução, hipótese e conduta e marca o agendamento como Realizado."""

    permission_classes = [EhMedico, PermissaoRequerida]
    permission_required = ("core.add_registroclinico", "core.change_agendamento")

    def post(self, request, pk):
        ag = self.agendamento(pk)
        if ag.status not in (Agendamento.Status.AGENDADO, Agendamento.Status.CONFIRMADO):
            raise ValidationError("Este agendamento não está aguardando atendimento.")
        dados = AtendimentoSerializer(data=request.data)
        dados.is_valid(raise_exception=True)
        medico = request.user.medico
        for tipo, campo in [
            (RegistroClinico.Tipo.EVOLUCAO, "evolucao"),
            (RegistroClinico.Tipo.DIAGNOSTICO, "diagnostico"),
            (RegistroClinico.Tipo.CONDUTA, "conduta"),
        ]:
            RegistroClinico.objects.create(
                agendamento=ag, medico=medico, tipo=tipo, texto=dados.validated_data[campo]
            )
        ag.status = Agendamento.Status.REALIZADO
        ag.save(update_fields=["status"])
        return Response(AgendamentoDetalheSerializer(ag).data)


class RegistrosDoAgendamento(AgendamentoDoUsuario, generics.ListAPIView):
    """Registros já gravados neste atendimento (o paciente só vê os liberados, em PAC004)."""

    serializer_class = RegistroClinicoSerializer
    permission_classes = [EhMedico]
    pagination_class = None

    def get_queryset(self):
        return self.agendamento(self.kwargs["pk"]).registros.all()


class TriagemDoAgendamento(AgendamentoDoUsuario, APIView):
    """Sinais vitais da triagem mais recente, para o médico em MED002."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        t = self.agendamento(pk).triagens.first()
        return Response(TriagemSerializer(t).data if t else None)


# ---------------------------------------------------------------------------
# PAC004, MED003 e aprovação: solicitações
# ---------------------------------------------------------------------------
class SolicitacaoList(generics.ListCreateAPIView):
    """
    Médico cria (MED003), paciente acompanha (PAC004) e enfermeiro vê todas,
    para aprovar o uso dos recursos.
    """

    serializer_class = SolicitacaoSerializer
    pagination_class = None
    permission_required = "core.add_solicitacaoprocedimento"

    def get_permissions(self):
        if self.request.method == "POST":
            return [EhMedico(), PermissaoRequerida()]
        return [IsAuthenticated()]

    def get_queryset(self):
        u = self.request.user
        qs = SolicitacaoProcedimento.objects.select_related(
            "tipo_procedimento",
            "agendamento_origem__medico_responsavel__usuario",
            "agendamento_origem__paciente__usuario",
        )
        if u.perfil == Usuario.Perfil.PACIENTE:
            qs = qs.filter(agendamento_origem__paciente__usuario=u)
        elif u.perfil == Usuario.Perfil.MEDICO:
            qs = qs.filter(agendamento_origem__medico_responsavel__usuario=u)
        situacao = self.request.query_params.get("status")
        if situacao:
            qs = qs.filter(status__in=situacao.upper().split(","))
        paciente = self.request.query_params.get("paciente")
        if paciente:
            qs = qs.filter(agendamento_origem__paciente_id=paciente)
        return qs


class AprovarSolicitacao(APIView):
    """A solicitação só entra na fila e só usa recurso depois de aprovada."""

    permission_classes = [EhEnfermeiro, PermissaoRequerida]
    permission_required = "core.change_solicitacaoprocedimento"

    def post(self, request, pk):
        s = servicos.aprovar_solicitacao(get_object_or_404(SolicitacaoProcedimento, pk=pk))
        return Response(SolicitacaoSerializer(s).data)


class RecusarSolicitacao(APIView):
    permission_classes = [EhEnfermeiro, PermissaoRequerida]
    permission_required = "core.change_solicitacaoprocedimento"

    def post(self, request, pk):
        s = servicos.recusar_solicitacao(get_object_or_404(SolicitacaoProcedimento, pk=pk))
        return Response(SolicitacaoSerializer(s).data)


class ResultadoList(generics.ListAPIView):
    """PAC004: só registros explicitamente liberados pelo médico (RN11)."""

    serializer_class = RegistroClinicoSerializer
    permission_classes = [EhPaciente]
    pagination_class = None

    def get_queryset(self):
        return RegistroClinico.objects.filter(
            agendamento__paciente__usuario=self.request.user, liberado_em__isnull=False
        ).select_related("agendamento__tipo_procedimento", "medico__usuario")


# ---------------------------------------------------------------------------
# MED001: disponibilidade (gravada no requisito do procedimento)
# ---------------------------------------------------------------------------
class DisponibilidadeList(generics.ListCreateAPIView):
    serializer_class = DisponibilidadeSerializer
    permission_classes = [EhMedico, PermissaoRequerida]
    pagination_class = None

    @property
    def permission_required(self):
        if self.request.method == "POST":
            return ("core.add_requisitoprocedimento", "core.change_requisitoprocedimento")
        return "core.view_requisitoprocedimento"

    def get_queryset(self):
        # Disponibilidade das consultas nas especialidades em que o médico está habilitado.
        return (
            RequisitoProcedimento.objects.filter(
                tipo_procedimento__modalidade=TipoProcedimento.Modalidade.CONSULTA,
                tipo_procedimento__especialidade__in=self.request.user.medico.especialidades_ativas(),
            )
            .select_related("tipo_procedimento__especialidade", "recurso__unidade")
            .prefetch_related("dias")
            .order_by("tipo_procedimento__nome", "recurso__nome")
        )


class EncerrarDisponibilidade(APIView):
    """Disponibilidade com horários ocupados não se exclui: encerra a partir de uma data."""

    permission_classes = [EhMedico, PermissaoRequerida]
    permission_required = "core.change_requisitoprocedimento"

    def post(self, request, pk):
        req = get_object_or_404(DisponibilidadeList(request=request).get_queryset(), pk=pk)
        a_partir = request.data.get("a_partir_de")
        a_partir = date.fromisoformat(a_partir) if a_partir else timezone.localdate()
        novo_fim = a_partir - timedelta(days=1)
        if novo_fim < req.data_inicial:
            raise ValidationError({"a_partir_de": "Deve ser posterior à data inicial."})
        req.data_final = min(req.data_final, novo_fim)
        req.save(update_fields=["data_final"])
        return Response(DisponibilidadeSerializer(req, context={"request": request}).data)


# ---------------------------------------------------------------------------
# MED004: prontuário, liberado pelo agendamento
# ---------------------------------------------------------------------------
class Prontuario(APIView):
    """
    RN13: só com agendamento do paciente sob responsabilidade do médico e com
    prontuário liberado. RN14: o instante do acesso fica nesse agendamento.
    """

    permission_classes = [EhMedico]

    def get(self, request, paciente_id):
        medico = request.user.medico
        paciente = get_object_or_404(Paciente, pk=paciente_id)
        vinculo = servicos.registrar_acesso_prontuario(medico, paciente)
        if vinculo is None:
            return Response(
                {"detail": "Você não possui vínculo assistencial com este paciente."}, status=403
            )
        registros = RegistroClinico.objects.filter(agendamento__paciente=paciente).select_related(
            "agendamento__tipo_procedimento", "medico__usuario"
        )
        triagens = Triagem.objects.filter(agendamento__paciente=paciente).select_related(
            "enfermeiro__usuario"
        )
        return Response(
            {
                "paciente": {"id": paciente.id, "nome": str(paciente), "data_nascimento": paciente.data_nascimento},
                "acesso": {
                    "agendamento": vinculo.pk,
                    "procedimento": vinculo.tipo_procedimento.nome,
                    "inicio_planejado": vinculo.inicio_planejado,
                    "acessado_em": vinculo.prontuario_acessado_em,
                },
                "registros": RegistroClinicoSerializer(registros, many=True, context={"request": request}).data,
                "triagens": TriagemSerializer(triagens, many=True).data,
            }
        )


class LiberarRegistro(APIView):
    """RN11: ação explícita do médico responsável pelo registro."""

    permission_classes = [EhMedico, PermissaoRequerida]
    permission_required = "core.change_registroclinico"

    def post(self, request, pk):
        registro = get_object_or_404(RegistroClinico, pk=pk, medico__usuario=request.user)
        if registro.liberado_em is None:
            registro.liberado_em = timezone.now()
            registro.save(update_fields=["liberado_em"])
        return Response(RegistroClinicoSerializer(registro).data)


# ---------------------------------------------------------------------------
# ENF001: triagem
# ---------------------------------------------------------------------------
class FilaTriagem(generics.ListAPIView):
    """Agendamentos de hoje na unidade do enfermeiro, ainda sem triagem."""

    serializer_class = AgendamentoSerializer
    permission_classes = [EhEnfermeiro]
    pagination_class = None

    def get_queryset(self):
        ini = _inicio_do_dia(timezone.localdate())
        return (
            Agendamento.objects.filter(
                alocacoes__recurso__unidade=self.request.user.enfermeiro.unidade,
                inicio_planejado__gte=ini,
                inicio_planejado__lt=ini + timedelta(days=1),
                status__in=[Agendamento.Status.AGENDADO, Agendamento.Status.CONFIRMADO],
                triagens__isnull=True,
            )
            .select_related("paciente__usuario", "tipo_procedimento", "medico_responsavel__usuario")
            .prefetch_related(Prefetch("alocacoes", queryset=AlocacaoRecurso.objects.select_related("recurso__unidade")))
            .distinct()
        )


class TriagemCreate(generics.CreateAPIView):
    serializer_class = TriagemSerializer
    permission_classes = [EhEnfermeiro, PermissaoRequerida]
    permission_required = "core.add_triagem"

    def perform_create(self, serializer):
        d = serializer.validated_data
        sugerida = sugerir_classificacao(
            d["pressao_sistolica"], d["pressao_diastolica"], d["frequencia_cardiaca"],
            d["temperatura"], d["saturacao"],
        )
        triagem = Triagem(**d, enfermeiro=self.request.user.enfermeiro, classificacao_sugerida=sugerida)
        triagem.full_clean()
        triagem.save()
        serializer.instance = triagem


class SugerirRisco(APIView):
    """Sugestão de classificação enquanto o enfermeiro digita os sinais vitais."""

    permission_classes = [EhEnfermeiro]

    def post(self, request):
        try:
            valor = sugerir_classificacao(
                int(request.data["pressao_sistolica"]), int(request.data["pressao_diastolica"]),
                int(request.data["frequencia_cardiaca"]), float(request.data["temperatura"]),
                int(request.data["saturacao"]),
            )
        except (KeyError, TypeError, ValueError):
            raise ValidationError("Informe todos os sinais vitais.")
        return Response({"classificacao_sugerida": valor, "nome": Triagem.Risco(valor).label})


# ---------------------------------------------------------------------------
# ENF002: ocupação de recursos
# ---------------------------------------------------------------------------
class AlocacaoList(generics.ListAPIView):
    """Alocações de um dia (hoje, se nada for dito) na unidade do enfermeiro."""

    serializer_class = AlocacaoSerializer
    permission_classes = [EhEnfermeiro]
    pagination_class = None

    def get_queryset(self):
        ini = _inicio_do_dia(_data(self.request, "data", timezone.localdate()))
        return AlocacaoRecurso.objects.filter(
            recurso__unidade=self.request.user.enfermeiro.unidade,
            inicio_planejado__gte=ini,
            inicio_planejado__lt=ini + timedelta(days=1),
        ).select_related("recurso__unidade", "agendamento__paciente__usuario", "agendamento__tipo_procedimento")


class _AcaoNaAlocacao(APIView):
    permission_classes = [EhEnfermeiro, PermissaoRequerida]
    permission_required = "core.change_alocacaorecurso"

    def alocacao(self, pk):
        return get_object_or_404(
            AlocacaoRecurso, pk=pk, recurso__unidade=self.request.user.enfermeiro.unidade
        )


class AbrirOcupacao(_AcaoNaAlocacao):
    def post(self, request, pk):
        aloc = self.alocacao(pk)
        if aloc.status != AlocacaoRecurso.Status.PLANEJADA:
            raise ValidationError("Só alocações planejadas podem ser abertas.")
        if AlocacaoRecurso.objects.filter(recurso=aloc.recurso, status=AlocacaoRecurso.Status.EM_USO).exists():
            raise ValidationError("Este recurso já está em uso em outra alocação (RN09).")
        dados = AberturaSerializer(data=request.data)
        dados.is_valid(raise_exception=True)
        agora = timezone.now()  # RN08: relógio do servidor
        atraso = (agora - aloc.inicio_planejado).total_seconds() / 60
        motivo = dados.validated_data.get("motivo_atraso", "")
        if atraso > 30 and not motivo:
            return Response(
                {"detail": "Atraso acima de 30 minutos: informe o motivo.", "precisa_motivo": True,
                 "atraso_min": int(atraso)},
                status=400,
            )
        aloc.motivo_atraso = motivo
        aloc.motivo_atraso_detalhe = dados.validated_data.get("motivo_atraso_detalhe", "")
        aloc.full_clean()
        aloc.abrir_ocupacao(request.user.enfermeiro, agora)
        aloc.save(update_fields=["motivo_atraso", "motivo_atraso_detalhe"])
        return Response(AlocacaoSerializer(aloc).data)


class EncerrarOcupacao(_AcaoNaAlocacao):
    def post(self, request, pk):
        aloc = self.alocacao(pk)
        agora = timezone.now()
        duracao = (agora - aloc.inicio_realizado).total_seconds() / 60 if aloc.inicio_realizado else 0
        if duracao > 2 * aloc.duracao_planejada_min and not request.data.get("confirmar"):
            return Response(
                {"detail": "A duração passou do dobro da planejada. Confirme o encerramento.",
                 "precisa_confirmar": True},
                status=400,
            )
        aloc.encerrar_ocupacao(agora)
        return Response(AlocacaoSerializer(aloc).data)


# ---------------------------------------------------------------------------
# ENF003: recursos da unidade
# ---------------------------------------------------------------------------
class RecursoList(generics.ListCreateAPIView):
    serializer_class = RecursoSerializer
    permission_classes = [EhEnfermeiro, PermissaoRequerida]
    pagination_class = None

    @property
    def permission_required(self):
        return "core.add_recurso" if self.request.method == "POST" else "core.view_recurso"

    def get_queryset(self):
        return Recurso.objects.filter(unidade=self.request.user.enfermeiro.unidade)


class RecursoDetail(generics.RetrieveUpdateAPIView):
    """RN16: recurso não é excluído, só inativado (PATCH ativo=false)."""

    serializer_class = RecursoSerializer
    permission_classes = [EhEnfermeiro, PermissaoRequerida]
    permission_required = "core.change_recurso"

    def get_queryset(self):
        return Recurso.objects.filter(unidade=self.request.user.enfermeiro.unidade)


# ---------------------------------------------------------------------------
# ENF004: Painel de Ocupação e encaixe
# ---------------------------------------------------------------------------
class Painel(APIView):
    permission_classes = [EhEnfermeiro]

    def get(self, request):
        hoje = timezone.localdate()
        de = _data(request, "de", hoje - timedelta(days=7))
        ate = _data(request, "ate", hoje + timedelta(days=7))
        unidade = request.query_params.get("unidade")
        tipo = request.query_params.get("tipo")
        return Response(
            servicos.painel_ocupacao(
                de,
                ate,
                unidade=get_object_or_404(Unidade, pk=unidade) if unidade else None,
                tipo_procedimento=get_object_or_404(TipoProcedimento, pk=tipo) if tipo else None,
            )
        )


class Encaixe(APIView):
    permission_classes = [EhEnfermeiro, PermissaoRequerida]
    permission_required = "core.add_agendamento"

    def post(self, request):
        dados = EncaixeSerializer(data=request.data)
        dados.is_valid(raise_exception=True)
        ag = servicos.encaixar(dados.validated_data["solicitacao"], dados.validated_data["inicio"])
        return Response(AgendamentoDetalheSerializer(ag).data, status=status.HTTP_201_CREATED)
