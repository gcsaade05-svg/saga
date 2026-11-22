"""
Modelos do SAGA, Sistema de Agendamento e Gestão Assistencial.
PMR3304 Sistemas de Informação, 2026.

Decisão de modelagem central
----------------------------
Sala e equipamento são tratados como um único conceito: Recurso, que
representa só coisas físicas do hospital. Isso torna uniforme tanto a alocação
quanto a apuração de ocupação: uma tabela só em vez de duas, e uma única
consulta para o Painel de Ocupação. O médico não é recurso: a agenda dele é
checada pelos agendamentos de que é responsável (RN03).

A disponibilidade fica no próprio requisito do procedimento: cada
RequisitoProcedimento diz por qual período, em que horário e em quais dias da
semana (DiaDisponibilidade) aquele recurso atende aquele procedimento.

Relações exigidas pela disciplina
---------------------------------
1 x n : Unidade -> Recurso
        Paciente -> Agendamento
        TipoProcedimento -> Agendamento
        Agendamento -> SolicitacaoProcedimento (agendamento de origem)
        RequisitoProcedimento -> DiaDisponibilidade
        RequisitoProcedimento -> Agendamento
        Agendamento -> RegistroClinico
        Agendamento -> Triagem
        Enfermeiro -> Triagem

n x n : Agendamento <-> Recurso          (through AlocacaoRecurso)
        TipoProcedimento <-> Recurso     (through RequisitoProcedimento)
        Medico <-> Especialidade         (through HabilitacaoMedico)

Normalização
------------
Nenhum atributo calculado é gravado: durações, atraso e ociosidade são
propriedades derivadas das janelas. Os dias da semana da disponibilidade,
que no formulário de MED001 são um campo de seleção múltipla, ficam em tabela
própria (DiaDisponibilidade) para respeitar a 1FN. Médico e paciente da
solicitação não são repetidos: vêm do agendamento de origem.
O documento do Diagrama Entidade Relação detalha cada decisão.
"""
from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


# ---------------------------------------------------------------------------
# Usuários e perfis
# ---------------------------------------------------------------------------
class Usuario(AbstractUser):
    """Usuário único do sistema. O perfil determina as permissões e as telas."""

    class Perfil(models.TextChoices):
        PACIENTE = "PACIENTE", "Paciente"
        MEDICO = "MEDICO", "Médico"
        ENFERMEIRO = "ENFERMEIRO", "Enfermeiro"

    perfil = models.CharField(max_length=12, choices=Perfil.choices)
    telefone = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_perfil_display()})"


class Paciente(models.Model):
    """Ator 1. Faz o próprio cadastro (AUT002) e agenda apenas consultas (RN01)."""

    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name="paciente")
    cpf = models.CharField("CPF", max_length=14, unique=True)
    data_nascimento = models.DateField()
    cartao_sus = models.CharField("cartão SUS", max_length=20, blank=True)

    class Meta:
        verbose_name = "paciente"
        verbose_name_plural = "pacientes"

    def __str__(self):
        return self.usuario.get_full_name() or self.usuario.username


class Especialidade(models.Model):
    """Área de atuação médica. Restringe quem atende e o que pode ser agendado."""

    nome = models.CharField(max_length=80, unique=True)

    class Meta:
        verbose_name = "especialidade"
        verbose_name_plural = "especialidades"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Medico(models.Model):
    """Ator 2. Publica disponibilidade, atende e solicita exames e cirurgias."""

    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name="medico")
    crm = models.CharField("CRM", max_length=20, unique=True)
    especialidades = models.ManyToManyField(
        Especialidade,
        through="HabilitacaoMedico",
        related_name="medicos",
        verbose_name="especialidades",
    )

    class Meta:
        verbose_name = "médico"
        verbose_name_plural = "médicos"

    def __str__(self):
        return f"Dr(a). {self.usuario.get_full_name() or self.usuario.username}"

    def especialidades_ativas(self):
        return Especialidade.objects.filter(
            habilitacoes__medico=self,
            habilitacoes__situacao=HabilitacaoMedico.Situacao.ATIVA,
        )

    def livre_em(self, inicio, fim, ignorar_agendamento=None):
        """RN03: o médico não atende dois agendamentos ao mesmo tempo."""
        conflitos = self.agendamentos.exclude(status=Agendamento.Status.CANCELADO).filter(
            inicio_planejado__lt=fim, fim_planejado__gt=inicio
        )
        if ignorar_agendamento is not None:
            conflitos = conflitos.exclude(pk=ignorar_agendamento.pk)
        return not conflitos.exists()


