# Como colocar o SAGA no ar

O projeto segue o caminho das aulas 3 e 4 de laboratório: **Render**, com o
Django servido pelo **Gunicorn**, os arquivos estáticos pelo **WhiteNoise** e o
banco em **PostgreSQL** (lido da variável `DATABASE_URL` pelo `dj-database-url`).
Um único serviço web responde a API em `/api/v1/` e entrega o React já
compilado nas outras rotas. O arquivo `render.yaml` cria o serviço e o banco.

Tempo estimado: 20 minutos na primeira vez.

## O que já está pronto no projeto

| Arquivo | Para que serve |
|---|---|
| `render.yaml` | Cria o serviço web e o banco PostgreSQL no Render |
| `build.sh` | Instala, compila o React, junta os estáticos, roda o `migrate`, cria o superusuário e popula o banco vazio |
| `saga/settings.py` | Lê a chave secreta, o modo de produção e o `DATABASE_URL` do ambiente |
| `requirements.txt` | Inclui `gunicorn`, `whitenoise`, `dj-database-url` e `psycopg2-binary` |

Nada disso muda o jeito de rodar no seu PC: o `iniciar.bat` continua igual.

## Passo a passo

### 1. Subir o código para o GitHub

1. Crie uma conta em <https://github.com> (se ainda não tiver).
2. Crie um repositório novo, por exemplo `saga-pmr3304`. Pode ser privado.
3. Instale o [GitHub Desktop](https://desktop.github.com), entre na sua conta e
   use **File > Add local repository** apontando para a pasta do projeto. Se
   ele disser que a pasta não é um repositório, clique em **create a repository**.
4. Confira que `venv`, `node_modules` e `db.sqlite3` **não** aparecem na lista
   de arquivos (o `.gitignore` já exclui). Faça o commit e clique em **Publish**.

### 2. Criar o serviço no Render

1. Crie uma conta em <https://render.com> entrando com o GitHub.
2. No painel, clique em **New > Blueprint** e escolha o repositório do SAGA.
3. O Render lê o `render.yaml` e mostra o serviço `saga-pmr3304` e o banco
   `saga-db`. Ele pede a senha do superusuário (`DJANGO_SUPERUSER_PASSWORD`);
   o usuário é `admin`. Clique em **Apply**. A chave secreta é gerada sozinha.
4. Espere o primeiro build (uns 5 minutos). Quando aparecer **Live**, o
   endereço fica no topo da página, algo como `https://saga-pmr3304.onrender.com`.

### 3. Testar

Abra o endereço e entre com uma das contas de demonstração (os botões na tela
de entrada preenchem usuário e senha).

## Coisas que é bom saber

- **Primeiro acesso lento.** No plano gratuito o serviço dorme depois de 15
  minutos sem uso e leva cerca de um minuto para acordar. Antes de apresentar,
  abra o site uma vez para ele acordar.
- **Os dados ficam guardados** no PostgreSQL entre um deploy e outro. Como
  a agenda de demonstração é gerada a partir do dia do primeiro deploy, antes
  de apresentar vale recriá-la: em **Environment**, defina
  `SAGA_RECRIAR_DADOS=1`, faça **Manual Deploy** e depois volte para `0`.
- **Banco gratuito tem prazo.** O PostgreSQL do plano gratuito do Render
  expira depois de um tempo; confira a data no painel do banco e, se
  precisar, crie outro e faça um novo deploy.
- **Atualizar o site.** Cada commit enviado ao GitHub dispara um novo deploy
  automático.
- **Se o build falhar**, a aba **Logs** do serviço mostra a linha do erro.
  O mais comum é esquecer de enviar a pasta `frontend/src` ou o
  `frontend/package-lock.json`.

## Testar o modo de produção no próprio PC (opcional)

No Windows o `gunicorn` não roda, mas dá para conferir o build do React
servido pelo Django:

```bat
cd frontend
npm run build
cd ..
set SAGA_DEBUG=0
set SAGA_SECRET_KEY=qualquer-texto-longo-so-para-teste-local-1234567890
venv\Scripts\python manage.py collectstatic --no-input
venv\Scripts\python manage.py runserver --insecure
```

Abra <http://localhost:8000>. Feche o terminal depois para voltar ao modo normal.
