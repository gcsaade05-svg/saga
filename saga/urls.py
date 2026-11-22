from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, Http404
from django.urls import include, path, re_path


def spa(request):
    """Entrega o index.html do React para qualquer rota que não seja da API.

    Só existe depois de `npm run build`; em desenvolvimento quem serve o
    front-end é o Vite, na porta 5173.
    """
    indice = settings.FRONTEND_DIST / "index.html"
    if not indice.exists():
        raise Http404("Front-end não compilado. Rode `npm run build` em frontend/.")
    return FileResponse(open(indice, "rb"), content_type="text/html")


urlpatterns = [
    path("admin/", admin.site.urls),
    # API REST (aula 5): versão 1 em /api/v1/; contas em /api/v1/auth/.
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/", include("api.urls")),
    # Login da API navegável do DRF, para testar no navegador como na aula.
    path("api-auth/", include("rest_framework.urls")),
    re_path(r"^(?!api/|api-auth/|admin/|static/).*$", spa),
]