class HabilitacaoMedico(models.Model):
    """n x n: Medico <-> Especialidade, com atributos próprios."""

    class Situacao(models.TextChoices):
        ATIVA = "ATIVA", "Ativa"
        SUSPENSA = "SUSPENSA", "Suspensa"

    medico = models.ForeignKey(Medico, on_delete=models.CASCADE, related_name="habilitacoes")
    especialidade = models.ForeignKey(
        Especialidade, on_delete=models.PROTECT, related_name="habilitacoes"
    )
    rqe = models.CharField("RQE", max_length=20, blank=True)
    data_habilitacao = models.DateField()
    situacao = models.CharField(max_length=10, choices=Situacao.choices, default=Situacao.ATIVA)

    class Meta:
        verbose_name = "habilitação do médico"
        verbose_name_plural = "habilitações dos médicos"
        constraints = [
            models.UniqueConstraint(
                fields=["medico", "especialidade"], name="unica_habilitacao_por_especialidade"
            )
        ]

    def __str__(self):
        return f"{self.medico} em {self.especialidade}"


class Unidade(models.Model):
    """Unidade assistencial: ambulatório, centro cirúrgico, imagem, laboratório."""

    class Tipo(models.TextChoices):
        AMBULATORIO = "AMBULATORIO", "Ambulatório"
        CENTRO_CIRURGICO = "CENTRO_CIRURGICO", "Centro cirúrgico"
        IMAGEM = "IMAGEM", "Diagnóstico por imagem"
        LABORATORIO = "LABORATORIO", "Laboratório"

    nome = models.CharField(max_length=80, unique=True)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    # RN17: a ociosidade só conta dentro do horário de funcionamento.
    hora_abertura = models.TimeField(default=time(7, 0))
    hora_fechamento = models.TimeField(default=time(19, 0))

    class Meta:
        verbose_name = "unidade"
        verbose_name_plural = "unidades"
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    def clean(self):
        if self.hora_fechamento <= self.hora_abertura:
            raise ValidationError({"hora_fechamento": "O fechamento deve ser após a abertura."})


class Enfermeiro(models.Model):
    """Ator 3. Faz triagem e registra a ocupação real dos recursos."""

    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name="enfermeiro")
    coren = models.CharField("COREN", max_length=20, unique=True)
    unidade = models.ForeignKey(
        Unidade, on_delete=models.PROTECT, related_name="enfermeiros", verbose_name="unidade"
    )

    class Meta:
        verbose_name = "enfermeiro"
        verbose_name_plural = "enfermeiros"

    def __str__(self):
        return f"Enf. {self.usuario.get_full_name() or self.usuario.username}"


# ---------------------------------------------------------------------------
# Estrutura física e catálogo
# ---------------------------------------------------------------------------
class Recurso(models.Model):
    """
    1 x n: Unidade -> Recurso.

    Sala e equipamento em uma entidade só: só coisas físicas do hospital. É
    esta uniformidade que permite ao Painel de Ocupação somar horas de qualquer
    tipo de recurso com a mesma consulta.
    """

    class Tipo(models.TextChoices):
        SALA = "SALA", "Sala"
        EQUIPAMENTO = "EQUIPAMENTO", "Equipamento"

    nome = models.CharField(max_length=80)
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    unidade = models.ForeignKey(Unidade, on_delete=models.PROTECT, related_name="recursos")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "recurso"
        verbose_name_plural = "recursos"
        ordering = ["unidade__nome", "tipo", "nome"]
        constraints = [
            models.UniqueConstraint(fields=["unidade", "nome"], name="recurso_unico_na_unidade")
        ]

    def __str__(self):
        return self.nome

    def livre_em(self, inicio, fim, ignorar_agendamento=None):
        """RN03: o recurso está livre se nenhuma alocação ativa se sobrepõe à janela."""
        conflitos = self.alocacoes.exclude(status=AlocacaoRecurso.Status.LIBERADA).filter(
            inicio_planejado__lt=fim, fim_planejado__gt=inicio
        )
        if ignorar_agendamento is not None:
            conflitos = conflitos.exclude(agendamento=ignorar_agendamento)
        return not conflitos.exists()


