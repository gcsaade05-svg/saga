"""
Testes da API e das regras de negócio. Rodar com:  python manage.py test core

O banco de teste é populado pelo mesmo comando seed, então os testes exercitam
o sistema com os dados de demonstração.
"""
import io
from datetime import timedelta

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core import servicos
from core.models import (
    Agendamento,
    AlocacaoRecurso,
    Especialidade,
    Paciente,
    RegistroClinico,
    SolicitacaoProcedimento,
)
from core.utils import cpf_valido, gerar_cpf


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed", stdout=io.StringIO())

    def setUp(self):
        cache.clear()
        self.api = APIClient()

    def entrar(self, usuario, senha="saga1234"):
        # Login por sessão (aula 5): o APIClient guarda o cookie sessionid.
        r = self.api.post("/api/v1/auth/login/", {"username": usuario, "senha": senha}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        return r.data["usuario"]


class AutenticacaoTests(Base):
    def test_login_devolve_perfil(self):
        u = self.entrar("ana.ribeiro")
        self.assertEqual(u["perfil"], "PACIENTE")

    def test_mensagem_generica_rn20(self):
        r1 = self.api.post("/api/v1/auth/login/", {"username": "ana.ribeiro", "senha": "errada"}, format="json")
        r2 = self.api.post("/api/v1/auth/login/", {"username": "ninguem", "senha": "errada"}, format="json")
        self.assertEqual(r1.status_code, 401)
        self.assertEqual(r1.data, r2.data)

    def test_bloqueio_apos_cinco_falhas(self):
        for _ in range(5):
            self.api.post("/api/v1/auth/login/", {"username": "ana.ribeiro", "senha": "x"}, format="json")
        r = self.api.post("/api/v1/auth/login/", {"username": "ana.ribeiro", "senha": "saga1234"}, format="json")
        self.assertEqual(r.status_code, 429)

    def test_cadastro_paciente(self):
        dados = {
            "nome_completo": "Teste da Silva", "cpf": gerar_cpf(), "data_nascimento": "1990-05-10",
            "email": "teste@exemplo.com", "telefone": "(11) 99999-0000", "username": "teste.silva",
            "senha": "UmaSenhaBoa#2026", "confirmar_senha": "UmaSenhaBoa#2026",
        }
        r = self.api.post("/api/v1/auth/cadastro/", dados, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(Paciente.objects.filter(usuario__username="teste.silva").exists())
        dados["username"] = "outro"
        dados["email"] = "outro@exemplo.com"
        r = self.api.post("/api/v1/auth/cadastro/", dados, format="json")
        self.assertIn("cpf", r.data)  # CPF repetido

    def test_cpf(self):
        self.assertTrue(cpf_valido("529.982.247-25"))
        self.assertFalse(cpf_valido("111.111.111-11"))
        self.assertFalse(cpf_valido("529.982.247-24"))

    def test_login_cria_sessao_e_logout_por_post(self):
        self.entrar("ana.ribeiro")
        self.assertIn("sessionid", self.api.cookies)
        self.assertEqual(self.api.get("/api/v1/auth/eu/").data["usuario"]["username"], "ana.ribeiro")
        self.assertEqual(self.api.get("/api/v1/auth/logout/").status_code, 405)  # logout é por POST
        self.assertEqual(self.api.post("/api/v1/auth/logout/").status_code, 204)
        self.assertIsNone(self.api.get("/api/v1/auth/eu/").data["usuario"])
        self.assertEqual(self.api.get("/api/v1/agendamentos/").status_code, 401)

    def test_csrf_exigido_com_sessao(self):
        from rest_framework.test import APIClient
        cliente = APIClient(enforce_csrf_checks=True)
        r = cliente.post("/api/v1/auth/login/", {"username": "ana.ribeiro", "senha": "saga1234"}, format="json")
        self.assertEqual(r.status_code, 200)
        r = cliente.post("/api/v1/auth/logout/")
        self.assertEqual(r.status_code, 403)  # sem o cabeçalho X-CSRFToken
        cliente.get("/api/v1/auth/eu/")  # entrega o cookie csrftoken
        r = cliente.post("/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=cliente.cookies["csrftoken"].value)
        self.assertEqual(r.status_code, 204)

    def test_basic_auth_como_no_postman(self):
        import base64
        cred = base64.b64encode(b"fernanda.rocha:saga1234").decode()
        r = self.api.get("/api/v1/painel/", HTTP_AUTHORIZATION=f"Basic {cred}")
        self.assertEqual(r.status_code, 200)

    def test_usuarios_ficam_no_grupo_do_perfil(self):
        from core.models import Usuario
        for username, grupo in [("ana.ribeiro", "Paciente"), ("helena.vasconcelos", "Medico"),
                                ("fernanda.rocha", "Enfermeiro")]:
            u = Usuario.objects.get(username=username)
            self.assertEqual(list(u.groups.values_list("name", flat=True)), [grupo])
        enf = Usuario.objects.get(username="fernanda.rocha")
        self.assertTrue(enf.has_perm("core.change_solicitacaoprocedimento"))
        self.assertFalse(Usuario.objects.get(username="ana.ribeiro").has_perm("core.add_recurso"))

    def test_perfil_errado_e_barrado(self):
        self.entrar("ana.ribeiro")
        self.assertEqual(self.api.get("/api/v1/painel/").status_code, 403)


class PacienteTests(Base):
    def setUp(self):
        super().setUp()
        self.entrar("ana.ribeiro")

    def test_agendar_consulta_e_resumo(self):
        esp = Especialidade.objects.get(nome="Ortopedia")
        janelas = self.api.get(f"/api/v1/janelas/?especialidade={esp.id}").data
        self.assertTrue(janelas)
        j = janelas[0]
        r = self.api.post("/api/v1/agendamentos/", {"requisito": j["requisito"], "inicio": j["inicio"]}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        # Só recursos físicos: a sala. O médico não é recurso (DER v1.2).
        self.assertEqual(r.data["totais"]["recursos"], 1)
        self.assertEqual(r.data["alocacoes"][0]["recurso_tipo"], "SALA")
        self.assertTrue(r.data["medico"])
        self.assertTrue(r.data["prontuario_liberado"])
        # A mesma janela não aparece mais e não pode ser ocupada de novo (RN02).
        r2 = self.api.post("/api/v1/agendamentos/", {"requisito": j["requisito"], "inicio": j["inicio"]}, format="json")
        self.assertEqual(r2.status_code, 409)

    def test_horario_fora_da_disponibilidade_e_recusado(self):
        esp = Especialidade.objects.get(nome="Ortopedia")
        j = self.api.get(f"/api/v1/janelas/?especialidade={esp.id}").data[0]
        inicio = timezone.localtime(j["inicio"]).replace(hour=3, minute=0).isoformat()
        r = self.api.post("/api/v1/agendamentos/", {"requisito": j["requisito"], "inicio": inicio}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_confirmar_presenca(self):
        ag = next(a for a in Agendamento.objects.filter(paciente__usuario__username="ana.ribeiro")
                  if servicos.pode_confirmar(a))
        r = self.api.post(f"/api/v1/agendamentos/{ag.id}/confirmar/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["status"], "CONFIRMADO")

    def test_cancelar_libera_recursos(self):
        ag = Agendamento.objects.filter(
            paciente__usuario__username="ana.ribeiro", status="AGENDADO",
            inicio_planejado__gt=timezone.now() + timedelta(days=2),
        ).first()
        r = self.api.post(f"/api/v1/agendamentos/{ag.id}/cancelar/", {"motivo": "curto"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.api.post(f"/api/v1/agendamentos/{ag.id}/cancelar/", {"motivo": "Não poderei comparecer nesse dia."}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(ag.alocacoes.exclude(status="LIBERADA").exists())  # RN07

    def test_remarcar_cria_novo_ligado_ao_original(self):
        ag = Agendamento.objects.filter(
            paciente__usuario__username="ana.ribeiro", status="AGENDADO",
            tipo_procedimento__modalidade="CONSULTA",
            inicio_planejado__gt=timezone.now() + timedelta(days=2),
        ).first()
        j = self.api.get(f"/api/v1/janelas/?especialidade={ag.tipo_procedimento.especialidade_id}").data[0]
        r = self.api.post(f"/api/v1/agendamentos/{ag.id}/remarcar/",
                          {"motivo": "Conflito com o trabalho.", "requisito": j["requisito"], "inicio": j["inicio"]}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["remarcacao_de"], ag.id)
        ag.refresh_from_db()
        self.assertEqual(ag.status, "CANCELADO")

    def test_nao_ve_agendamento_de_outro(self):
        outro = Agendamento.objects.exclude(paciente__usuario__username="ana.ribeiro").first()
        self.assertEqual(self.api.get(f"/api/v1/agendamentos/{outro.id}/").status_code, 404)

    def test_fila_com_posicao(self):
        r = self.api.get("/api/v1/solicitacoes/?status=NA_FILA")
        self.assertTrue(all(s["posicao_na_fila"] >= 1 for s in r.data))


class MedicoTests(Base):
    def setUp(self):
        super().setUp()
        self.entrar("helena.vasconcelos")

    def test_prontuario_grava_instante_no_agendamento(self):
        ag = Agendamento.objects.filter(
            medico_responsavel__usuario__username="helena.vasconcelos", prontuario_liberado=True,
        ).exclude(status="CANCELADO").order_by("-inicio_planejado").first()
        r = self.api.get(f"/api/v1/prontuario/{ag.paciente_id}/")
        self.assertEqual(r.status_code, 200)
        vinculo = Agendamento.objects.get(pk=r.data["acesso"]["agendamento"])
        self.assertEqual(vinculo.paciente_id, ag.paciente_id)
        self.assertIsNotNone(vinculo.prontuario_acessado_em)  # RN14

    def test_prontuario_sem_vinculo_e_negado(self):
        from core.models import Usuario
        u = Usuario.objects.create_user("sem.vinculo", password="x", perfil="PACIENTE")
        p = Paciente.objects.create(usuario=u, cpf=gerar_cpf(), data_nascimento="1980-01-01")
        self.assertEqual(self.api.get(f"/api/v1/prontuario/{p.id}/").status_code, 403)

    def test_cancelado_nao_libera_prontuario(self):
        ag = Agendamento.objects.filter(medico_responsavel__usuario__username="helena.vasconcelos").first()
        Agendamento.objects.filter(paciente=ag.paciente, medico_responsavel=ag.medico_responsavel).update(
            prontuario_liberado=False
        )
        self.assertEqual(self.api.get(f"/api/v1/prontuario/{ag.paciente_id}/").status_code, 403)

    def test_solicitar_exame_e_proibir_consulta(self):
        from core.models import TipoProcedimento
        origem = Agendamento.objects.filter(
            medico_responsavel__usuario__username="helena.vasconcelos", status="REALIZADO"
        ).first()
        exame = TipoProcedimento.objects.get(nome="Artroscopia de joelho")
        consulta = TipoProcedimento.objects.get(nome="Consulta ortopédica")
        base = {"agendamento_origem": origem.id, "prioridade": 2,
                "justificativa": "Dor no joelho há três meses, sem melhora."}
        r = self.api.post("/api/v1/solicitacoes/", {**base, "tipo_procedimento": exame.id}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        # Médico e paciente vêm do agendamento de origem; nasce aguardando aprovação.
        self.assertEqual(r.data["paciente"], origem.paciente_id)
        self.assertEqual(r.data["status"], "AGUARDANDO_APROVACAO")
        self.assertFalse(r.data["aprovada"])
        self.assertIsNone(r.data["posicao_na_fila"])
        self.assertEqual(self.api.post("/api/v1/solicitacoes/", {**base, "tipo_procedimento": consulta.id}, format="json").status_code, 400)

    def test_nao_solicita_a_partir_de_atendimento_de_outro_medico(self):
        from core.models import TipoProcedimento
        alheio = Agendamento.objects.exclude(medico_responsavel__usuario__username="helena.vasconcelos").first()
        exame = TipoProcedimento.objects.get(nome="Tomografia de crânio")
        r = self.api.post("/api/v1/solicitacoes/", {"agendamento_origem": alheio.id, "tipo_procedimento": exame.id,
                          "prioridade": 1, "justificativa": "Cefaleia persistente há duas semanas."}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_atendimento_grava_tres_registros(self):
        ag = Agendamento.objects.filter(
            medico_responsavel__usuario__username="helena.vasconcelos", status__in=["AGENDADO", "CONFIRMADO"]
        ).first()
        r = self.api.post(f"/api/v1/agendamentos/{ag.id}/atendimento/", {
            "evolucao": "Paciente refere melhora da dor após repouso.",
            "diagnostico": "Tendinopatia patelar.", "conduta": "Fisioterapia por seis semanas.",
        }, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(RegistroClinico.objects.filter(agendamento=ag).count(), 3)

    def test_publicar_disponibilidade_exige_habilitacao(self):
        esp = Especialidade.objects.get(nome="Cardiologia")  # Helena não é cardiologista
        from core.models import Recurso, RequisitoProcedimento
        sala = Recurso.objects.get(nome="Sala de Imagem A")  # sala ainda sem consulta ortopédica
        hoje = timezone.localdate()
        dados = {"especialidade": esp.id, "sala": sala.id, "data_inicial": str(hoje),
                 "data_final": str(hoje + timedelta(days=30)), "hora_inicio": "18:00",
                 "hora_fim": "19:00", "duracao_consulta_min": 30, "dias": [5]}
        self.assertEqual(self.api.post("/api/v1/disponibilidades/", dados, format="json").status_code, 400)
        dados["especialidade"] = Especialidade.objects.get(nome="Ortopedia").id
        r = self.api.post("/api/v1/disponibilidades/", dados, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        # A disponibilidade foi gravada no requisito da consulta, com os dias em tabela própria.
        req = RequisitoProcedimento.objects.get(pk=r.data["id"])
        self.assertEqual(req.tipo_procedimento.nome, "Consulta ortopédica")
        self.assertEqual(list(req.dias.values_list("dia_semana", flat=True)), [5])
        self.assertEqual(r.data["vagas_livres"] > 0, True)


class EnfermeiroTests(Base):
    def setUp(self):
        super().setUp()
        self.entrar("fernanda.rocha")

    def test_painel_tem_totais_que_fecham(self):
        r = self.api.get("/api/v1/painel/")
        self.assertEqual(r.status_code, 200)
        soma = sum(l["total"] for l in r.data["linhas"])
        self.assertAlmostEqual(soma, r.data["total_geral"], delta=0.05)

    def test_aprovar_solicitacao_poe_na_fila(self):
        s = SolicitacaoProcedimento.objects.filter(status="AGUARDANDO_APROVACAO").first()
        r = self.api.post(f"/api/v1/solicitacoes/{s.id}/aprovar/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["status"], "NA_FILA")
        self.assertTrue(r.data["aprovada"])
        self.assertIsNotNone(r.data["aprovada_em"])
        self.assertEqual(self.api.post(f"/api/v1/solicitacoes/{s.id}/aprovar/").status_code, 400)

    def test_nao_encaixa_sem_aprovacao(self):
        s = SolicitacaoProcedimento.objects.filter(status="AGUARDANDO_APROVACAO").first()
        inicio = (timezone.now() + timedelta(days=3)).isoformat()
        r = self.api.post("/api/v1/encaixe/", {"solicitacao": s.id, "inicio": inicio}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.api.get("/api/v1/painel/")
        ids = {j["candidato"]["solicitacao_id"] for j in r.data["janelas_ociosas"] if j["candidato"]}
        self.assertNotIn(s.id, ids)

    def test_encaixe_da_fila(self):
        r = self.api.get("/api/v1/painel/")
        janela = next((j for j in r.data["janelas_ociosas"] if j["candidato"]), None)
        if janela is None:
            self.skipTest("nenhuma janela com candidato no período")
        c = janela["candidato"]
        r = self.api.post("/api/v1/encaixe/", {"solicitacao": c["solicitacao_id"], "inicio": c["inicio_sugerido"]}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(SolicitacaoProcedimento.objects.get(pk=c["solicitacao_id"]).status, "AGENDADA")

    def test_abrir_e_encerrar_ocupacao(self):
        aloc = AlocacaoRecurso.objects.filter(
            recurso__unidade__nome="Centro Cirúrgico A", status="PLANEJADA",
            inicio_planejado__gt=timezone.now(),
        ).order_by("inicio_planejado").first()
        # A lista de alocações mostra um dia por vez (hoje, se nada for dito),
        # então informamos o dia da alocação escolhida.
        dia = timezone.localtime(aloc.inicio_planejado).date().isoformat()
        r = self.api.post(f"/api/v1/alocacoes/{aloc.id}/abrir/?data={dia}", {}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        r = self.api.post(f"/api/v1/alocacoes/{aloc.id}/encerrar/?data={dia}", {}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["status"], "ENCERRADA")

    def test_cadastro_de_recurso_so_na_propria_unidade(self):
        from core.models import Unidade
        minha = Unidade.objects.get(nome="Centro Cirúrgico A")
        outra = Unidade.objects.get(nome="Imagem")
        r = self.api.post("/api/v1/recursos/", {"nome": "Sala Cirúrgica 3", "tipo": "SALA", "unidade": minha.id}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        r = self.api.post("/api/v1/recursos/", {"nome": "Sala X", "tipo": "SALA", "unidade": outra.id}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_sugestao_de_risco(self):
        r = self.api.post("/api/v1/triagem/sugerir/", {"pressao_sistolica": 210, "pressao_diastolica": 110,
                          "frequencia_cardiaca": 90, "temperatura": 36.5, "saturacao": 97}, format="json")
        self.assertEqual(r.data["classificacao_sugerida"], 5)
