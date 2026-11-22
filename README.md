# SAGA: Sistema de Agendamento e Gestão Assistencial

Trabalho aplicado de **PMR3304 Sistemas de Informação 2026**, Escola Politécnica da USP.

Sistema de gestão da agenda assistencial de um hospital: consultas, exames e
cirurgias disputando as mesmas salas e equipamentos e a agenda dos médicos.

- **Back-end:** Django 5 + Django REST Framework, autenticação por sessão do Django, grupos e permissões
- **Front-end:** React (Vite), consumindo a API
- **Banco:** SQLite no computador e PostgreSQL na publicação (Render), populado só com dados sintéticos

---

## Como rodar

### Jeito rápido (Windows)

1. Instale o [Python](https://www.python.org/downloads/) (marque **Add python.exe to PATH**)
   e o [Node.js LTS](https://nodejs.org).
2. Dê dois cliques em **`iniciar.bat`**. Na primeira vez ele instala tudo
   (alguns minutos); depois abre a API, o site e o navegador sozinho.
3. Antes de uma apresentação, rode **`reiniciar_dados.bat`** para recriar os
   dados de demonstração com a agenda a partir de hoje.

Para publicar na internet, veja [PUBLICAR.md](PUBLICAR.md).

### Passo a passo manual

São dois processos: a API (porta 8000) e o front-end (porta 5173).

#### 1. API

```bash
python -m venv venv
venv\Scripts\activate            # Windows  (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py seed            # dados sintéticos (use --limpar para recomeçar)
python manage.py runserver
```

#### 2. Front-end (outro terminal)

Precisa do [Node.js](https://nodejs.org) 20 ou mais recente.

```bash
cd frontend
npm install
npm run dev
```

Abra <http://localhost:5173>. O Vite repassa as chamadas `/api` para o Django.

### Usuários de demonstração

Todos com senha **`saga1234`**. Na tela de entrada, os botões de
demonstração preenchem usuário e senha.

| Perfil | Usuário | Tela inicial |
|---|---|---|
| Paciente | `ana.ribeiro` | Meus agendamentos |
| Médica | `helena.vasconcelos` | Minha agenda |
| Enfermeira | `fernanda.rocha` (Centro Cirúrgico A) | Ocupação de recursos |

A interface administrativa do Django continua em <http://127.0.0.1:8000/admin/>
(crie um usuário com `python manage.py createsuperuser`). É por ela que se
mantém o catálogo institucional, fora do escopo dos casos de uso.

### Testes

```bash
python manage.py test core
```

---

## As 18 telas

Cada tela do documento de Casos de Uso tem sua própria página no site.

| # | Tela do documento | Endereço | Endpoint principal |
|---|---|---|---|
| 1 | AUT001 Autenticação | `/entrar` | `POST /api/v1/auth/login/` |
| 2 | AUT002 Cadastro de paciente | `/cadastro` | `POST /api/v1/auth/cadastro/` |
| 3 | PAC001 Busca de horários | `/paciente/agendar` | `GET /api/v1/janelas/`, `POST /api/v1/agendamentos/` |
| 4 | PAC001 Resumo do agendamento | `/paciente/agendamentos/{id}` | `GET /api/v1/agendamentos/{id}/` |
| 5 | PAC002 Meus agendamentos e confirmação | `/paciente/agendamentos` | `POST /api/v1/agendamentos/{id}/confirmar/` |
| 6 | PAC003 Cancelar ou remarcar | `/paciente/agendamentos/{id}/alterar` | `POST /api/v1/agendamentos/{id}/cancelar/` e `.../remarcar/` |
| 7 | PAC004 Solicitações e resultados | `/paciente/solicitacoes` | `GET /api/v1/solicitacoes/`, `GET /api/v1/resultados/` |
| 8 | Minha agenda (médico) | `/medico/agenda` | `GET /api/v1/agendamentos/?data=` |
| 9 | MED001 Disponibilidade para consultas | `/medico/disponibilidade` | `GET/POST /api/v1/disponibilidades/` |
| 10 | MED002 Registro de atendimento | `/medico/atendimento/{id}` | `POST .../atendimento/` |
| 11 | MED003 Solicitar exame ou cirurgia | `/medico/atendimento/{id}/solicitar` | `POST /api/v1/solicitacoes/` |
| 12 | MED004 Prontuário | `/medico/prontuario/{paciente}` | `GET /api/v1/prontuario/{paciente}/` |
| 13 | Fila de triagem | `/enfermeiro/fila` | `GET /api/v1/triagem/fila/` |
| 14 | ENF001 Triagem | `/enfermeiro/triagem/{id}` | `POST /api/v1/triagens/` |
| 15 | ENF002 Ocupação de recursos | `/enfermeiro/ocupacao` | `POST /api/v1/alocacoes/{id}/abrir/` e `/encerrar/` |
| 16 | ENF003 Recursos da unidade | `/enfermeiro/recursos` | `GET/POST/PATCH /api/v1/recursos/` |
| 17 | ENF004 Painel de Ocupação e encaixe | `/enfermeiro/painel` | `GET /api/v1/painel/`, `POST /api/v1/encaixe/` |
| 18 | Aprovar solicitações (uso de recursos) | `/enfermeiro/aprovacoes` | `POST /api/v1/solicitacoes/{id}/aprovar/` e `/recusar/` |

As regras de negócio ficam em `core/servicos.py` e são as mesmas usadas pelo
`seed` e pelos testes. Exemplo: um agendamento só é criado se sala e
equipamento estiverem dentro da disponibilidade publicada e livres juntos
(RN02), e se houver um médico habilitado livre no horário (RN03); a verificação
é refeita dentro da transação para o caso de dois pacientes clicarem no mesmo
horário.

---

## Diagrama Entidade Relação

A entrega do DER está na raiz da pasta:

- `DER_SAGA_PMR3304.pdf`: documento com diagrama de classes, DER conceitual e
  físico, normalização e dicionário de dados
- `SAGA_DER.xml`: o modelo no formato do DBDesigner 4

Os dois são gerados a partir de `core/models.py`, então nunca divergem do
banco. Para regenerar depois de mudar o modelo:

```bash
python docs/der/modelo.py        # extrai tabelas e relações
python docs/der/diagramas.py     # desenha (precisa do Graphviz)
python docs/der/dbdesigner.py    # gera o XML do DBDesigner
bash docs/der/montar_documento.sh  # monta o docx e o PDF (Node, LibreOffice)
```

---

## Modelagem em uma frase

Sala e equipamento são um único conceito, **Recurso** (só coisas físicas do
hospital); a alocação de recurso guarda na mesma linha a janela planejada e a
realizada, e é dessa diferença que sai o Painel de Ocupação.

### Mudanças do DER v1.2 (entrega final)

| Pedido | Como ficou no sistema |
|---|---|
| Acesso ao prontuário como atributo do agendamento | `Agendamento.prontuario_liberado` e `prontuario_acessado_em`; a tabela `AcessoProntuario` saiu. O médico só abre o prontuário com um agendamento seu, ativo e liberado (RN13), e o instante do acesso fica gravado nele (RN14). |
| Médico e paciente da solicitação vêm do agendamento | `SolicitacaoProcedimento.agendamento_origem`; `medico_id` e `paciente_id` saíram. |
| Solicitação aprovada para uso do recurso | `aprovada` e `aprovada_em`; a solicitação nasce "Aguardando aprovação", a enfermagem aprova na tela nova e só então ela entra na fila e pode ser encaixada. |
| Disponibilidade no requisito do procedimento | `RequisitoProcedimento` ganhou período e horário, e os dias da semana ficam em `DiaDisponibilidade`; `BlocoDisponibilidade` saiu. O agendamento aponta para o requisito usado. |
| Recurso só como coisa física | Tipo `Profissional` e `Medico.recurso` saíram. A agenda do médico é checada pelos agendamentos de que ele é responsável (RN03). |

A migração `0003` apaga os dados sintéticos antigos, que não têm conversão
direta, e o `seed` recria a base no modelo novo (o `iniciar.bat` já faz isso).

---

## Estrutura

```
sis info/
├── manage.py, requirements.txt
├── iniciar.bat, reiniciar_dados.bat   rodar no Windows
├── render.yaml, build.sh, PUBLICAR.md publicação online (Render + PostgreSQL)
├── saga/                    configuração do projeto (settings, urls)
├── core/                    o domínio
│   ├── models.py            as 16 entidades do DER v1.2
│   ├── servicos.py          regras de negócio (agendar, cancelar, painel, encaixe)
│   ├── admin.py             cadastro do catálogo pelo /admin/
│   ├── utils.py             CPF, sugestão de classificação de risco
│   ├── tests.py             31 testes da API
│   └── management/commands/ seed (dados sintéticos) e ocupacao (painel no terminal)
├── accounts/                contas: login, logout e cadastro
│   ├── views.py, urls.py    /api/v1/auth/ (sessão do Django)
│   ├── serializers.py       usuário e cadastro de paciente
│   └── grupos.py, sinais.py grupos Paciente, Medico e Enfermeiro com suas permissões
├── api/                     API REST
│   ├── views.py             views genéricas do DRF (ListAPIView, ListCreateAPIView...)
│   ├── serializers.py       ModelSerializers: validação de entrada e formato de saída
│   ├── permissions.py       grupo do perfil e permissão requerida
│   └── urls.py              endpoints em /api/v1/
└── frontend/                React (Vite)
    └── src/paginas/         telas por perfil: paciente, medico, enfermeiro
```

---

## Como o projeto segue as aulas de laboratório

| Aula | O que foi ensinado | Onde está no SAGA |
|---|---|---|
| 1. Git | Repositório do grupo, commits frequentes | `.gitignore` pronto (sem `venv`, `node_modules`, banco) |
| 2. HTML e CSS | CSS em arquivo externo, seletores, pseudo-classes, caixa, Flexbox, Grid, media queries, Google Fonts, Font Awesome e Sass | `frontend/src/estilo.scss` (variáveis e aninhamento do Sass, sem estilo em linha); fontes e ícones no `<head>` de `frontend/index.html` |
| 3. HTTP e Django | Projeto e apps, `urls.py` com `include`, métodos e códigos HTTP, Render com Gunicorn e WhiteNoise | `saga/urls.py` inclui as urls de cada app; a API responde 200, 201, 400, 401, 403, 404 e 409; `render.yaml` e `build.sh` |
| 4. SQL e ORM | Models, migrações, `ForeignKey` (1 x n), `ManyToManyField` (n x n), `OneToOneField` (1 x 1), admin, `get_object_or_404`, PostgreSQL no Render com `dj-database-url` e superusuário por variável | `core/models.py`, `core/migrations/`, `core/admin.py`, `saga/settings.py`, `build.sh` |
| 5. Autenticação | Sessão e cookies, app `accounts`, login e logout por POST, `@login_required`/permissões, grupos com permissões e usuário entrando no grupo no cadastro | `accounts/`: `django.contrib.auth.login` e `logout`, grupos em `accounts/grupos.py`, sinal que põe o usuário no grupo do perfil |
| 5. REST | App `api`, `ModelSerializer`, views genéricas, rotas `/api/v1/`, permissões do DRF, Postman | `api/`: views genéricas, `IsAuthenticated` por padrão, grupo e `permission_required` por view; teste no Postman com Basic Auth |
| 6. JavaScript e React | Vite, componentes, JSX com `className`, `useState`, renderização condicional, `map` nas tabelas e `fetch` da API | `frontend/` (React com Vite). O menu do celular abre e fecha pelo estado; os dias da semana e os horários marcados trocam de `className` |

### Testar a API no Postman ou no navegador

- **Navegador:** depois de entrar no site, abra <http://localhost:8000/api/v1/agendamentos/>.
  A API navegável do DRF usa a mesma sessão. Também dá para entrar por
  <http://localhost:8000/api-auth/login/>.
- **Postman ou Thunder Client:** aba **Authorization**, tipo **Basic Auth**, com
  usuário e senha de demonstração (por exemplo `fernanda.rocha` / `saga1234`), e
  `GET http://127.0.0.1:8000/api/v1/painel/`.

---

## Próximos passos

- [ ] Rotina agendada para liberar agendamentos não confirmados (RN06, função `liberar_nao_confirmados` pronta)
- [ ] Histórico completo de acessos ao prontuário (hoje fica o último, por agendamento)

---

## Sobre os dados

O sistema manipula dados de saúde, que são dados pessoais sensíveis. Este é um
trabalho acadêmico e o banco é populado **exclusivamente com dados sintéticos**
gerados pelo comando `seed`. Os CPFs têm dígitos válidos, mas são aleatórios e
não pertencem a ninguém.