class TipoProcedimento(models.Model):
    """Consulta, exame ou cirurgia. Declara de quais recursos precisa e por quanto tempo."""

    class Modalidade(models.TextChoices):
        CONSULTA = "CONSULTA", "Consulta"
        EXAME = "EXAME", "Exame"
        CIRURGIA = "CIRURGIA", "Cirurgia"

    nome = models.CharField(max_length=100, unique=True)
    modalidade = models.CharField(max_length=10, choices=Modalidade.choices)
    especialidade = models.ForeignKey(
        Especialidade, on_delete=models.PROTECT, related_name="procedimentos"
    )
    duracao_padrao_min = models.PositiveIntegerField("duração padrão (min)", default=30)
    exige_preparo = models.BooleanField("exige preparo pela enfermagem", default=False)
    recursos = models.ManyToManyField(
        Recurso,
        through="RequisitoProcedimento",
        related_name="procedimentos",
        verbose_name="recursos",
    )

    class Meta:
        verbose_name = "tipo de procedimento"
        verbose_name_plural = "tipos de procedimento"
        ordering = ["modalidade", "nome"]

    def __str__(self):
        return f"{self.nome} ({self.get_modalidade_display()})"

    def recursos_obrigatorios(self):
        return self.requisitos.filter(obrigatorio=True).select_related("recurso")


class RequisitoProcedimento(models.Model):
    """
    n x n: TipoProcedimento <-> Recurso.

    Diz quais recursos são aptos ao procedimento, por quanto tempo cada um
    fica ocupado e QUANDO ele está disponível para esse procedimento: período
    (data inicial e final), janela diária (hora de início e fim) e dias da
    semana (DiaDisponibilidade). A disponibilidade publicada em MED001 é
    gravada aqui, e não em uma tabela de blocos separada.

    Na consulta, cada sala do catálogo é uma alternativa: a janela é gerada a
    partir da disponibilidade da sala, e a duração é o tempo de ocupação. Em
    exame e cirurgia, todos os requisitos obrigatórios são usados juntos (RN02),
    e cada um precisa estar dentro da própria disponibilidade.
    """

    tipo_procedimento = models.ForeignKey(
        TipoProcedimento, on_delete=models.CASCADE, related_name="requisitos"
    )
    recurso = models.ForeignKey(Recurso, on_delete=models.CASCADE, related_name="requisitos")
    obrigatorio = models.BooleanField(default=True)
    tempo_ocupacao_min = models.PositiveIntegerField("tempo de ocupação (min)")
    tempo_setup_min = models.PositiveIntegerField("tempo de setup (min)", default=0)
    data_inicial = models.DateField()
    data_final = models.DateField()
    hora_inicio = models.TimeField()
    hora_fim = models.TimeField()

    class Meta:
        verbose_name = "requisito de procedimento"
        verbose_name_plural = "requisitos de procedimento"
        ordering = ["tipo_procedimento__nome", "recurso__nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_procedimento", "recurso"], name="requisito_unico_por_recurso"
            )
        ]

    def __str__(self):
        return f"{self.tipo_procedimento.nome} usa {self.recurso.nome}"

    def clean(self):
        erros = {}
        if self.data_final and self.data_inicial:
            if self.data_final < self.data_inicial:
                erros["data_final"] = "Deve ser igual ou posterior à data inicial."
            elif (self.data_final - self.data_inicial).days > 366:
                erros["data_final"] = "No máximo um ano após a data inicial."
        if self.hora_fim and self.hora_inicio and self.hora_fim <= self.hora_inicio:
            erros["hora_fim"] = "Deve ser posterior à hora de início."
        d = self.tempo_ocupacao_min
        if d is not None and not (5 <= d <= 600):
            erros["tempo_ocupacao_min"] = "Entre 5 e 600 minutos."
        if erros:
            raise ValidationError(erros)

    def dias_semana(self):
        """Usa o prefetch quando existe, para não fazer uma consulta por requisito."""
        return {d.dia_semana for d in self.dias.all()}

    def cobre(self, inicio, fim, dias=None):
        """A janela [inicio, fim) cabe inteira na disponibilidade deste requisito?"""
        ini_local = timezone.localtime(inicio)
        fim_local = timezone.localtime(fim)
        if ini_local.date() != fim_local.date() and fim_local.time() != time(0, 0):
            return False
        dia = ini_local.date()
        if not (self.data_inicial <= dia <= self.data_final):
            return False
        if dia.weekday() not in (dias if dias is not None else self.dias_semana()):
            return False
        return self.hora_inicio <= ini_local.time() and fim_local.time() <= self.hora_fim

    def janelas(self, de=None, ate=None, passo_min=None):
        """
        Gera as janelas (início, fim) de consulta entre `de` e `ate`.

        É um cálculo, não uma consulta: a janela só passa a existir no banco
        quando vira um Agendamento.
        """
        tz = timezone.get_current_timezone()
        dias_semana = self.dias_semana()
        primeiro = max(self.data_inicial, de or self.data_inicial)
        ultimo = min(self.data_final, ate or self.data_final)
        passo = timedelta(minutes=passo_min or self.tempo_ocupacao_min)
        dia = primeiro
        while dia <= ultimo:
            if dia.weekday() in dias_semana:
                inicio = datetime.combine(dia, self.hora_inicio, tzinfo=tz)
                limite = datetime.combine(dia, self.hora_fim, tzinfo=tz)
                while inicio + passo <= limite:
                    yield inicio, inicio + passo
                    inicio += passo
            dia += timedelta(days=1)


