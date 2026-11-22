"""
AUT001 e AUT002 com o sistema de autenticação do Django (aula 5).

O login usa django.contrib.auth.login: o Django grava a sessão no banco
(tabela django_session) e manda ao navegador só a chave, no cookie
sessionid. O logout é por POST, como na aula. O React recebe o cookie
csrftoken e o devolve no cabeçalho X-CSRFToken em todo POST.
"""
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Usuario

from .serializers import CadastroPacienteSerializer, UsuarioSerializer

MENSAGEM_LOGIN = "Usuário ou senha inválidos."  # RN20: sempre a mesma
TENTATIVAS, BLOQUEIO_MIN = 5, 15


@method_decorator(ensure_csrf_cookie, name="dispatch")
class Eu(APIView):
    """Quem está logado nesta sessão. Também entrega o cookie csrftoken ao React."""

    permission_classes = [AllowAny]

    def get(self, request):
        u = request.user
        return Response({"usuario": UsuarioSerializer(u).data if u.is_authenticated else None})


class Entrar(APIView):
    """AUT001. Bloqueia por 15 minutos após 5 falhas seguidas do mesmo usuário."""

    permission_classes = [AllowAny]

    def post(self, request):
        username = (request.data.get("username") or "").strip().lower()
        senha = request.data.get("senha") or request.data.get("password") or ""
        chave = f"login-falhas:{username}"
        if cache.get(chave, 0) >= TENTATIVAS:
            return Response(
                {"detail": f"Muitas tentativas. Tente de novo em {BLOQUEIO_MIN} minutos."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        usuario = Usuario.objects.filter(username__iexact=username).first()
        if usuario is not None and not usuario.is_active and usuario.check_password(senha):
            return Response(
                {"detail": "Conta inativa. Procure a administração do hospital."},
                status=status.HTTP_403_FORBIDDEN,
            )
        autenticado = authenticate(
            request, username=usuario.username if usuario else username, password=senha
        )
        if autenticado is None:
            cache.set(chave, cache.get(chave, 0) + 1, BLOQUEIO_MIN * 60)
            return Response({"detail": MENSAGEM_LOGIN}, status=status.HTTP_401_UNAUTHORIZED)
        cache.delete(chave)
        login(request, autenticado)  # cria a sessão e envia o cookie sessionid
        return Response({"usuario": UsuarioSerializer(autenticado).data})


class Sair(APIView):
    """Logout por POST (com GET o Django responde 405, como visto na aula)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class Cadastro(generics.CreateAPIView):
    """AUT002. Cria o paciente, coloca no grupo Paciente e já entra no sistema."""

    serializer_class = CadastroPacienteSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = serializer.save()
        login(request, usuario, backend="django.contrib.auth.backends.ModelBackend")
        return Response({"usuario": UsuarioSerializer(usuario).data}, status=status.HTTP_201_CREATED)
