"""
Painel de Ocupação no terminal — prova que a entidade multidimensional funciona
antes de existir qualquer frontend.

Imprime a tabela cruzada RECURSO x DIA com subtotal por linha, subtotal por coluna
e total geral, mais as janelas ociosas candidatas a encaixe da fila de espera.

Uso:  python manage.py ocupacao
      python manage.py ocupacao --dias 7
      python manage.py ocupacao --unidade "Centro Cirúrgico A"
"""
from collections import defaultdict
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import AlocacaoRecurso, Recurso, SolicitacaoProcedimento


class Command(BaseCommand):
    help = "Imprime o Painel de Ocupação (tabela cruzada recurso x dia) no terminal."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=7, help="Janela de análise. Padrão: 7.")
        parser.add_argument("--unidade", type=str, default=None, help="Filtra por unidade.")

    def handle(self, *args, **options):
        dias = options["dias"]
        fim = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        inicio = fim - timedelta(days=dias)

        alocacoes = AlocacaoRecurso.objects.select_related("recurso", "recurso__unidade").filter(
            inicio_planejado__gte=inicio, inicio_planejado__lt=fim + timedelta(days=1)
        )
        if options["unidade"]:
            alocacoes = alocacoes.filter(recurso__unidade__nome__icontains=options["unidade"])

        if not alocacoes.exists():
            self.stdout.write(
                self.style.WARNING(
                    "Nenhuma alocação no período. Rode primeiro: python manage.py seed"
                )
            )
            return

        # ------------------------------------------------ agregação do fato
        # dimensões: recurso x dia | medidas: horas planejadas, realizadas, ociosas
        planejado = defaultdict(float)
        realizado = defaultdict(float)
        recursos = set()
        dias_set = set()

        for aloc in alocacoes:
            dia = timezone.localtime(aloc.inicio_planejado).date()
            chave = (aloc.recurso.nome, dia)
            recursos.add(aloc.recurso.nome)
            dias_set.add(dia)

            planejado[chave] += aloc.duracao_planejada_min / 60
            if aloc.duracao_realizada_min:
                realizado[chave] += aloc.duracao_realizada_min / 60

        recursos = sorted(recursos)
        dias_ordenados = sorted(dias_set)

        # ------------------------------------------------ impressão
        self.stdout.write("")
        titulo = "PAINEL DE OCUPAÇÃO — horas realizadas por recurso × dia"
        self.stdout.write(self.style.MIGRATE_HEADING(titulo))
        periodo = (
            f"{inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}"
            + (f"  ·  unidade: {options['unidade']}" if options["unidade"] else "")
        )
        self.stdout.write(periodo)
        self.stdout.write("")

        larg_nome = max(len(r) for r in recursos) + 2
        cab = "Recurso".ljust(larg_nome) + "".join(
            d.strftime("%d/%m").rjust(9) for d in dias_ordenados
        ) + "Total".rjust(11)
        self.stdout.write(self.style.HTTP_INFO(cab))
        self.stdout.write("-" * len(cab))

        total_coluna = defaultdict(float)
        total_geral = 0.0

        for recurso in recursos:
            linha = recurso.ljust(larg_nome)
            soma_linha = 0.0
            for dia in dias_ordenados:
                valor = realizado[(recurso, dia)]
                soma_linha += valor
                total_coluna[dia] += valor
                linha += (f"{valor:,.1f}".replace(".", ",") if valor else "—").rjust(9)
            total_geral += soma_linha
            linha += f"{soma_linha:,.1f}".replace(".", ",").rjust(11)
            self.stdout.write(linha)

        self.stdout.write("-" * len(cab))
        rodape = "TOTAL GERAL".ljust(larg_nome)
        for dia in dias_ordenados:
            rodape += f"{total_coluna[dia]:,.1f}".replace(".", ",").rjust(9)
        rodape += f"{total_geral:,.1f}".replace(".", ",").rjust(11)
        self.stdout.write(self.style.SUCCESS(rodape))

        # ------------------------------------------------ medidas derivadas
        horas_planejadas = sum(planejado.values())
        horas_realizadas = sum(realizado.values())
        ociosas = horas_planejadas - horas_realizadas
        taxa = (horas_realizadas / horas_planejadas * 100) if horas_planejadas else 0

        atrasos = [
            (timezone.localtime(a.inicio_realizado) - timezone.localtime(a.inicio_planejado))
            .total_seconds() / 60
            for a in alocacoes
            if a.inicio_realizado
        ]
        atraso_medio = sum(atrasos) / len(atrasos) if atrasos else 0

        liberadas = alocacoes.filter(status=AlocacaoRecurso.Status.LIBERADA)
        horas_liberadas = sum(a.duracao_planejada_min for a in liberadas) / 60

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("MEDIDAS DO PERÍODO"))
        self.stdout.write(f"  Horas planejadas .......... {horas_planejadas:8.1f} h")
        self.stdout.write(f"  Horas realizadas .......... {horas_realizadas:8.1f} h")
        self.stdout.write(f"  Horas ociosas ............. {ociosas:8.1f} h")
        self.stdout.write(f"  Taxa de ocupação .......... {taxa:8.1f} %")
        self.stdout.write(f"  Atraso médio de início .... {atraso_medio:8.1f} min")
        self.stdout.write(
            f"  Janelas liberadas ......... {liberadas.count():8d}  "
            f"({horas_liberadas:.1f} h devolvidas por cancelamento ou ausência)"
        )

        # ------------------------------------------------ encaixe da fila
        fila = SolicitacaoProcedimento.objects.filter(
            status=SolicitacaoProcedimento.Status.NA_FILA,
            aprovada=True,
        ).select_related("agendamento_origem__paciente__usuario", "tipo_procedimento")[:5]

        if fila:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING("FILA DE ESPERA — candidatos a encaixe"))
            for i, s in enumerate(fila, start=1):
                espera = (timezone.now() - s.criada_em).days
                self.stdout.write(
                    f"  {i}. {s.tipo_procedimento.nome:28s} "
                    f"{s.get_prioridade_display():12s} "
                    f"{espera:3d} dias na fila   {s.paciente}"
                )
            self.stdout.write("")
            self.stdout.write(
                "  → No Painel de Ocupação da tela, cada janela ociosa terá um botão "
                "para encaixar o primeiro da fila."
            )
        self.stdout.write("")