class DiaDisponibilidade(models.Model):
    """
    1 x n: RequisitoProcedimento -> DiaDisponibilidade.

    Aplicação direta da 1FN: "Repetir em" é multivalorado no formulário, então
    cada dia da semana vira uma linha, e não uma lista dentro de uma coluna.
    """

    class DiaSemana(models.IntegerChoices):
        # Mesma numeração de date.weekday() do Python.
        SEGUNDA = 0, "Segunda-feira"
        TERCA = 1, "Terça-feira"
        QUARTA = 2, "Quarta-feira"
        QUINTA = 3, "Quinta-feira"
        SEXTA = 4, "Sexta-feira"
        SABADO = 5, "Sábado"
        DOMINGO = 6, "Domingo"

    requisito = models.ForeignKey(
        RequisitoProcedimento, on_delete=models.CASCADE, related_name="dias"
    )
    dia_semana = models.PositiveSmallIntegerField(choices=DiaSemana.choices)

    class Meta:
        verbose_name = "dia de disponibilidade"
        verbose_name_plural = "dias de disponibilidade"
        ordering = ["dia_semana"]
        constraints = [
            models.UniqueConstraint(
                fields=["requisito", "dia_semana"], name="dia_unico_por_requisito"
            )
        ]

    def __str__(self):
        return self.get_dia_semana_display()


