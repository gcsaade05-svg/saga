"""Tradução de erros para respostas HTTP (configurado em REST_FRAMEWORK)."""
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.response import Response
from rest_framework.views import exception_handler

from core import servicos


def tratador_de_erros(exc, contexto):
    """
    Regras de negócio violadas viram 400; janela ocupada na corrida vira 409.
    Sem login, 401 (sem o cabeçalho WWW-Authenticate, para o navegador não
    abrir a janela de senha do Basic Auth): o React volta para a tela de entrada.
    """
    if isinstance(exc, servicos.JanelaOcupada):
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
    if isinstance(exc, DjangoValidationError):
        corpo = exc.message_dict if hasattr(exc, "error_dict") else {"detail": exc.messages}
        return Response(corpo, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, NotAuthenticated):
        return Response({"detail": str(exc.detail)}, status=status.HTTP_401_UNAUTHORIZED)
    return exception_handler(exc, contexto)
