"""
Django Admin do SAGA.

Além de servir para o grupo navegar nos dados, é por aqui que se mantém o
catálogo institucional (fora do escopo dos casos de uso, seção 1.2).
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
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


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "perfil", "is_staff")
    list_filter = ("perfil", "is_staff", "is_active")
    fieldsets = UserAdmin.fieldsets + (("SAGA", {"fields": ("perfil", "telefone")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("SAGA", {"fields": ("perfil", "telefone")}),)


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ("usuario", "cpf", "data_nascimento")
    search_fields = ("usuario__first_name", "usuario__last_name", "cpf")


class HabilitacaoInline(admin.TabularInline):
    model = HabilitacaoMedico
    extra = 1


@admin.register(Medico)
class MedicoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "crm", "lista_especialidades")
    search_fields = ("usuario__first_name", "usuario__last_name", "crm")
    inlines = [HabilitacaoInline]

    @admin.display(description="especialidades")
    def lista_especialidades(self, obj):
        return ", ".join(e.nome for e in obj.especialidades.all()) or "-"


@admin.register(Enfermeiro)
class EnfermeiroAdmin(admin.ModelAdmin):
    list_display = ("usuario", "coren", "unidade")
    list_filter = ("unidade",)


@admin.register(Especialidade)
class EspecialidadeAdmin(admin.ModelAdmin):
    list_display = ("nome",)
    search_fields = ("nome",)


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "total_recursos")
    list_filter = ("tipo",)

    @admin.display(description="recursos")
    def total_recursos(self, obj):
        return obj.recursos.count()


@admin.register(Recurso)
class RecursoAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "unidade", "ativo")
    list_filter = ("tipo", "unidade", "ativo")
    search_fields = ("nome",)


class RequisitoInline(admin.TabularInline):
    model = RequisitoProcedimento
    extra = 1
    fields = (
        "recurso", "obrigatorio", "tempo_ocupacao_min", "tempo_setup_min",
        "data_inicial", "data_final", "hora_inicio", "hora_fim",
    )
    show_change_link = True  # os dias da semana ficam na página do requisito


class DiaDisponibilidadeInline(admin.TabularInline):
    model = DiaDisponibilidade
    extra = 1


@admin.register(RequisitoProcedimento)
class RequisitoProcedimentoAdmin(admin.ModelAdmin):
    """Disponibilidade de cada recurso para cada procedimento (MED001)."""

    list_display = (
        "tipo_procedimento", "recurso", "tempo_ocupacao_min", "data_inicial", "data_final",
        "hora_inicio", "hora_fim", "lista_dias",
    )
    list_filter = ("tipo_procedimento__modalidade", "recurso__unidade")
    inlines = [DiaDisponibilidadeInline]

    @admin.display(description="dias")
    def lista_dias(self, obj):
        return ", ".join(d.get_dia_semana_display()[:3] for d in obj.dias.all()) or "-"


@admin.register(TipoProcedimento)
class TipoProcedimentoAdmin(admin.ModelAdmin):
    list_display = ("nome", "modalidade", "especialidade", "duracao_padrao_min", "exige_preparo")
    list_filter = ("modalidade", "especialidade", "exige_preparo")
    search_fields = ("nome",)
    inlines = [RequisitoInline]


@admin.register(SolicitacaoProcedimento)
class SolicitacaoAdmin(admin.ModelAdmin):
    list_display = (
        "tipo_procedimento", "paciente", "medico", "prioridade", "status", "aprovada", "criada_em",
    )
    list_filter = ("status", "aprovada", "prioridade", "tipo_procedimento__modalidade")
    search_fields = (
        "agendamento_origem__paciente__usuario__first_name",
        "agendamento_origem__paciente__usuario__last_name",
    )
    raw_id_fields = ("agendamento_origem",)


class AlocacaoInline(admin.TabularInline):
    model = AlocacaoRecurso
    extra = 0
    fields = (
        "recurso",
        "papel",
        "inicio_planejado",
        "fim_planejado",
        "inicio_realizado",
        "fim_realizado",
        "status",
    )


@admin.register(Agendamento)
class AgendamentoAdmin(admin.ModelAdmin):
    list_display = (
        "tipo_procedimento",
        "paciente",
        "inicio_planejado",
        "status",
        "prontuario_liberado",
        "prontuario_acessado_em",
        "planejado_min",
        "realizado_min",
        "atraso_min",
    )
    list_filter = ("status", "tipo_procedimento__modalidade", "tipo_procedimento")
    search_fields = ("paciente__usuario__first_name", "paciente__usuario__last_name")
    date_hierarchy = "inicio_planejado"
    inlines = [AlocacaoInline]

    @admin.display(description="planejado (min)")
    def planejado_min(self, obj):
        return obj.duracao_planejada_min

    @admin.display(description="realizado (min)")
    def realizado_min(self, obj):
        return obj.duracao_realizada_min or "—"

    @admin.display(description="atraso (min)")
    def atraso_min(self, obj):
        atraso = obj.atraso_inicio_min
        return "—" if atraso is None else atraso


@admin.register(AlocacaoRecurso)
class AlocacaoRecursoAdmin(admin.ModelAdmin):
    list_display = (
        "recurso",
        "agendamento",
        "inicio_planejado",
        "inicio_realizado",
        "fim_realizado",
        "status",
        "ociosidade",
    )
    list_filter = ("status", "recurso__tipo", "recurso__unidade")
    date_hierarchy = "inicio_planejado"

    @admin.display(description="ociosidade (min)")
    def ociosidade(self, obj):
        valor = obj.ociosidade_min
        return "—" if valor is None else valor


@admin.register(Triagem)
class TriagemAdmin(admin.ModelAdmin):
    list_display = ("agendamento", "enfermeiro", "classificacao_risco", "realizada_em")
    list_filter = ("classificacao_risco", "enfermeiro__unidade")


@admin.register(RegistroClinico)
class RegistroClinicoAdmin(admin.ModelAdmin):
    list_display = ("agendamento", "medico", "tipo", "criado_em")
    list_filter = ("tipo",)


admin.site.site_header = "SAGA: Sistema de Agendamento e Gestão Assistencial"
admin.site.site_title = "SAGA"
admin.site.index_title = "Administração"