# ---------------------------------------------------------------------------
# Solicitação e agendamento
# ---------------------------------------------------------------------------
class SolicitacaoProcedimento(models.Model):
    """
    1 x n: Agendamento (de origem) -> SolicitacaoProcedimento.

    RN01: o paciente agenda apenas consultas. Exame e cirurgia nascem aqui,
    pedidos pelo médico durante um atendimento. Médico e paciente não são
    gravados de novo: vêm do agendamento de origem (sem dependência transitiva).

    A solicitação só usa recurso depois de aprovada: nasce "Aguardando
    aprovação", o enfermeiro aprova (aprovada, aprovada_em) e só então ela
    entra na fila e pode ser encaixada.
    """

    class Prioridade(models.IntegerChoices):
        ELETIVA = 1, "Eletiva"
        PRIORITARIA = 2, "Prioritária"
        URGENTE = 3, "Urgente"

    class Status(models.TextChoices):
        AGUARDANDO_APROVACAO = "AGUARDANDO_APROVACAO", "Aguardando aprovação"
        NA_FILA = "NA_FILA", "Na fila"
        AGENDADA = "AGENDADA", "Agendada"
        CANCELADA = "CANCELADA", "Cancelada"

    agendamento_origem = models.ForeignKey(
        "Agendamento", on_delete=models.PROTECT, related_name="solicitacoes_geradas"
    )
    tipo_procedimento = models.ForeignKey(
        TipoProcedimento, on_delete=models.PROTECT, related_name="solicitacoes"
    )
    prioridade = models.IntegerField(choices=Prioridade.choices, default=Prioridade.ELETIVA)
    justificativa = models.TextField(blank=True)
    criada_em = models.DateTimeField(default=timezone.now)
    status = models.CharField(
        max_length=25, choices=Status.choices, default=Status.AGUARDANDO_APROVACAO
    )
    aprovada = models.BooleanField(default=False)
    aprovada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "solicitação de procedimento"
        verbose_name_plural = "solicitações de procedimento"
        # RN04: prioridade decrescente e, no empate, antiguidade.
        ordering = ["-prioridade", "criada_em"]

    def __str__(self):
        return f"{self.tipo_procedimento.nome} para {self.paciente}"

    # Derivados do agendamento de origem, nunca gravados.
    @property
    def paciente(self):
        return self.agendamento_origem.paciente

    @property
    def medico(self):
        return self.agendamento_origem.medico_responsavel

    def clean(self):
        if (
            self.tipo_procedimento_id
            and self.tipo_procedimento.modalidade == TipoProcedimento.Modalidade.CONSULTA
        ):
            raise ValidationError(
                {"tipo_procedimento": "Consultas não são solicitadas, o paciente agenda direto."}
            )
        if self.aprovada and self.status == self.Status.AGUARDANDO_APROVACAO:
            raise ValidationError("Solicitação aprovada não pode estar aguardando aprovação.")
        if not self.aprovada and self.status in (self.Status.NA_FILA, self.Status.AGENDADA):
            raise ValidationError("Só a solicitação aprovada entra na fila ou é agendada.")

    def aprovar(self, quando=None):
        if self.status != self.Status.AGUARDANDO_APROVACAO:
            raise ValidationError("Esta solicitação não está aguardando aprovação.")
        self.aprovada = True
        self.aprovada_em = quando or timezone.now()
        self.status = self.Status.NA_FILA
        self.save(update_fields=["aprovada", "aprovada_em", "status"])


