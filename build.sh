#!/usr/bin/env bash
# Build da publicação no Render (aula 3 e aula 4, "Implantando no Render"):
# instala, compila o React, junta os estáticos, migra o PostgreSQL e cria o
# superusuário a partir das variáveis DJANGO_SUPERUSER_*.
set -o errexit
pip install -r requirements.txt
(cd frontend && npm ci --no-audit --no-fund && npm run build)
python manage.py collectstatic --no-input
python manage.py migrate --no-input
# Na primeira vez cria o superusuário; nas próximas ele já existe, e tudo bem.
python manage.py createsuperuser --no-input || true
# Popula com dados sintéticos só se o banco estiver vazio. Para recomeçar a
# demonstração com a agenda a partir de hoje, defina SAGA_RECRIAR_DADOS=1 no
# Render e faça um novo deploy (depois volte para 0).
if [ "${SAGA_RECRIAR_DADOS:-0}" = "1" ]; then
  python manage.py seed --limpar
else
  python manage.py seed
fi
