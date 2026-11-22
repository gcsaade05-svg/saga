"""
Popula o banco com dados sintéticos para demonstração.

Nenhum dado real de paciente é usado: o sistema manipula dados de saúde, que
são dados pessoais sensíveis, e este é um trabalho acadêmico.

Os agendamentos são criados pelas mesmas funções que a API usa
(core.servicos), então o banco de demonstração obedece às mesmas regras de
negócio que o sistema em produção obedeceria.

Uso:  python manage.py seed
      python manage.py seed --limpar
"""
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core import servicos
from core.models import (
    Agendamento,
    AlocacaoRecurso,
    DiaDisponibilidade,
    Enfermeiro,
    Especialidade,
    HabilitacaoMedico,
    Medico,
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
from core.utils import gerar_cpf, sugerir_classificacao

NOMES = [
    "Ana Ribeiro", "Bruno Carvalho", "Carla Menezes", "Diego Fontes", "Elisa Tavares",
    "Fábio Nogueira", "Gisele Amaral", "Henrique Prado", "Isabela Moraes", "João Vasques",
    "Karina Duarte", "Lucas Peixoto", "Mariana Salles", "Nelson Barreto", "Olívia Campos",
    "Paulo Rezende", "Queila Andrade", "Rafael Siqueira", "Sofia Bastos", "Tiago Lemos",
    "Úrsula Freitas", "Vitor Marques", "Wanda Correia", "Xavier Pontes",
]

# nome, especialidade principal, segunda especialidade
MEDICOS = [
    ("Helena Vasconcelos", "Ortopedia", None),
    ("Rodrigo Almeida", "Cardiologia", "Clínica Médica"),
    ("Patrícia Lins", "Radiologia", None),
    ("Marcelo Tanaka", "Clínica Médica", None),
]

ENFERMEIROS = [
    ("Fernanda Rocha", "Centro Cirúrgico A"),
    ("Gustavo Neves", "Ambulatório Central"),
    ("Juliana Prates", "Imagem"),
]

DIAS_UTEIS = [0, 1, 2, 3, 4]

# Catálogo: nome, modalidade, especialidade, duração, exige preparo, requisitos.
# Cada requisito já traz a disponibilidade do recurso para aquele procedimento:
# (recurso, ocupação, setup, dias da semana, hora início, hora fim).
# Na consulta, cada sala é uma alternativa; em exame e cirurgia, vão todos juntos.
CATALOGO = [
    ("Consulta ortopédica", "CONSULTA", "Ortopedia", 30, False,
     [("Consultório 1", 30, 0, [0, 2], time(8), time(12))]),
    ("Consulta cardiológica", "CONSULTA", "Cardiologia", 30, False,
     [("Consultório 2", 30, 0, [1, 3], time(8), time(12))]),
    ("Consulta de clínica médica", "CONSULTA", "Clínica Médica", 20, False,
     [("Consultório 1", 20, 0, [1, 3], time(13), time(17)),
      ("Consultório 2", 20, 0, [4], time(13), time(17))]),
    ("Tomografia de crânio", "EXAME", "Radiologia", 45, True,
     [("Sala de Imagem A", 45, 10, DIAS_UTEIS, time(7), time(19)),
      ("Tomógrafo", 45, 10, DIAS_UTEIS, time(7), time(19))]),
    ("Artroscopia de joelho", "CIRURGIA", "Ortopedia", 90, True,
     [("Sala Cirúrgica 1", 90, 30, DIAS_UTEIS, time(7), time(19)),
      ("Arco Cirúrgico", 90, 15, DIAS_UTEIS, time(7), time(19))]),
    ("Cateterismo", "CIRURGIA", "Cardiologia", 120, True,
     [("Sala Cirúrgica 2", 120, 30, DIAS_UTEIS, time(7), time(19))]),
]

# De qual consulta nasce cada pedido de exame ou cirurgia (MED003).
ORIGEM = {
    "Tomografia de crânio": ["Consulta de clínica médica", "Consulta ortopédica"],
    "Artroscopia de joelho": ["Consulta ortopédica"],
    "Cateterismo": ["Consulta cardiológica"],
}

MOTIVOS_CANCELAMENTO = [
    "Conflito com compromisso de trabalho (dado sintético).",
    "Paciente apresentou melhora dos sintomas (dado sintético).",
    "Viagem marcada para a mesma data (dado sintético).",
]


def slug(nome):
    partes = nome.lower().split()
    return partes[0] + "." + partes[-1]


class Command(BaseCommand):
    help = "Popula o banco com dados sintéticos do SAGA."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limpar", action="store_true", help="Apaga os dados existentes antes de popular."
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(3304)  # reprodutível: todo mundo do grupo vê o mesmo banco
        agora = timezone.now()

        if Unidade.objects.exists() and not options["limpar"]:
            self.stdout.write("Banco já populado. Use --limpar para recomeçar.")
            return
        if options["limpar"]:
            self.stdout.write("Limpando dados...")
            for modelo in (
                RegistroClinico, Triagem, AlocacaoRecurso, SolicitacaoProcedimento, Agendamento,
                DiaDisponibilidade, RequisitoProcedimento, TipoProcedimento, HabilitacaoMedico,
                Medico, Enfermeiro, Paciente, Recurso, Especialidade, Unidade,
            ):
                modelo.objects.all().delete()
            Usuario.objects.filter(is_superuser=False).delete()

        # -------------------------------------------------- catálogo institucional
        especialidades = {
            nome: Especialidade.objects.create(nome=nome)
            for nome in ["Cardiologia", "Clínica Médica", "Ortopedia", "Radiologia"]
        }
        unidades = {
            nome: Unidade.objects.create(nome=nome, tipo=tipo, hora_abertura=a, hora_fechamento=f)
            for nome, tipo, a, f in [
                ("Ambulatório Central", Unidade.Tipo.AMBULATORIO, time(7), time(19)),
                ("Centro Cirúrgico A", Unidade.Tipo.CENTRO_CIRURGICO, time(7), time(19)),
                ("Imagem", Unidade.Tipo.IMAGEM, time(7), time(19)),
            ]
        }
        recursos = {}
        for nome, tipo, unidade in [
            ("Consultório 1", Recurso.Tipo.SALA, "Ambulatório Central"),
            ("Consultório 2", Recurso.Tipo.SALA, "Ambulatório Central"),
            ("Sala Cirúrgica 1", Recurso.Tipo.SALA, "Centro Cirúrgico A"),
            ("Sala Cirúrgica 2", Recurso.Tipo.SALA, "Centro Cirúrgico A"),
            ("Arco Cirúrgico", Recurso.Tipo.EQUIPAMENTO, "Centro Cirúrgico A"),
            ("Sala de Imagem A", Recurso.Tipo.SALA, "Imagem"),
            ("Tomógrafo", Recurso.Tipo.EQUIPAMENTO, "Imagem"),
        ]:
            recursos[nome] = Recurso.objects.create(nome=nome, tipo=tipo, unidade=unidades[unidade])

        def cria_usuario(nome, perfil):
            primeiro, ultimo = nome.split()[0], nome.split()[-1]
            usuario = Usuario(
                username=slug(nome),
                first_name=primeiro,
                last_name=ultimo,
                email=f"{slug(nome)}@saga.exemplo",
                perfil=perfil,
                telefone=f"(11) 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}",
            )
            usuario.set_password("saga1234")
            usuario.save()
            return usuario

        medicos = {}
        for i, (nome, principal, segunda) in enumerate(MEDICOS, start=1):
            usuario = cria_usuario(nome, Usuario.Perfil.MEDICO)
            # O médico não é recurso: a agenda dele é checada pelos agendamentos (RN03).
            medico = Medico.objects.create(usuario=usuario, crm=f"SP{100000 + i}")
            for j, esp in enumerate(e for e in (principal, segunda) if e):
                HabilitacaoMedico.objects.create(
                    medico=medico,
                    especialidade=especialidades[esp],
                    rqe=f"RQE{2000 + 10 * i + j}",
                    data_habilitacao=agora.date() - timedelta(days=900 - 200 * j + 30 * i),
                )
            medicos[nome] = medico

        enfermeiros = []
        for i, (nome, unidade) in enumerate(ENFERMEIROS, start=1):
            usuario = cria_usuario(nome, Usuario.Perfil.ENFERMEIRO)
            enfermeiros.append(
                Enfermeiro.objects.create(
                    usuario=usuario, coren=f"COREN-SP{50000 + i}", unidade=unidades[unidade]
                )
            )

        pacientes = []
        for nome in NOMES:
            usuario = cria_usuario(nome, Usuario.Perfil.PACIENTE)
            pacientes.append(
                Paciente.objects.create(
                    usuario=usuario,
                    cpf=gerar_cpf(rng),
                    data_nascimento=agora.date() - timedelta(days=rng.randint(7000, 25000)),
                    cartao_sus="".join(str(rng.randint(0, 9)) for _ in range(15)),
                )
            )

        # -------------------------------------------------- catálogo e disponibilidade (MED001)
        hoje = timezone.localdate()
        inicio_historico = hoje - timedelta(days=45)
        inicio_exames = hoje - timedelta(days=21)
        fim_agenda = hoje + timedelta(days=90)
        tipos = {}
        for nome, modalidade, esp, duracao, preparo, requisitos in CATALOGO:
            tipo = TipoProcedimento.objects.create(
                nome=nome,
                modalidade=modalidade,
                especialidade=especialidades[esp],
                duracao_padrao_min=duracao,
                exige_preparo=preparo,
            )
            for recurso_nome, ocupacao, setup, dias, h_ini, h_fim in requisitos:
                req = RequisitoProcedimento(
                    tipo_procedimento=tipo,
                    recurso=recursos[recurso_nome],
                    tempo_ocupacao_min=ocupacao,
                    tempo_setup_min=setup,
                    data_inicial=inicio_historico,
                    data_final=fim_agenda,
                    hora_inicio=h_ini,
                    hora_fim=h_fim,
                )
                req.full_clean()
                req.save()
                DiaDisponibilidade.objects.bulk_create(
                    DiaDisponibilidade(requisito=req, dia_semana=d) for d in dias
                )
            tipos[nome] = tipo

        # O histórico é gravado "no passado": as funções de serviço recebem o
        # instante como parâmetro, e os horários realizados são simulados.
        historico = []
        consultas_realizadas = {}  # nome do tipo -> agendamentos que servem de origem

        def desfecho_passado():
            return rng.choices(
                [Agendamento.Status.REALIZADO, Agendamento.Status.CANCELADO, Agendamento.Status.AUSENCIA],
                weights=[84, 9, 7],
            )[0]

        # -------------------------------------------------- consultas (PAC001)
        for tipo in [t for t in tipos.values() if t.modalidade == "CONSULTA"]:
            for req in servicos.salas_de_consulta(servicos._carrega_tipo(tipo)):
                for inicio, _ in req.janelas(inicio_historico, hoje + timedelta(days=14)):
                    futuro = inicio > agora
                    if rng.random() > (0.35 if futuro else 0.6):
                        continue
                    paciente = rng.choice(pacientes)
                    try:
                        ag = servicos.criar_agendamento(paciente, tipo, inicio, requisito=req)
                    except servicos.JanelaOcupada:
                        continue
                    desfecho = None if futuro else desfecho_passado()
                    historico.append((ag, desfecho))
                    if desfecho == Agendamento.Status.REALIZADO:
                        consultas_realizadas.setdefault(tipo.nome, []).append(ag)

        def origem_para(tipo, antes_de):
            """Uma consulta realizada antes do exame, de uma especialidade que pede esse exame."""
            candidatas = [
                ag for nome in ORIGEM[tipo.nome] for ag in consultas_realizadas.get(nome, [])
                if ag.inicio_planejado < antes_de - timedelta(days=2)
            ]
            return rng.choice(candidatas) if candidatas else None

        # -------------------------------------------------- exames e cirurgias (MED003)
        procedimentos = [t for t in tipos.values() if t.modalidade != "CONSULTA"]
        dia = inicio_exames
        while dia <= hoje + timedelta(days=14):
            if dia.weekday() < 5:
                for tipo in procedimentos:
                    for _ in range(2):
                        hora = rng.choice([7, 8, 9, 10, 13, 14, 15, 16])
                        inicio = timezone.make_aware(
                            datetime.combine(dia, time(hora, rng.choice([0, 30])))
                        )
                        origem = origem_para(tipo, inicio)
                        if origem is None:
                            continue
                        itens = servicos.recursos_necessarios(servicos._carrega_tipo(tipo))
                        if not servicos.combinacao_livre(itens, inicio):
                            continue  # a combinação não está livre junta: pula, como o sistema faria
                        fim = inicio + timedelta(minutes=tipo.duracao_padrao_min)
                        if servicos.escolher_medico(
                            servicos.medicos_habilitados(tipo.especialidade), inicio, fim
                        ) is None:
                            continue  # nenhum médico habilitado livre (RN03)
                        criada = origem.fim_planejado + timedelta(minutes=5)
                        sol = SolicitacaoProcedimento.objects.create(
                            agendamento_origem=origem,
                            tipo_procedimento=tipo,
                            prioridade=rng.choices([1, 2, 3], weights=[6, 3, 1])[0],
                            justificativa="Indicação clínica registrada em consulta (dado sintético).",
                            criada_em=criada,
                        )
                        servicos.aprovar_solicitacao(sol, agora=criada + timedelta(hours=rng.randint(2, 30)))
                        ag = servicos.criar_agendamento(origem.paciente, tipo, inicio, solicitacao=sol)
                        historico.append((ag, None if inicio > agora else desfecho_passado()))
            dia += timedelta(days=1)

        # -------------------------------------------------- desfechos e execução (ENF002)
        for ag, desfecho in historico:
            if desfecho is None:
                abre, fecha = servicos.janela_de_confirmacao(ag)
                if abre <= agora <= fecha and rng.random() < 0.5:
                    servicos.confirmar_presenca(ag, agora=abre + (agora - abre) / 2)
                continue
            if desfecho == Agendamento.Status.CANCELADO:
                servicos.cancelar_agendamento(
                    ag,
                    rng.choice(MOTIVOS_CANCELAMENTO),
                    agora=ag.inicio_planejado - timedelta(hours=rng.choice([6, 30, 72])),
                )
                continue
            if desfecho == Agendamento.Status.AUSENCIA:
                ag.status = Agendamento.Status.AUSENCIA
                ag.save(update_fields=["status"])
                ag.alocacoes.update(status=AlocacaoRecurso.Status.LIBERADA)
                continue

            # Realizado: o enfermeiro abre e encerra cada alocação. Aqui nasce o REALIZADO.
            atraso = rng.choices([0, 5, 10, 15, 25, 40], weights=[35, 25, 18, 12, 7, 3])[0]
            variacao = rng.randint(-10, 20) if ag.tipo_procedimento.modalidade != "CONSULTA" else rng.randint(-8, 6)
            enfermeiro = rng.choice(enfermeiros)
            for aloc in ag.alocacoes.all():
                inicio_real = aloc.inicio_planejado + timedelta(minutes=atraso)
                aloc.abrir_ocupacao(enfermeiro, inicio_real)
                if atraso > 30:
                    aloc.motivo_atraso = rng.choice(
                        [c for c, _ in AlocacaoRecurso.MotivoAtraso.choices if c != "OUTRO"]
                    )
                    aloc.save(update_fields=["motivo_atraso"])
                duracao_real = max(10, aloc.duracao_planejada_min + variacao)
                aloc.encerrar_ocupacao(inicio_real + timedelta(minutes=duracao_real))
            ag.status = Agendamento.Status.REALIZADO
            ag.save(update_fields=["status"])

            # ENF001: triagem para quem exige preparo e para parte das consultas.
            if ag.tipo_procedimento.exige_preparo or rng.random() < 0.3:
                sinais = dict(
                    pa_sistolica=rng.randint(105, 175),
                    pa_diastolica=rng.randint(60, 95),
                    fc=rng.randint(55, 115),
                    temperatura=round(rng.uniform(35.8, 38.3), 1),
                    saturacao=rng.randint(91, 99),
                )
                sugerida = sugerir_classificacao(**sinais)
                escolhida = sugerida
                observacoes = ""
                if sugerida > 1 and rng.random() < 0.1:
                    escolhida = sugerida - 1
                    observacoes = "Paciente estável, sinais elevados por ansiedade (dado sintético)."
                Triagem.objects.create(
                    agendamento=ag,
                    enfermeiro=enfermeiro,
                    pressao_sistolica=sinais["pa_sistolica"],
                    pressao_diastolica=sinais["pa_diastolica"],
                    frequencia_cardiaca=sinais["fc"],
                    temperatura=Decimal(str(sinais["temperatura"])),
                    saturacao=sinais["saturacao"],
                    classificacao_sugerida=sugerida,
                    classificacao_risco=escolhida,
                    observacoes=observacoes,
                    realizada_em=ag.inicio_planejado - timedelta(minutes=25),
                )

            # MED002: três registros clínicos por atendimento.
            liberado = ag.tipo_procedimento.modalidade == "EXAME" and rng.random() < 0.8
            for tipo_reg, texto in [
                (RegistroClinico.Tipo.EVOLUCAO, "Paciente atendido, sem intercorrências no procedimento (dado sintético)."),
                (RegistroClinico.Tipo.DIAGNOSTICO, "Hipótese compatível com a queixa principal (dado sintético)."),
                (RegistroClinico.Tipo.CONDUTA, "Orientações fornecidas e retorno programado (dado sintético)."),
            ]:
                RegistroClinico.objects.create(
                    agendamento=ag,
                    medico=ag.medico_responsavel,
                    tipo=tipo_reg,
                    texto=texto,
                    liberado_em=ag.fim_planejado + timedelta(days=1) if liberado else None,
                )
            # auto_now_add grava o instante do seed; o histórico simulado usa o do atendimento.
            ag.registros.update(criado_em=ag.fim_planejado)

        # -------------------------------------------------- fila de espera (RN04)
        # Parte aprovada (já está na fila) e parte aguardando a aprovação do enfermeiro.
        for i in range(16):
            tipo = rng.choice(procedimentos)
            origem = origem_para(tipo, agora)
            if origem is None:
                continue
            # O pedido é feito no fim da consulta de origem.
            criada = origem.fim_planejado + timedelta(minutes=rng.randint(1, 10))
            sol = SolicitacaoProcedimento.objects.create(
                agendamento_origem=origem,
                tipo_procedimento=tipo,
                prioridade=rng.choices([1, 2, 3], weights=[5, 3, 2])[0],
                justificativa="Indicação clínica registrada em consulta (dado sintético).",
                criada_em=criada,
            )
            if i % 4:  # três em cada quatro já foram aprovadas
                servicos.aprovar_solicitacao(sol, agora=criada + timedelta(hours=rng.randint(1, 20)))

        # -------------------------------------------------- RN14: último acesso ao prontuário
        for ag in Agendamento.objects.filter(status=Agendamento.Status.REALIZADO)[:30]:
            ag.prontuario_acessado_em = ag.inicio_planejado + timedelta(minutes=5)
            ag.save(update_fields=["prontuario_acessado_em"])

        # -------------------------------------------------- usuária de demonstração
        # Garante que a paciente "ana.ribeiro" tenha o que mostrar em cada tela.
        ana = pacientes[0]
        self._prepara_demo(ana, tipos, consultas_realizadas, agora)

        self._resumo()

    def _prepara_demo(self, ana, tipos, consultas_realizadas, agora):
        # Uma consulta dentro da janela de confirmação (entre 24 h e 72 h).
        alvo = agora + timedelta(hours=48)
        feito = False
        for tipo in [t for t in tipos.values() if t.modalidade == "CONSULTA"]:
            for req in servicos.salas_de_consulta(servicos._carrega_tipo(tipo)):
                for inicio, _ in req.janelas(alvo.date() - timedelta(days=1), alvo.date() + timedelta(days=3)):
                    if agora + timedelta(hours=25) < inicio < agora + timedelta(hours=71):
                        try:
                            servicos.criar_agendamento(ana, tipo, inicio, requisito=req)
                            feito = True
                            break
                        except servicos.JanelaOcupada:
                            continue
                if feito:
                    break
            if feito:
                break
        # Uma consulta mais adiante, para cancelar ou remarcar (PAC003).
        for req in servicos.salas_de_consulta(servicos._carrega_tipo(tipos["Consulta ortopédica"])):
            hoje = timezone.localdate()
            for inicio, _ in req.janelas(hoje + timedelta(days=6), hoje + timedelta(days=20)):
                try:
                    servicos.criar_agendamento(ana, tipos["Consulta ortopédica"], inicio, requisito=req)
                    break
                except servicos.JanelaOcupada:
                    continue
            break
        # Uma consulta realizada da Ana com a Dra. Helena, que gera dois pedidos:
        # um já aprovado (na fila) e um aguardando a aprovação do enfermeiro.
        origem = (
            Agendamento.objects.filter(
                paciente=ana, status=Agendamento.Status.REALIZADO,
                medico_responsavel__usuario__username="helena.vasconcelos",
            ).order_by("-inicio_planejado").first()
        )
        if origem is None:
            origem = self._consulta_passada(ana, tipos["Consulta ortopédica"], agora)
        if origem is None:
            return
        tomografia = tipos["Tomografia de crânio"]
        sol = SolicitacaoProcedimento.objects.create(
            agendamento_origem=origem,
            tipo_procedimento=tomografia,
            prioridade=SolicitacaoProcedimento.Prioridade.PRIORITARIA,
            justificativa="Cefaleia persistente, investigar (dado sintético).",
            criada_em=origem.fim_planejado + timedelta(minutes=3),
        )
        servicos.aprovar_solicitacao(sol, agora=origem.fim_planejado + timedelta(hours=5))
        SolicitacaoProcedimento.objects.create(
            agendamento_origem=origem,
            tipo_procedimento=tipos["Artroscopia de joelho"],
            prioridade=SolicitacaoProcedimento.Prioridade.ELETIVA,
            justificativa="Dor no joelho direito há três meses, sem melhora (dado sintético).",
            criada_em=origem.fim_planejado + timedelta(minutes=4),
        )

    def _consulta_passada(self, paciente, tipo, agora):
        """Grava uma consulta já realizada, no primeiro horário livre da última semana."""
        for req in servicos.salas_de_consulta(servicos._carrega_tipo(tipo)):
            hoje = timezone.localdate()
            for inicio, _ in reversed(list(req.janelas(hoje - timedelta(days=10), hoje))):
                if inicio >= agora - timedelta(days=1):
                    continue
                try:
                    ag = servicos.criar_agendamento(paciente, tipo, inicio, requisito=req)
                except servicos.JanelaOcupada:
                    continue
                ag.status = Agendamento.Status.REALIZADO
                ag.save(update_fields=["status"])
                return ag
        return None

    def _resumo(self):
        linhas = [
            ("Unidades", Unidade.objects.count()),
            ("Recursos", Recurso.objects.count()),
            ("Tipos de procedimento", TipoProcedimento.objects.count()),
            ("Disponibilidades", RequisitoProcedimento.objects.count()),
            ("Pacientes", Paciente.objects.count()),
            ("Médicos", Medico.objects.count()),
            ("Enfermeiros", Enfermeiro.objects.count()),
            ("Agendamentos", Agendamento.objects.count()),
            ("Alocações de recurso", AlocacaoRecurso.objects.count()),
            ("Triagens", Triagem.objects.count()),
            ("Registros clínicos", RegistroClinico.objects.count()),
            ("Solicitações na fila", SolicitacaoProcedimento.objects.filter(status="NA_FILA").count()),
            ("Aguardando aprovação",
             SolicitacaoProcedimento.objects.filter(status="AGUARDANDO_APROVACAO").count()),
        ]
        self.stdout.write(self.style.SUCCESS("\nBanco populado com dados sintéticos.\n"))
        for rotulo, valor in linhas:
            self.stdout.write(f"  {rotulo} ".ljust(30, ".") + f" {valor}")
        self.stdout.write("\n  Senha de todos os usuários: saga1234")
        self.stdout.write("  Para testar: ana.ribeiro (paciente), helena.vasconcelos (médica),")
        self.stdout.write("               fernanda.rocha (enfermeira)\n")