class Agendamento(models.Model):
    """
    Entidade multidimensional transacional.

    Cruza paciente, médico, tipo de procedimento, unidade, recurso e tempo, e
    acumula duração planejada, duração realizada e atraso de início.
    """

    class Status(models.TextChoices):
        AGENDADO = "AGENDADO", "Agendado"
        CONFIRMADO = "CONFIRMADO", "Confirmado"
        REALIZADO = "REALIZADO", "Realizado"
        CANCELADO = "CANCELADO", "Cancelado"
        AUSENCIA = "AUSENCIA", "Ausência"

    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="agendamentos")
    tipo_procedimento = models.ForeignKey(
        TipoProcedimento, on_delete=models.PROTECT, related_name="agendamentos"
    )
    medico_responsavel = models.ForeignKey(
        Medico, on_delete=models.SET_NULL, null=True, blank=True, related_name="agendamentos"
    )
    # Disponibilidade usada: o requisito (sala) cuja janela foi ocupada. Na
    # consulta é a origem do horário (PAC001); exame e cirurgia nascem de uma
    # solicitação (MED003 e encaixe em ENF004) e guardam o requisito principal.
    requisito = models.ForeignKey(
        RequisitoProcedimento,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="agendamentos",
    )
    # 1 x n e não 1 x 1: se o agendamento de um exame é cancelado, a solicitação
    # volta para a fila e pode gerar outro agendamento, sem apagar o histórico.
    solicitacao = models.ForeignKey(
        SolicitacaoProcedimento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agendamentos",
    )
    # Autorrelacionamento: a remarcação (PAC003) cria um agendamento novo que
    # aponta para o original, preservando o histórico.
    remarcacao_de = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="remarcacoes",
    )
    inicio_planejado = models.DateTimeField()
    fim_planejado = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.AGENDADO)
    criado_em = models.DateTimeField(auto_now_add=True)
    confirmado_em = models.DateTimeField(null=True, blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)
    motivo_cancelamento = models.TextField(blank=True)
    cancelamento_tardio = models.BooleanField(default=False)
    # RN13 e RN14: o acesso ao prontuário é atributo do agendamento. O médico
    # responsável só lê o prontuário do paciente com um agendamento liberado,
    # e o último acesso fica gravado no próprio agendamento.
    prontuario_liberado = models.BooleanField(default=False)
    prontuario_acessado_em = models.DateTimeField(null=True, blank=True)

    recursos = models.ManyToManyField(
        Recurso,
        through="AlocacaoRecurso",
        related_name="agendamentos",
        verbose_name="recursos alocados",
    )

    class Meta:
        verbose_name = "agendamento"
        verbose_name_plural = "agendamentos"
        ordering = ["inicio_planejado"]

    def __str__(self):
        quando = timezone.localtime(self.inicio_planejado).strftime("%d/%m %H:%M")
        return f"{self.tipo_procedimento.nome}, {self.paciente}, {quando}"

    def clean(self):
        if self.fim_planejado and self.inicio_planejado:
            if self.fim_planejado <= self.inicio_planejado:
                raise ValidationError({"fim_planejado": "O fim deve ser posterior ao início."})
        # Paciente e procedimento são repetidos aqui mesmo quando há solicitação,
        # porque a consulta não tem solicitação e a consulta do painel precisa
        # deles em todos os agendamentos. A redundância é controlada por esta regra.
        if self.solicitacao_id:
            s = self.solicitacao
            if (
                s.agendamento_origem.paciente_id != self.paciente_id
                or s.tipo_procedimento_id != self.tipo_procedimento_id
            ):
                raise ValidationError(
                    "Paciente e procedimento devem ser os mesmos da solicitação de origem."
                )

    # --- Medidas do fato transacional (derivadas, nunca gravadas) ---------
    @property
    def duracao_planejada_min(self):
        return int((self.fim_planejado - self.inicio_planejado).total_seconds() // 60)

    @property
    def duracao_realizada_min(self):
        """Maior janela realizada entre as alocações, em minutos."""
        duracoes = [a.duracao_realizada_min for a in self.alocacoes.all()]
        duracoes = [d for d in duracoes if d is not None]
        return max(duracoes) if duracoes else None

    @property
    def atraso_inicio_min(self):
        """Diferença entre o primeiro início real e o início planejado."""
        inicios = [a.inicio_realizado for a in self.alocacoes.all() if a.inicio_realizado]
        if not inicios:
            return None
        return int((min(inicios) - self.inicio_planejado).total_seconds() // 60)

    @property
    def unidade(self):
        """Derivada da sala alocada. Não é gravada para não violar a 3FN."""
        alocs = list(self.alocacoes.all())  # aproveita o prefetch das listas
        principal = next((a for a in alocs if a.papel == AlocacaoRecurso.Papel.PRINCIPAL), None)
        aloc = principal or (alocs[0] if alocs else None)
        return aloc.recurso.unidade if aloc else None


class AlocacaoRecurso(models.Model):
    """
    n x n: Agendamento <-> Recurso. O núcleo do sistema.

    Carrega na mesma linha a janela PLANEJADA e a janela REALIZADA. É essa
    diferença que revela ociosidade e atraso, e é dela que o Painel de Ocupação
    é derivado. Quem preenche o realizado é o enfermeiro, ao abrir e encerrar
    a ocupação (ENF002).
    """

    class Papel(models.TextChoices):
        PRINCIPAL = "PRINCIPAL", "Principal"
        APOIO = "APOIO", "Apoio"

    class Status(models.TextChoices):
        PLANEJADA = "PLANEJADA", "Planejada"
        EM_USO = "EM_USO", "Em uso"
        ENCERRADA = "ENCERRADA", "Encerrada"
        LIBERADA = "LIBERADA", "Liberada sem uso"

    class MotivoAtraso(models.TextChoices):
        PROCEDIMENTO_ANTERIOR = "PROC_ANTERIOR", "Atraso do procedimento anterior"
        PACIENTE = "PACIENTE", "Atraso do paciente"
        EQUIPE = "EQUIPE", "Indisponibilidade de equipe"
        MATERIAL = "MATERIAL", "Indisponibilidade de material"
        OUTRO = "OUTRO", "Outro"

    agendamento = models.ForeignKey(
        Agendamento, on_delete=models.CASCADE, related_name="alocacoes"
    )
    recurso = models.ForeignKey(Recurso, on_delete=models.PROTECT, related_name="alocacoes")
    papel = models.CharField(max_length=10, choices=Papel.choices, default=Papel.PRINCIPAL)

    inicio_planejado = models.DateTimeField()
    fim_planejado = models.DateTimeField()
    inicio_realizado = models.DateTimeField(null=True, blank=True)
    fim_realizado = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLANEJADA)
    aberta_por = models.ForeignKey(
        Enfermeiro,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alocacoes_abertas",
        verbose_name="aberta por",
    )
    motivo_atraso = models.CharField(max_length=15, choices=MotivoAtraso.choices, blank=True)
    motivo_atraso_detalhe = models.CharField(max_length=500, blank=True)
    encerramento_retroativo = models.BooleanField(default=False)

    class Meta:
        verbose_name = "alocação de recurso"
        verbose_name_plural = "alocações de recurso"
        ordering = ["inicio_planejado"]
        constraints = [
            models.UniqueConstraint(
                fields=["agendamento", "recurso"], name="recurso_unico_por_agendamento"
            ),
            # RN09: o mesmo recurso não pode ter duas alocações "Em uso" ao mesmo tempo.
            models.UniqueConstraint(
                fields=["recurso"],
                condition=Q(status="EM_USO"),
                name="um_uso_por_recurso",
            ),
        ]

    def __str__(self):
        return f"{self.recurso.nome} no agendamento {self.agendamento_id}"

    def clean(self):
        if self.fim_planejado <= self.inicio_planejado:
            raise ValidationError({"fim_planejado": "O fim deve ser posterior ao início."})
        # RN03: um recurso não pode estar em dois lugares ao mesmo tempo.
        conflito = (
            AlocacaoRecurso.objects.filter(recurso=self.recurso)
            .exclude(pk=self.pk)
            .exclude(status=self.Status.LIBERADA)
            .filter(
                inicio_planejado__lt=self.fim_planejado,
                fim_planejado__gt=self.inicio_planejado,
            )
        )
        if conflito.exists():
            raise ValidationError(f"O recurso {self.recurso} já está alocado nessa janela.")
        if self.motivo_atraso == self.MotivoAtraso.OUTRO and not self.motivo_atraso_detalhe:
            raise ValidationError({"motivo_atraso_detalhe": "Descreva o motivo."})

    # --- Ações do enfermeiro (RN08: sempre o relógio do servidor) ---------
    def abrir_ocupacao(self, enfermeiro, quando=None):
        """O enfermeiro registra que o recurso começou a ser usado de fato."""
        self.inicio_realizado = quando or timezone.now()
        self.aberta_por = enfermeiro
        self.status = self.Status.EM_USO
        self.save(update_fields=["inicio_realizado", "aberta_por", "status"])

    def encerrar_ocupacao(self, quando=None, retroativo=False):
        """O enfermeiro registra que o recurso foi liberado."""
        if self.status != self.Status.EM_USO:
            raise ValidationError("Só é possível encerrar uma alocação em uso.")
        self.fim_realizado = quando or timezone.now()
        self.status = self.Status.ENCERRADA
        self.encerramento_retroativo = retroativo
        self.save(update_fields=["fim_realizado", "status", "encerramento_retroativo"])

    # --- Medidas (derivadas) ----------------------------------------------
    @property
    def duracao_planejada_min(self):
        return int((self.fim_planejado - self.inicio_planejado).total_seconds() // 60)

    @property
    def duracao_realizada_min(self):
        if not (self.inicio_realizado and self.fim_realizado):
            return None
        return int((self.fim_realizado - self.inicio_realizado).total_seconds() // 60)

    @property
    def atraso_inicio_min(self):
        if not self.inicio_realizado:
            return None
        return int((self.inicio_realizado - self.inicio_planejado).total_seconds() // 60)

    @property
    def ociosidade_min(self):
        """Quanto da janela reservada não foi usado. Negativo significa estouro."""
        realizada = self.duracao_realizada_min
        if realizada is None:
            return None
        return self.duracao_planejada_min - realizada


# ---------------------------------------------------------------------------
# Registros clínicos
# ---------------------------------------------------------------------------
class Triagem(models.Model):
    """
    1 x n: Agendamento -> Triagem e Enfermeiro -> Triagem.

    RN15: triagem não é editável; uma correção é uma nova triagem, por isso um
    agendamento pode ter várias e vale a mais recente.
    """

    class Risco(models.IntegerChoices):
        AZUL = 1, "Azul (não urgente)"
        VERDE = 2, "Verde (pouco urgente)"
        AMARELO = 3, "Amarelo (urgente)"
        LARANJA = 4, "Laranja (muito urgente)"
        VERMELHO = 5, "Vermelho (emergência)"

    agendamento = models.ForeignKey(
        Agendamento, on_delete=models.CASCADE, related_name="triagens"
    )
    enfermeiro = models.ForeignKey(Enfermeiro, on_delete=models.PROTECT, related_name="triagens")
    pressao_sistolica = models.PositiveSmallIntegerField("PA sistólica (mmHg)")
    pressao_diastolica = models.PositiveSmallIntegerField("PA diastólica (mmHg)")
    frequencia_cardiaca = models.PositiveSmallIntegerField("FC (bpm)")
    temperatura = models.DecimalField("temperatura (°C)", max_digits=4, decimal_places=1)
    saturacao = models.PositiveSmallIntegerField("SpO2 (%)")
    classificacao_sugerida = models.IntegerField(choices=Risco.choices, null=True, blank=True)
    classificacao_risco = models.IntegerField(choices=Risco.choices)
    observacoes = models.CharField(max_length=500, blank=True)
    realizada_em = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "triagem"
        verbose_name_plural = "triagens"
        ordering = ["-realizada_em"]

    def __str__(self):
        return f"Triagem de {self.agendamento.paciente}: {self.get_classificacao_risco_display()}"

    @property
    def sobrepos_sugestao(self):
        """Derivado: o enfermeiro escolheu risco menor que o sugerido (ENF001 fluxo a)."""
        return (
            self.classificacao_sugerida is not None
            and self.classificacao_risco < self.classificacao_sugerida
        )

    def clean(self):
        if self.pressao_diastolica and self.pressao_sistolica:
            if self.pressao_diastolica >= self.pressao_sistolica:
                raise ValidationError({"pressao_diastolica": "Deve ser menor que a sistólica."})
        if self.sobrepos_sugestao and not self.observacoes:
            raise ValidationError(
                {"observacoes": "Obrigatório ao escolher risco menor que o sugerido."}
            )


class RegistroClinico(models.Model):
    """1 x n: Agendamento -> RegistroClinico. Evolução, diagnóstico e conduta."""

    class Tipo(models.TextChoices):
        EVOLUCAO = "EVOLUCAO", "Evolução"
        DIAGNOSTICO = "DIAGNOSTICO", "Hipótese diagnóstica"
        CONDUTA = "CONDUTA", "Conduta"

    agendamento = models.ForeignKey(
        Agendamento, on_delete=models.CASCADE, related_name="registros"
    )
    medico = models.ForeignKey(Medico, on_delete=models.PROTECT, related_name="registros")
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    texto = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)
    # RN11: a liberação para o paciente é ação explícita do médico.
    liberado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "registro clínico"
        verbose_name_plural = "registros clínicos"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.get_tipo_display()} de {self.agendamento.paciente}"
