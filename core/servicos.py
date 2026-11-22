"""
Regras de negócio do SAGA.

Fica aqui tudo o que mais de um lugar precisa: a API, o comando seed e os
testes. Assim a regra "a combinação inteira precisa estar livre" (RN02) existe
em um único ponto do código.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DurationField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import (
    Agendamento,
    AlocacaoRecurso,
    HabilitacaoMedico,
    Medico,
    Recurso,
    RequisitoProcedimento,
    SolicitacaoProcedimento,
    TipoProcedimento,
)

JANELA_MAXIMA_DIAS = 90  # RN18
CONFIRMACAO_ABRE_H = 72  # RN05
CONFIRMACAO_FECHA_H = 24  # RN05
OCIOSIDADE_MINIMA_MIN = 60  # RN17


class JanelaOcupada(Exception):
    """A janela deixou de estar livre entre a busca e a gravação (PAC001, fluxo b)."""


# ---------------------------------------------------------------------------
# Quais recursos um procedimento consome
# ---------------------------------------------------------------------------
@dataclass
class ItemAlocacao:
    recurso: Recurso
    ocupacao_min: int
    setup_min: int = 0
    requisito: RequisitoProcedimento = None

    @property
    def span(self):
        # O setup ocupa o recurso, mas não aparece na duração mostrada ao paciente.
        return timedelta(minutes=self.ocupacao_min + self.setup_min)

    @property
    def papel(self):
        if self.recurso.tipo == Recurso.Tipo.SALA:
            return AlocacaoRecurso.Papel.PRINCIPAL
        return AlocacaoRecurso.Papel.APOIO


def _requisitos(tipo):
    """Requisitos obrigatórios com recurso e dias carregados (usa o prefetch se houver)."""
    return [r for r in tipo.requisitos.all() if r.obrigatorio]


def salas_de_consulta(tipo):
    """Na consulta, cada sala do catálogo é uma alternativa com disponibilidade própria."""
    return [r for r in _requisitos(tipo) if r.recurso.tipo == Recurso.Tipo.SALA]


def recursos_necessarios(tipo, requisito_sala=None):
    """
    Lista os recursos que um agendamento vai ocupar, cada um com o requisito
    que traz a sua disponibilidade.

    Consulta: a sala escolhida (uma das alternativas do catálogo) mais os
    equipamentos obrigatórios. Exame e cirurgia: todos os requisitos
    obrigatórios juntos (RN02). O médico não é recurso: a agenda dele é
    verificada à parte, pelos agendamentos de que é responsável (RN03).
    """
    itens = []
    for req in _requisitos(tipo):
        if tipo.modalidade == TipoProcedimento.Modalidade.CONSULTA and req.recurso.tipo == Recurso.Tipo.SALA:
            continue
        itens.append(ItemAlocacao(req.recurso, req.tempo_ocupacao_min, req.tempo_setup_min, req))
    if requisito_sala is not None:
        itens.insert(
            0, ItemAlocacao(requisito_sala.recurso, requisito_sala.tempo_ocupacao_min, 0, requisito_sala)
        )
    return itens


def duracao_do(tipo, requisito_sala=None):
    if tipo.modalidade == TipoProcedimento.Modalidade.CONSULTA and requisito_sala is not None:
        return requisito_sala.tempo_ocupacao_min
    return tipo.duracao_padrao_min


def requisito_principal(itens):
    """O requisito da sala, gravado em Agendamento.requisito."""
    return next((i.requisito for i in itens if i.recurso.tipo == Recurso.Tipo.SALA), None)


class MapaOcupacao:
    """
    Carrega de uma vez as alocações de um conjunto de recursos num período e
    responde "está livre?" em memória. Evita uma consulta por janela candidata,
    o que torna a busca de PAC001 rápida mesmo para 90 dias.
    """

    def __init__(self, recurso_ids, de, ate):
        self.ocupado = defaultdict(list)
        qs = (
            AlocacaoRecurso.objects.filter(recurso_id__in=set(recurso_ids))
            .exclude(status=AlocacaoRecurso.Status.LIBERADA)
            .filter(inicio_planejado__lt=ate, fim_planejado__gt=de)
            .values_list("recurso_id", "inicio_planejado", "fim_planejado")
        )
        for rid, ini, fim in qs:
            self.ocupado[rid].append((ini, fim))

    def livre(self, recurso_id, inicio, fim):
        return all(fim <= i or inicio >= f for i, f in self.ocupado[recurso_id])

    def reservar(self, recurso_id, inicio, fim):
        self.ocupado[recurso_id].append((inicio, fim))


class AgendaMedicos(MapaOcupacao):
    """Mesmo princípio do mapa, para a agenda dos médicos (RN03)."""

    def __init__(self, medico_ids, de, ate):  # noqa: D401 (reaproveita livre/reservar)
        self.ocupado = defaultdict(list)
        qs = (
            Agendamento.objects.filter(medico_responsavel_id__in=set(medico_ids))
            .exclude(status=Agendamento.Status.CANCELADO)
            .filter(inicio_planejado__lt=ate, fim_planejado__gt=de)
            .values_list("medico_responsavel_id", "inicio_planejado", "fim_planejado")
        )
        for mid, ini, fim in qs:
            self.ocupado[mid].append((ini, fim))


def dentro_da_disponibilidade(itens, inicio):
    """Cada recurso precisa estar disponível para este procedimento na janela inteira."""
    return all(
        item.requisito is None or item.requisito.cobre(inicio, inicio + item.span) for item in itens
    )


def combinacao_livre(itens, inicio, mapa=None, ignorar_agendamento=None):
    """RN02: só serve se todos os recursos estiverem disponíveis e livres ao mesmo tempo."""
    if not dentro_da_disponibilidade(itens, inicio):
        return False
    for item in itens:
        if not item.recurso.ativo:
            return False
        fim = inicio + item.span
        if mapa is not None:
            if not mapa.livre(item.recurso.pk, inicio, fim):
                return False
        elif not item.recurso.livre_em(inicio, fim, ignorar_agendamento):
            return False
    return True


def medicos_habilitados(especialidade):
    return list(
        Medico.objects.filter(
            habilitacoes__especialidade=especialidade,
            habilitacoes__situacao=HabilitacaoMedico.Situacao.ATIVA,
            usuario__is_active=True,
        )
        .select_related("usuario")
        .order_by("id")
    )


def escolher_medico(medicos, inicio, fim, preferido=None, agenda=None):
    """
    RN03 e RN12: o médico responsável é um habilitado ativo na especialidade,
    livre na janela. Quem pediu o procedimento tem preferência.
    """
    ordem = sorted(medicos, key=lambda m: 0 if preferido and m.pk == preferido.pk else 1)
    for m in ordem:
        livre = agenda.livre(m.pk, inicio, fim) if agenda is not None else m.livre_em(inicio, fim)
        if livre:
            return m
    return None


# ---------------------------------------------------------------------------
# PAC001: busca de janelas de consulta
# ---------------------------------------------------------------------------
def tipo_consulta_da(especialidade):
    return TipoProcedimento.objects.filter(
        especialidade=especialidade, modalidade=TipoProcedimento.Modalidade.CONSULTA
    ).first()


def _carrega_tipo(tipo):
    """Recarrega o tipo com requisitos, recursos e dias em poucas consultas."""
    return (
        TipoProcedimento.objects.prefetch_related("requisitos__recurso__unidade", "requisitos__dias")
        .get(pk=tipo.pk)
    )


def buscar_janelas_consulta(especialidade, de, ate=None, agora=None):
    agora = agora or timezone.now()
    ate = ate or de
    if (ate - de).days > JANELA_MAXIMA_DIAS:
        raise ValidationError(f"O período de busca é de no máximo {JANELA_MAXIMA_DIAS} dias.")
    tipo = tipo_consulta_da(especialidade)
    if tipo is None:
        return []
    tipo = _carrega_tipo(tipo)
    salas = [
        r for r in salas_de_consulta(tipo)
        if r.recurso.ativo and r.data_inicial <= ate and r.data_final >= de
    ]
    medicos = medicos_habilitados(especialidade)
    if not salas or not medicos:
        return []

    tz = timezone.get_current_timezone()
    inicio_periodo = datetime.combine(de, time.min, tzinfo=tz)
    fim_periodo = datetime.combine(ate + timedelta(days=1), time.min, tzinfo=tz)
    planos = [(r, recursos_necessarios(tipo, r)) for r in salas]
    mapa = MapaOcupacao([i.recurso.pk for _, itens in planos for i in itens], inicio_periodo, fim_periodo)
    agenda = AgendaMedicos([m.pk for m in medicos], inicio_periodo, fim_periodo)

    janelas = []
    for req, itens in planos:
        for inicio, fim in req.janelas(de, ate):
            if inicio <= agora or not combinacao_livre(itens, inicio, mapa):
                continue
            medico = escolher_medico(medicos, inicio, fim, agenda=agenda)
            if medico is None:
                continue
            janelas.append(
                {
                    "requisito": req,
                    "tipo": tipo,
                    "inicio": inicio,
                    "fim": fim,
                    "medico": medico,
                    "unidade": req.recurso.unidade,
                    "sala": req.recurso,
                    "duracao_min": req.tempo_ocupacao_min,
                }
            )
    janelas.sort(key=lambda j: (j["inicio"], j["sala"].nome))
    return janelas


# ---------------------------------------------------------------------------
# Criação, confirmação, cancelamento e remarcação
# ---------------------------------------------------------------------------
@transaction.atomic
def criar_agendamento(
    paciente,
    tipo,
    inicio,
    requisito=None,
    solicitacao=None,
    remarcacao_de=None,
    medico=None,
):
    """
    PAC001 passos 6 e 7, e encaixe de ENF004.

    Revalida dentro da transação: entre a listagem e o clique outro paciente
    pode ter ocupado a mesma janela.
    """
    tipo = _carrega_tipo(tipo)
    consulta = tipo.modalidade == TipoProcedimento.Modalidade.CONSULTA
    if consulta:
        if requisito is None or requisito.tipo_procedimento_id != tipo.pk:
            raise ValidationError("Escolha um horário publicado para esta consulta.")
        if requisito.recurso.tipo != Recurso.Tipo.SALA:
            raise ValidationError("A disponibilidade da consulta é a de uma sala.")
        if inicio not in {i for i, _ in requisito.janelas(inicio.date(), inicio.date())}:
            raise ValidationError("O horário não pertence à disponibilidade publicada.")
    else:
        if solicitacao is None:
            raise ValidationError("Exames e cirurgias só são agendados a partir de solicitação (RN01).")
        if not solicitacao.aprovada:
            raise ValidationError("A solicitação ainda não foi aprovada para uso dos recursos.")
        requisito = None

    itens = recursos_necessarios(tipo, requisito)
    if not itens:
        raise ValidationError("O procedimento não tem recursos cadastrados no catálogo.")
    if not dentro_da_disponibilidade(itens, inicio):
        raise ValidationError("O horário está fora da disponibilidade de algum recurso do procedimento.")
    if not combinacao_livre(itens, inicio):
        raise JanelaOcupada("Este horário acabou de ser ocupado.")

    duracao = duracao_do(tipo, requisito)
    fim = inicio + timedelta(minutes=duracao)
    preferido = medico or (solicitacao.medico if solicitacao is not None else None)
    responsavel = escolher_medico(medicos_habilitados(tipo.especialidade), inicio, fim, preferido)
    if responsavel is None:
        raise JanelaOcupada("Nenhum médico habilitado está livre neste horário.")

    agendamento = Agendamento(
        paciente=paciente,
        tipo_procedimento=tipo,
        medico_responsavel=responsavel,
        requisito=requisito or requisito_principal(itens),
        solicitacao=solicitacao,
        remarcacao_de=remarcacao_de,
        inicio_planejado=inicio,
        fim_planejado=fim,
        # RN13: o agendamento libera ao médico responsável o prontuário do paciente.
        prontuario_liberado=True,
    )
    agendamento.full_clean()
    agendamento.save()
    AlocacaoRecurso.objects.bulk_create(
        [
            AlocacaoRecurso(
                agendamento=agendamento,
                recurso=item.recurso,
                papel=item.papel,
                inicio_planejado=inicio,
                fim_planejado=inicio + item.span,
            )
            for item in itens
        ]
    )
    if solicitacao is not None:
        solicitacao.status = SolicitacaoProcedimento.Status.AGENDADA
        solicitacao.save(update_fields=["status"])
    return agendamento


def janela_de_confirmacao(agendamento):
    abre = agendamento.inicio_planejado - timedelta(hours=CONFIRMACAO_ABRE_H)
    fecha = agendamento.inicio_planejado - timedelta(hours=CONFIRMACAO_FECHA_H)
    return abre, fecha


def pode_confirmar(agendamento, agora=None):
    agora = agora or timezone.now()
    abre, fecha = janela_de_confirmacao(agendamento)
    return agendamento.status == Agendamento.Status.AGENDADO and abre <= agora <= fecha


def confirmar_presenca(agendamento, agora=None):
    """PAC002."""
    agora = agora or timezone.now()
    if agendamento.status != Agendamento.Status.AGENDADO:
        raise ValidationError("Só agendamentos com situação Agendado podem ser confirmados.")
    abre, fecha = janela_de_confirmacao(agendamento)
    if agora < abre:
        raise ValidationError(
            f"A confirmação abre em {timezone.localtime(abre):%d/%m às %H:%M}."
        )
    if agora > fecha:
        raise ValidationError("O prazo de confirmação já terminou.")
    agendamento.status = Agendamento.Status.CONFIRMADO
    agendamento.confirmado_em = agora
    agendamento.save(update_fields=["status", "confirmado_em"])
    return agendamento


@transaction.atomic
def cancelar_agendamento(agendamento, motivo, agora=None):
    """PAC003. RN07: as alocações viram "Liberada sem uso"."""
    agora = agora or timezone.now()
    if agendamento.status not in (Agendamento.Status.AGENDADO, Agendamento.Status.CONFIRMADO):
        raise ValidationError("Este agendamento não pode mais ser cancelado.")
    if len((motivo or "").strip()) < 10:
        raise ValidationError({"motivo": "Informe o motivo com ao menos 10 caracteres."})
    agendamento.status = Agendamento.Status.CANCELADO
    agendamento.cancelado_em = agora
    agendamento.motivo_cancelamento = motivo.strip()
    agendamento.cancelamento_tardio = agendamento.inicio_planejado - agora < timedelta(hours=24)
    # Agendamento cancelado não sustenta mais o vínculo assistencial (RN13).
    agendamento.prontuario_liberado = False
    agendamento.save(
        update_fields=[
            "status", "cancelado_em", "motivo_cancelamento", "cancelamento_tardio",
            "prontuario_liberado",
        ]
    )
    agendamento.alocacoes.update(status=AlocacaoRecurso.Status.LIBERADA)
    if agendamento.solicitacao_id:
        SolicitacaoProcedimento.objects.filter(pk=agendamento.solicitacao_id).update(
            status=SolicitacaoProcedimento.Status.NA_FILA
        )
    return agendamento


@transaction.atomic
def remarcar_agendamento(agendamento, novo_inicio, motivo, requisito=None, agora=None):
    """PAC003 com ação Remarcar: cancela o original e cria o novo apontando para ele."""
    cancelar_agendamento(agendamento, motivo, agora)
    return criar_agendamento(
        paciente=agendamento.paciente,
        tipo=agendamento.tipo_procedimento,
        inicio=novo_inicio,
        medico=agendamento.medico_responsavel,
        requisito=requisito,
        solicitacao=agendamento.solicitacao,
        remarcacao_de=agendamento,
    )


@transaction.atomic
def liberar_nao_confirmados(agora=None):
    """RN06: sem confirmação até 24 h antes, a janela volta para a agenda."""
    agora = agora or timezone.now()
    limite = agora + timedelta(hours=CONFIRMACAO_FECHA_H)
    vencidos = Agendamento.objects.filter(
        status=Agendamento.Status.AGENDADO, inicio_planejado__lte=limite, inicio_planejado__gt=agora
    )
    total = 0
    for ag in vencidos:
        ag.status = Agendamento.Status.CANCELADO
        ag.cancelado_em = agora
        ag.motivo_cancelamento = "Liberado automaticamente por falta de confirmação (RN06)."
        ag.prontuario_liberado = False
        ag.save(update_fields=["status", "cancelado_em", "motivo_cancelamento", "prontuario_liberado"])
        ag.alocacoes.update(status=AlocacaoRecurso.Status.LIBERADA)
        total += 1
    return total


# ---------------------------------------------------------------------------
# PAC004 e RN13
# ---------------------------------------------------------------------------
def posicao_na_fila(solicitacao):
    """Posição dentro da fila do mesmo procedimento, pela ordem de RN04."""
    if solicitacao.status != SolicitacaoProcedimento.Status.NA_FILA:
        return None
    a_frente = SolicitacaoProcedimento.objects.filter(
        status=SolicitacaoProcedimento.Status.NA_FILA,
        tipo_procedimento=solicitacao.tipo_procedimento,
    ).filter(
        Q(prioridade__gt=solicitacao.prioridade)
        | Q(prioridade=solicitacao.prioridade, criada_em__lt=solicitacao.criada_em)
    )
    return a_frente.count() + 1


def agendamento_de_vinculo(medico, paciente):
    """
    RN13: o vínculo assistencial é um agendamento do paciente sob
    responsabilidade do médico, com o prontuário liberado. Devolve o mais
    recente, ou None se não houver vínculo.
    """
    return (
        Agendamento.objects.filter(
            medico_responsavel=medico, paciente=paciente, prontuario_liberado=True
        )
        .exclude(status=Agendamento.Status.CANCELADO)
        .order_by("-inicio_planejado")
        .first()
    )


def tem_vinculo_assistencial(medico, paciente):
    return agendamento_de_vinculo(medico, paciente) is not None


def registrar_acesso_prontuario(medico, paciente, agora=None):
    """
    RN14: o instante do último acesso fica no agendamento que deu o vínculo.
    Sem vínculo, nada é aberto e a API responde 403.
    """
    ag = agendamento_de_vinculo(medico, paciente)
    if ag is not None:
        ag.prontuario_acessado_em = agora or timezone.now()
        ag.save(update_fields=["prontuario_acessado_em"])
    return ag


@transaction.atomic
def aprovar_solicitacao(solicitacao, agora=None):
    """A solicitação só entra na fila e só aloca recurso depois de aprovada."""
    solicitacao.aprovar(agora)
    return solicitacao


@transaction.atomic
def recusar_solicitacao(solicitacao):
    if solicitacao.status != SolicitacaoProcedimento.Status.AGUARDANDO_APROVACAO:
        raise ValidationError("Esta solicitação não está aguardando aprovação.")
    solicitacao.status = SolicitacaoProcedimento.Status.CANCELADA
    solicitacao.save(update_fields=["status"])
    return solicitacao


# ---------------------------------------------------------------------------
# ENF004: Painel de Ocupação
# ---------------------------------------------------------------------------
def _horas(td):
    if td is None:
        return 0.0
    if isinstance(td, (int, float)):  # alguns bancos devolvem microssegundos
        return td / 3_600_000_000
    return td.total_seconds() / 3600


def painel_ocupacao(de, ate, unidade=None, tipo_procedimento=None, agora=None):
    """
    Entidade multidimensional analítica.

    Dimensões: recurso, dia, unidade, tipo de procedimento.
    Medidas: horas planejadas, realizadas e ociosas, taxa de ocupação,
    atraso médio, taxa de ausência.

    A tabela cruzada é agregada pelo banco (GROUP BY recurso, dia), e não em
    memória, como pedem os requerimentos não funcionais.
    """
    agora = agora or timezone.now()
    if ate < de:
        raise ValidationError("A data final deve ser igual ou posterior à inicial.")
    if (ate - de).days > JANELA_MAXIMA_DIAS:
        raise ValidationError(f"O painel considera no máximo {JANELA_MAXIMA_DIAS} dias.")

    tz = timezone.get_current_timezone()
    inicio = datetime.combine(de, time.min, tzinfo=tz)
    fim = datetime.combine(ate + timedelta(days=1), time.min, tzinfo=tz)

    base = AlocacaoRecurso.objects.filter(inicio_planejado__gte=inicio, inicio_planejado__lt=fim)
    if unidade:
        base = base.filter(recurso__unidade=unidade)
    if tipo_procedimento:
        base = base.filter(agendamento__tipo_procedimento=tipo_procedimento)

    duracao_real = ExpressionWrapper(
        F("fim_realizado") - F("inicio_realizado"), output_field=DurationField()
    )
    duracao_plan = ExpressionWrapper(
        F("fim_planejado") - F("inicio_planejado"), output_field=DurationField()
    )
    # Só entra no "planejado" o que já deveria ter acontecido; senão a agenda
    # futura apareceria como ociosidade.
    cruzada = (
        base.annotate(dia=TruncDate("inicio_planejado", tzinfo=tz))
        .values("recurso_id", "recurso__nome", "recurso__tipo", "recurso__unidade__nome", "dia")
        .annotate(
            realizado=Sum(duracao_real),
            planejado=Sum(duracao_plan, filter=Q(fim_planejado__lte=agora)),
        )
        .order_by("recurso__unidade__nome", "recurso__nome", "dia")
    )

    dias = []
    d = de
    while d <= ate:
        dias.append(d)
        d += timedelta(days=1)

    linhas = {}
    total_coluna = defaultdict(float)
    horas_planejadas = horas_realizadas = 0.0
    for row in cruzada:
        rid = row["recurso_id"]
        linha = linhas.setdefault(
            rid,
            {
                "recurso_id": rid,
                "recurso": row["recurso__nome"],
                "tipo": row["recurso__tipo"],
                "unidade": row["recurso__unidade__nome"],
                "valores": {},
                "total": 0.0,
            },
        )
        real = round(_horas(row["realizado"]), 2)
        linha["valores"][row["dia"].isoformat()] = real
        linha["total"] = round(linha["total"] + real, 2)
        total_coluna[row["dia"].isoformat()] += real
        horas_realizadas += real
        horas_planejadas += _horas(row["planejado"])

    # Medidas de agendamento (não de alocação): atraso e ausência.
    atrasos = [
        (a.inicio_realizado - a.inicio_planejado).total_seconds() / 60
        for a in base.filter(inicio_realizado__isnull=False).only(
            "inicio_realizado", "inicio_planejado"
        )
    ]
    agendamentos = Agendamento.objects.filter(alocacoes__in=base).distinct()
    realizados = agendamentos.filter(status=Agendamento.Status.REALIZADO).count()
    ausencias = agendamentos.filter(status=Agendamento.Status.AUSENCIA).count()
    liberadas = base.filter(status=AlocacaoRecurso.Status.LIBERADA)

    return {
        "periodo": {"de": de.isoformat(), "ate": ate.isoformat()},
        "dias": [x.isoformat() for x in dias],
        "linhas": list(linhas.values()),
        "totais_coluna": {k: round(v, 2) for k, v in total_coluna.items()},
        "total_geral": round(horas_realizadas, 2),
        "medidas": {
            "horas_planejadas": round(horas_planejadas, 1),
            "horas_realizadas": round(horas_realizadas, 1),
            "horas_ociosas": round(horas_planejadas - horas_realizadas, 1),
            "taxa_ocupacao": round(100 * horas_realizadas / horas_planejadas, 1)
            if horas_planejadas
            else 0.0,
            "atraso_medio_min": round(sum(atrasos) / len(atrasos), 1) if atrasos else 0.0,
            "taxa_ausencia": round(100 * ausencias / (realizados + ausencias), 1)
            if (realizados + ausencias)
            else 0.0,
            "janelas_liberadas": liberadas.count(),
        },
        "janelas_ociosas": janelas_ociosas(de, ate, unidade, agora),
    }


def janelas_ociosas(de, ate, unidade=None, agora=None, limite=20):
    """
    RN17: intervalo livre contínuo de pelo menos 60 minutos em sala ou
    equipamento, dentro do horário da unidade. Só janelas futuras, porque só
    elas podem receber encaixe. Para cada uma, sugere o primeiro da fila
    (ordem de RN04) cuja combinação inteira de recursos caiba ali.
    """
    agora = agora or timezone.now()
    tz = timezone.get_current_timezone()
    hoje = timezone.localtime(agora).date()
    de = max(de, hoje)
    if ate < de:
        return []

    recursos = Recurso.objects.filter(ativo=True).select_related("unidade")
    if unidade:
        recursos = recursos.filter(unidade=unidade)
    recursos = list(recursos)

    inicio_periodo = datetime.combine(de, time.min, tzinfo=tz)
    fim_periodo = datetime.combine(ate + timedelta(days=1), time.min, tzinfo=tz)
    fila = list(
        SolicitacaoProcedimento.objects.filter(
            status=SolicitacaoProcedimento.Status.NA_FILA, aprovada=True
        )
        .select_related(
            "agendamento_origem__paciente__usuario",
            "agendamento_origem__medico_responsavel",
            "tipo_procedimento__especialidade",
        )
        .prefetch_related("tipo_procedimento__requisitos__recurso", "tipo_procedimento__requisitos__dias")
    )
    planos = {s.pk: recursos_necessarios(s.tipo_procedimento) for s in fila}
    ids = [r.pk for r in recursos] + [i.recurso.pk for p in planos.values() for i in p]
    mapa = MapaOcupacao(ids, inicio_periodo, fim_periodo)
    medicos = {}
    for s in fila:
        esp = s.tipo_procedimento.especialidade
        if esp.pk not in medicos:
            medicos[esp.pk] = medicos_habilitados(esp)
    agenda = AgendaMedicos(
        [m.pk for lista in medicos.values() for m in lista], inicio_periodo, fim_periodo
    )
    contexto = {"fila": fila, "planos": planos, "mapa": mapa, "agenda": agenda, "medicos": medicos}

    resultado = []
    usados = set()
    d = de
    while d <= ate and len(resultado) < limite:
        if d.weekday() < 5:
            for recurso in recursos:
                abre = datetime.combine(d, recurso.unidade.hora_abertura, tzinfo=tz)
                fecha = datetime.combine(d, recurso.unidade.hora_fechamento, tzinfo=tz)
                # Encaixe com menos de 15 minutos de antecedência não é viável.
                abre = max(abre, _arredonda(agora + timedelta(minutes=15)))
                if fecha - abre < timedelta(minutes=OCIOSIDADE_MINIMA_MIN):
                    continue
                ocupados = sorted(
                    (max(i, abre), min(f, fecha))
                    for i, f in mapa.ocupado[recurso.pk]
                    if i < fecha and f > abre
                )
                cursor = abre
                livres = []
                for i, f in ocupados + [(fecha, fecha)]:
                    if i - cursor >= timedelta(minutes=OCIOSIDADE_MINIMA_MIN):
                        livres.append((cursor, i))
                    cursor = max(cursor, f)
                for ini, fim in livres:
                    resultado.append(
                        {
                            "recurso_id": recurso.pk,
                            "recurso": recurso.nome,
                            "unidade": recurso.unidade.nome,
                            "inicio": ini,
                            "fim": fim,
                            "duracao_min": int((fim - ini).total_seconds() // 60),
                            "candidato": _candidato_para(recurso, ini, fim, contexto, usados),
                        }
                    )
        d += timedelta(days=1)
    resultado.sort(key=lambda j: (j["inicio"], j["recurso"]))
    return resultado[:limite]


def _arredonda(inicio, minutos=5):
    """Ajusta o início para um múltiplo de 5 minutos, para não sugerir 09:03."""
    resto = inicio.minute % minutos
    if resto == 0 and inicio.second == 0 and inicio.microsecond == 0:
        return inicio
    return (inicio + timedelta(minutes=minutos - resto)).replace(second=0, microsecond=0)


def _candidato_para(recurso, ini, fim, contexto, usados):
    """
    Cada solicitação aprovada é sugerida uma vez só, e a sugestão reserva a
    combinação no mapa (e o médico na agenda), para que duas janelas não
    ofereçam o mesmo horário de um recurso.
    """
    inicio = _arredonda(ini)
    mapa, agenda = contexto["mapa"], contexto["agenda"]
    for sol in contexto["fila"]:
        if sol.pk in usados:
            continue
        itens = contexto["planos"][sol.pk]
        if not itens or all(i.recurso.pk != recurso.pk for i in itens):
            continue
        if max(i.span for i in itens) > fim - inicio:
            continue
        if not combinacao_livre(itens, inicio, mapa):
            continue
        fim_proc = inicio + timedelta(minutes=sol.tipo_procedimento.duracao_padrao_min)
        medico = escolher_medico(
            contexto["medicos"][sol.tipo_procedimento.especialidade_id], inicio, fim_proc,
            preferido=sol.medico, agenda=agenda,
        )
        if medico is None:
            continue
        usados.add(sol.pk)
        for item in itens:
            mapa.reservar(item.recurso.pk, inicio, inicio + item.span)
        agenda.reservar(medico.pk, inicio, fim_proc)
        return {
            "solicitacao_id": sol.pk,
            "paciente": str(sol.paciente),
            "medico": str(medico),
            "procedimento": sol.tipo_procedimento.nome,
            "prioridade": sol.get_prioridade_display(),
            "inicio_sugerido": inicio,
        }
    return None


@transaction.atomic
def encaixar(solicitacao, inicio):
    """ENF004: transforma uma janela ociosa em agendamento para o primeiro da fila."""
    if solicitacao.status != SolicitacaoProcedimento.Status.NA_FILA or not solicitacao.aprovada:
        raise ValidationError("A solicitação não está na fila de aprovadas.")
    return criar_agendamento(
        paciente=solicitacao.paciente,
        tipo=solicitacao.tipo_procedimento,
        inicio=inicio,
        solicitacao=solicitacao,
    )
