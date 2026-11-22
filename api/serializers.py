"""
Serializadores da API (aula 5): convertem os models em JSON e validam a
entrada, no mesmo papel do Form e do ModelForm nas páginas do Django.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from core import servicos
from core.models import (
    Agendamento,
    AlocacaoRecurso,
    DiaDisponibilidade,
    Especialidade,
    HabilitacaoMedico,
    Recurso,
    RegistroClinico,
    RequisitoProcedimento,
    SolicitacaoProcedimento,
    TipoProcedimento,
    Triagem,
    Unidade,
)


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------
class EspecialidadeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Especialidade
        fields = ["id", "nome"]


class UnidadeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unidade
        fields = ["id", "nome", "tipo", "hora_abertura", "hora_fechamento"]


class TipoProcedimentoSerializer(serializers.ModelSerializer):
    especialidade = serializers.CharField(source="especialidade.nome")

    class Meta:
        model = TipoProcedimento
        fields = ["id", "nome", "modalidade", "especialidade", "duracao_padrao_min", "exige_preparo"]


class RecursoSerializer(serializers.ModelSerializer):
    unidade_nome = serializers.CharField(source="unidade.nome", read_only=True)

    class Meta:
        model = Recurso
        fields = ["id", "nome", "tipo", "unidade", "unidade_nome", "ativo"]

    def validate_unidade(self, unidade):
        # ENF003: o enfermeiro só cadastra recursos da própria unidade.
        enfermeiro = self.context["request"].user.enfermeiro
        if unidade != enfermeiro.unidade:
            raise serializers.ValidationError("Só é possível cadastrar recursos da sua unidade.")
        return unidade


# ---------------------------------------------------------------------------
# Agendamento e alocações
# ---------------------------------------------------------------------------
class AlocacaoSerializer(serializers.ModelSerializer):
    recurso = serializers.CharField(source="recurso.nome")
    recurso_tipo = serializers.CharField(source="recurso.tipo")
    unidade = serializers.CharField(source="recurso.unidade.nome")
    duracao_planejada_min = serializers.IntegerField(read_only=True)
    duracao_realizada_min = serializers.IntegerField(read_only=True)
    atraso_inicio_min = serializers.IntegerField(read_only=True)
    ociosidade_min = serializers.IntegerField(read_only=True)
    paciente = serializers.CharField(source="agendamento.paciente.__str__", read_only=True)
    procedimento = serializers.CharField(source="agendamento.tipo_procedimento.nome", read_only=True)

    class Meta:
        model = AlocacaoRecurso
        fields = [
            "id", "agendamento", "recurso", "recurso_tipo", "unidade", "papel", "status",
            "inicio_planejado", "fim_planejado", "inicio_realizado", "fim_realizado",
            "duracao_planejada_min", "duracao_realizada_min", "atraso_inicio_min", "ociosidade_min",
            "motivo_atraso", "motivo_atraso_detalhe", "paciente", "procedimento",
        ]


class AgendamentoSerializer(serializers.ModelSerializer):
    paciente = serializers.CharField(source="paciente.__str__")
    paciente_id = serializers.IntegerField(source="paciente.id")
    procedimento = serializers.CharField(source="tipo_procedimento.nome")
    modalidade = serializers.CharField(source="tipo_procedimento.modalidade")
    especialidade_id = serializers.IntegerField(source="tipo_procedimento.especialidade_id")
    medico = serializers.SerializerMethodField()
    unidade = serializers.SerializerMethodField()
    status_nome = serializers.CharField(source="get_status_display")
    pode_confirmar = serializers.SerializerMethodField()
    confirmacao_abre = serializers.SerializerMethodField()
    duracao_planejada_min = serializers.IntegerField(read_only=True)

    class Meta:
        model = Agendamento
        fields = [
            "id", "paciente", "paciente_id", "procedimento", "modalidade", "especialidade_id", "medico", "unidade",
            "inicio_planejado", "fim_planejado", "duracao_planejada_min", "status", "status_nome",
            "pode_confirmar", "confirmacao_abre", "confirmado_em", "cancelado_em",
            "motivo_cancelamento", "cancelamento_tardio", "requisito", "solicitacao", "remarcacao_de",
            "prontuario_liberado", "prontuario_acessado_em",
        ]

    def get_medico(self, obj):
        return str(obj.medico_responsavel) if obj.medico_responsavel else None

    def get_unidade(self, obj):
        u = obj.unidade
        return u.nome if u else None

    def get_pode_confirmar(self, obj):
        return servicos.pode_confirmar(obj)

    def get_confirmacao_abre(self, obj):
        return servicos.janela_de_confirmacao(obj)[0]


class AgendamentoDetalheSerializer(AgendamentoSerializer):
    """Resumo do Agendamento (PAC001 passo 8): recursos alocados e totais."""

    alocacoes = AlocacaoSerializer(many=True)
    totais = serializers.SerializerMethodField()

    class Meta(AgendamentoSerializer.Meta):
        fields = AgendamentoSerializer.Meta.fields + ["alocacoes", "totais"]

    def get_totais(self, obj):
        alocs = list(obj.alocacoes.all())
        return {
            "recursos": len(alocs),
            "minutos_reservados": sum(a.duracao_planejada_min for a in alocs),
            "minutos_procedimento": obj.duracao_planejada_min,
            "duracao_realizada_min": obj.duracao_realizada_min,
            "atraso_inicio_min": obj.atraso_inicio_min,
        }


REQUISITOS_DE_CONSULTA = RequisitoProcedimento.objects.filter(
    tipo_procedimento__modalidade=TipoProcedimento.Modalidade.CONSULTA,
    recurso__tipo=Recurso.Tipo.SALA,
)


class NovoAgendamentoSerializer(serializers.Serializer):
    requisito = serializers.PrimaryKeyRelatedField(queryset=REQUISITOS_DE_CONSULTA)
    inicio = serializers.DateTimeField()


class CancelamentoSerializer(serializers.Serializer):
    motivo = serializers.CharField(min_length=10, max_length=500)


class RemarcacaoSerializer(CancelamentoSerializer):
    requisito = serializers.PrimaryKeyRelatedField(queryset=REQUISITOS_DE_CONSULTA)
    inicio = serializers.DateTimeField()


# ---------------------------------------------------------------------------
# Solicitações, disponibilidade e registros
# ---------------------------------------------------------------------------
class SolicitacaoSerializer(serializers.ModelSerializer):
    procedimento = serializers.CharField(source="tipo_procedimento.nome", read_only=True)
    modalidade = serializers.CharField(source="tipo_procedimento.modalidade", read_only=True)
    # Médico e paciente vêm do agendamento de origem: não são colunas da solicitação.
    paciente = serializers.IntegerField(source="agendamento_origem.paciente_id", read_only=True)
    paciente_nome = serializers.CharField(source="agendamento_origem.paciente.__str__", read_only=True)
    medico_nome = serializers.SerializerMethodField()
    origem_em = serializers.DateTimeField(source="agendamento_origem.inicio_planejado", read_only=True)
    prioridade_nome = serializers.CharField(source="get_prioridade_display", read_only=True)
    status_nome = serializers.CharField(source="get_status_display", read_only=True)
    posicao_na_fila = serializers.SerializerMethodField()

    class Meta:
        model = SolicitacaoProcedimento
        fields = [
            "id", "agendamento_origem", "origem_em", "paciente", "paciente_nome", "tipo_procedimento",
            "procedimento", "modalidade", "medico_nome", "prioridade", "prioridade_nome",
            "justificativa", "criada_em", "status", "status_nome", "aprovada", "aprovada_em",
            "posicao_na_fila",
        ]
        read_only_fields = ["criada_em", "status", "aprovada", "aprovada_em"]

    def get_medico_nome(self, obj):
        m = obj.agendamento_origem.medico_responsavel
        return str(m) if m else None

    def get_posicao_na_fila(self, obj):
        return servicos.posicao_na_fila(obj)

    def validate_agendamento_origem(self, ag):
        # MED003: a solicitação nasce de um atendimento do próprio médico.
        request = self.context["request"]
        if ag.medico_responsavel_id != request.user.medico.pk:
            raise serializers.ValidationError("O agendamento de origem precisa ser um atendimento seu.")
        if ag.status == Agendamento.Status.CANCELADO:
            raise serializers.ValidationError("O agendamento de origem foi cancelado.")
        return ag

    def validate_tipo_procedimento(self, tipo):
        if tipo.modalidade == TipoProcedimento.Modalidade.CONSULTA:
            raise serializers.ValidationError("Consultas não são solicitadas: o paciente agenda direto (RN01).")
        return tipo

    def validate_justificativa(self, texto):
        if len(texto.strip()) < 20:
            raise serializers.ValidationError("Mínimo de 20 caracteres.")
        return texto


class DisponibilidadeSerializer(serializers.ModelSerializer):
    """
    MED001. A disponibilidade publicada é gravada no requisito da consulta
    (TipoProcedimento de consulta da especialidade x sala), com os dias da
    semana em DiaDisponibilidade. Publicar de novo na mesma sala substitui o
    período anterior daquele requisito.
    """

    especialidade = serializers.PrimaryKeyRelatedField(queryset=Especialidade.objects.all(), write_only=True)
    sala = serializers.PrimaryKeyRelatedField(
        source="recurso", queryset=Recurso.objects.filter(tipo=Recurso.Tipo.SALA, ativo=True)
    )
    duracao_consulta_min = serializers.IntegerField(source="tempo_ocupacao_min", min_value=10, max_value=120)
    dias = serializers.ListField(child=serializers.IntegerField(min_value=0, max_value=6), write_only=True)
    dias_semana = serializers.SerializerMethodField()
    especialidade_nome = serializers.CharField(source="tipo_procedimento.especialidade.nome", read_only=True)
    procedimento = serializers.CharField(source="tipo_procedimento.nome", read_only=True)
    sala_nome = serializers.CharField(source="recurso.nome", read_only=True)
    unidade_nome = serializers.CharField(source="recurso.unidade.nome", read_only=True)
    vagas_livres = serializers.SerializerMethodField()
    agendamentos_futuros = serializers.SerializerMethodField()

    class Meta:
        model = RequisitoProcedimento
        fields = [
            "id", "especialidade", "especialidade_nome", "procedimento", "sala", "sala_nome",
            "unidade_nome", "data_inicial", "data_final", "hora_inicio", "hora_fim",
            "duracao_consulta_min", "dias", "dias_semana", "vagas_livres", "agendamentos_futuros",
        ]
        validators = []  # o par (procedimento, sala) é tratado no create: publicar de novo substitui

    def get_dias_semana(self, obj):
        return [d.get_dia_semana_display() for d in obj.dias.all()]

    def _ocupadas(self, obj):
        return set(
            obj.agendamentos.exclude(status=Agendamento.Status.CANCELADO)
            .filter(inicio_planejado__gte=timezone.now())
            .values_list("inicio_planejado", flat=True)
        )

    def get_agendamentos_futuros(self, obj):
        return len(self._ocupadas(obj))

    def get_vagas_livres(self, obj):
        hoje = timezone.localdate()
        if obj.data_final < hoje:
            return 0
        de = max(hoje, obj.data_inicial)
        ate = min(obj.data_final, hoje + timedelta(days=servicos.JANELA_MAXIMA_DIAS))
        ocupadas = self._ocupadas(obj)
        agora = timezone.now()
        return sum(1 for i, _ in obj.janelas(de, ate) if i > agora and i not in ocupadas)

    def validate(self, dados):
        if not dados.get("dias"):
            raise serializers.ValidationError({"dias": "Escolha ao menos um dia da semana."})
        if dados["data_inicial"] < timezone.localdate():
            raise serializers.ValidationError({"data_inicial": "Igual ou posterior à data corrente."})
        if (dados["data_final"] - dados["data_inicial"]).days > 180:
            raise serializers.ValidationError({"data_final": "No máximo 180 dias após a data inicial."})
        if dados["tempo_ocupacao_min"] % 5:
            raise serializers.ValidationError({"duracao_consulta_min": "Use um múltiplo de 5 minutos."})
        # RN12: só publica em especialidade na qual tenha habilitação ativa.
        medico = self.context["request"].user.medico
        esp = dados["especialidade"]
        if not HabilitacaoMedico.objects.filter(
            medico=medico, especialidade=esp, situacao=HabilitacaoMedico.Situacao.ATIVA
        ).exists():
            raise serializers.ValidationError({"especialidade": "Você não tem habilitação ativa nesta especialidade."})
        tipo = servicos.tipo_consulta_da(esp)
        if tipo is None:
            raise serializers.ValidationError({"especialidade": "Não há consulta cadastrada para esta especialidade."})
        dados["tipo_procedimento"] = tipo
        provisorio = RequisitoProcedimento(
            **{k: v for k, v in dados.items() if k not in ("dias", "especialidade")}
        )
        provisorio.clean()
        # A sala não pode ter duas consultas publicadas no mesmo horário.
        conflito = (
            RequisitoProcedimento.objects.filter(
                recurso=dados["recurso"],
                tipo_procedimento__modalidade=TipoProcedimento.Modalidade.CONSULTA,
                data_inicial__lte=dados["data_final"],
                data_final__gte=dados["data_inicial"],
                hora_inicio__lt=dados["hora_fim"],
                hora_fim__gt=dados["hora_inicio"],
                dias__dia_semana__in=dados["dias"],
            )
            .exclude(tipo_procedimento=tipo)
            .select_related("tipo_procedimento")
            .first()
        )
        if conflito:
            raise serializers.ValidationError(
                f"Conflito: a sala já está publicada para {conflito.tipo_procedimento.nome} nesse horário "
                f"({conflito.hora_inicio:%H:%M} às {conflito.hora_fim:%H:%M})."
            )
        return dados

    @transaction.atomic
    def create(self, dados):
        dias = sorted(set(dados.pop("dias")))
        dados.pop("especialidade")
        requisito, _ = RequisitoProcedimento.objects.update_or_create(
            tipo_procedimento=dados.pop("tipo_procedimento"),
            recurso=dados.pop("recurso"),
            defaults={**dados, "obrigatorio": True},
        )
        requisito.dias.all().delete()
        DiaDisponibilidade.objects.bulk_create(
            DiaDisponibilidade(requisito=requisito, dia_semana=d) for d in dias
        )
        return requisito


class RegistroClinicoSerializer(serializers.ModelSerializer):
    tipo_nome = serializers.CharField(source="get_tipo_display", read_only=True)
    medico_nome = serializers.CharField(source="medico.__str__", read_only=True)
    procedimento = serializers.CharField(source="agendamento.tipo_procedimento.nome", read_only=True)
    data_atendimento = serializers.DateTimeField(source="agendamento.inicio_planejado", read_only=True)
    pode_liberar = serializers.SerializerMethodField()

    class Meta:
        model = RegistroClinico
        fields = [
            "id", "agendamento", "tipo", "tipo_nome", "texto", "medico_nome", "procedimento",
            "data_atendimento", "criado_em", "liberado_em", "pode_liberar",
        ]

    def get_pode_liberar(self, obj):
        """RN11: só o médico autor libera o registro ao paciente."""
        request = self.context.get("request")
        return bool(request and obj.liberado_em is None and obj.medico.usuario_id == request.user.id)


class AtendimentoSerializer(serializers.Serializer):
    """MED002: os três campos viram três registros clínicos."""

    evolucao = serializers.CharField(min_length=20)
    diagnostico = serializers.CharField(min_length=10)
    conduta = serializers.CharField(min_length=10)


class TriagemSerializer(serializers.ModelSerializer):
    enfermeiro_nome = serializers.CharField(source="enfermeiro.__str__", read_only=True)
    classificacao_nome = serializers.CharField(source="get_classificacao_risco_display", read_only=True)
    sobrepos_sugestao = serializers.BooleanField(read_only=True)

    class Meta:
        model = Triagem
        fields = [
            "id", "agendamento", "enfermeiro_nome", "pressao_sistolica", "pressao_diastolica",
            "frequencia_cardiaca", "temperatura", "saturacao", "classificacao_sugerida",
            "classificacao_risco", "classificacao_nome", "observacoes", "realizada_em",
            "sobrepos_sugestao",
        ]
        read_only_fields = ["classificacao_sugerida", "realizada_em"]
        extra_kwargs = {
            "pressao_sistolica": {"min_value": 60, "max_value": 260},
            "pressao_diastolica": {"min_value": 30, "max_value": 160},
            "frequencia_cardiaca": {"min_value": 20, "max_value": 250},
            "temperatura": {"min_value": 30, "max_value": 45},
            "saturacao": {"min_value": 50, "max_value": 100},
        }


class AberturaSerializer(serializers.Serializer):
    motivo_atraso = serializers.ChoiceField(choices=AlocacaoRecurso.MotivoAtraso.choices, required=False, allow_blank=True)
    motivo_atraso_detalhe = serializers.CharField(max_length=500, required=False, allow_blank=True)


class EncaixeSerializer(serializers.Serializer):
    solicitacao = serializers.PrimaryKeyRelatedField(
        queryset=SolicitacaoProcedimento.objects.filter(
            status=SolicitacaoProcedimento.Status.NA_FILA, aprovada=True
        )
    )
    inicio = serializers.DateTimeField()

    def validate_inicio(self, inicio):
        if inicio <= timezone.now() + timedelta(minutes=5):
            raise serializers.ValidationError("O encaixe precisa ser em horário futuro.")
        return inicio
