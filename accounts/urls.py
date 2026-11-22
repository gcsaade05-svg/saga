"""Rotas de conta. Prefixo /api/v1/auth/ definido em saga/urls.py."""
from django.urls import path

from . import views

urlpatterns = [
    path("eu/", views.Eu.as_view(), name="eu"),
    path("login/", views.Entrar.as_view(), name="login"),
    path("logout/", views.Sair.as_view(), name="logout"),
    path("cadastro/", views.Cadastro.as_view(), name="cadastro"),
]
