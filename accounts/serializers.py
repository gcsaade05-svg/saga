"""Serializadores de conta: usuário logado e cadastro de paciente (AUT002)."""
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from core.models import Paciente, Usuario
from core.utils import cpf_valido, formatar_cpf


# ---------------------------------------------------------------------------
# Usuário e cadastro (AUT001, AUT002)
# ---------------------------------------------------------------------------
class UsuarioSerializer(serializers.ModelSerializer):
    nome = serializers.SerializerMethodField()
    perfil_nome = serializers.CharField(source="get_perfil_display", read_only=True)
    unidade = serializers.SerializerMethodField()
    grupos = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ["id", "username", "nome", "email", "perfil", "perfil_nome", "grupos", "unidade"]

    def get_nome(self, obj):
        return obj.get_full_name() or obj.username

    def get_grupos(self, obj):
        return list(obj.groups.values_list("name", flat=True))

    def get_unidade(self, obj):
        if obj.perfil == Usuario.Perfil.ENFERMEIRO and hasattr(obj, "enfermeiro"):
            u = obj.enfermeiro.unidade
            return {"id": u.id, "nome": u.nome}
        return None


class CadastroPacienteSerializer(serializers.Serializer):
    nome_completo = serializers.CharField(max_length=200)
    cpf = serializers.CharField(max_length=14)
    data_nascimento = serializers.DateField()
    email = serializers.EmailField(max_length=254)
    telefone = serializers.RegexField(r"^[\d\s()\-]{8,20}$", max_length=20)
    cartao_sus = serializers.RegexField(r"^\d*$", max_length=20, required=False, allow_blank=True)
    username = serializers.RegexField(r"^[\w.\-]+$", max_length=150)
    senha = serializers.CharField(write_only=True, max_length=128)
    confirmar_senha = serializers.CharField(write_only=True, max_length=128)

    def validate_nome_completo(self, valor):
        if len(valor.split()) < 2:
            raise serializers.ValidationError("Informe nome e sobrenome.")
        return valor.strip()

    def validate_cpf(self, valor):
        if not cpf_valido(valor):
            raise serializers.ValidationError("CPF inválido.")
        valor = formatar_cpf(valor)
        if Paciente.objects.filter(cpf=valor).exists():
            raise serializers.ValidationError("Já existe um cadastro com este CPF.")
        return valor

    def validate_data_nascimento(self, valor):
        hoje = timezone.localdate()
        if valor > hoje or (hoje - valor).days > 120 * 366:
            raise serializers.ValidationError("Data de nascimento fora do intervalo válido.")
        return valor

    def validate_email(self, valor):
        if Usuario.objects.filter(email__iexact=valor).exists():
            raise serializers.ValidationError("E-mail já cadastrado.")
        return valor.lower()

    def validate_username(self, valor):
        if Usuario.objects.filter(username__iexact=valor).exists():
            raise serializers.ValidationError("Nome de usuário indisponível.")
        return valor.lower()

    def validate(self, dados):
        if dados["senha"] != dados["confirmar_senha"]:
            raise serializers.ValidationError({"confirmar_senha": "As senhas não coincidem."})
        partes = dados["nome_completo"].split()
        provisorio = Usuario(
            username=dados["username"], first_name=partes[0], last_name=partes[-1], email=dados["email"]
        )
        try:
            validate_password(dados["senha"], provisorio)
        except Exception as erro:  # ValidationError do Django
            raise serializers.ValidationError({"senha": list(erro.messages)})
        return dados

    @transaction.atomic
    def create(self, dados):
        partes = dados["nome_completo"].split()
        usuario = Usuario(
            username=dados["username"],
            first_name=partes[0],
            last_name=" ".join(partes[1:]),
            email=dados["email"],
            telefone=dados["telefone"],
            perfil=Usuario.Perfil.PACIENTE,
        )
        usuario.set_password(dados["senha"])  # RN19: só o resumo criptográfico é gravado
        usuario.save()  # o sinal de accounts/sinais.py coloca o usuário no grupo Paciente
        Paciente.objects.create(
            usuario=usuario,
            cpf=dados["cpf"],
            data_nascimento=dados["data_nascimento"],
            cartao_sus=dados.get("cartao_sus", ""),
        )
        return usuario
