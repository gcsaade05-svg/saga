@echo off
rem SAGA: prepara e abre o sistema no Windows. Pode rodar quantas vezes quiser.
rem Primeira vez: demora alguns minutos (instala dependencias). Depois: segundos.
chcp 65001 >nul
cd /d "%~dp0"
title SAGA - preparando

rem Rodar de dentro do zip (WinRAR ou Windows abrem numa pasta temporaria) nao funciona:
rem o ambiente Python fica pela metade e some quando a janela fecha.
echo "%~dp0" | findstr /i /c:"\Temp\" /c:"rartemp" /c:".zip\" >nul && (
  echo [ERRO] O SAGA esta sendo aberto de dentro do arquivo .zip.
  echo        Clique com o botao direito no zip, escolha "Extrair tudo" ^(ou "Extrair aqui"^),
  echo        abra a pasta SAGA extraida e rode o iniciar.bat de la.
  pause & exit /b 1
)

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul || (
  echo [ERRO] Python 3.10 ou mais novo nao encontrado. Instale em https://www.python.org/downloads/
  echo        e marque "Add python.exe to PATH" na primeira tela do instalador.
  echo        Depois feche esta janela e rode o iniciar.bat de novo.
  pause & exit /b 1
)
where npm >nul 2>nul || (
  echo [ERRO] Node.js nao encontrado. Instale a versao LTS em https://nodejs.org
  pause & exit /b 1
)

if not exist venv (
  echo [1/4] Criando ambiente Python...
  python -m venv venv || (echo [ERRO] Falha ao criar o venv & pause & exit /b 1)
)
echo [2/4] Instalando dependencias do Python...
venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements.txt || (echo [ERRO] pip install falhou & pause & exit /b 1)
rem Se o venv veio quebrado (por exemplo, copiado de outra pasta), recria uma vez.
venv\Scripts\python -c "import django, rest_framework" >nul 2>nul || (
  echo Ambiente Python incompleto. Recriando...
  rmdir /s /q venv
  python -m venv venv || (echo [ERRO] Falha ao criar o venv & pause & exit /b 1)
  venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements.txt || (echo [ERRO] pip install falhou & pause & exit /b 1)
)

echo [3/4] Preparando o banco de dados...
venv\Scripts\python manage.py migrate -v 0 || (echo [ERRO] migrate falhou & pause & exit /b 1)
venv\Scripts\python manage.py seed

rem Confere o sass (usado pelo estilo.scss) para reinstalar em pastas de versoes anteriores.
if not exist frontend\node_modules\sass (
  echo [4/4] Instalando dependencias do front-end ^(so na primeira vez^)...
  pushd frontend & call npm install --no-audit --no-fund & popd
) else (
  echo [4/4] Dependencias do front-end ja instaladas.
)

echo.
echo Abrindo duas janelas: a API ^(porta 8000^) e o site ^(porta 5173^).
echo Para encerrar o SAGA, feche as duas janelas.
start "SAGA - API (nao feche)" cmd /k venv\Scripts\python manage.py runserver
start "SAGA - Site (nao feche)" cmd /k "cd frontend && npm run dev"
timeout /t 6 /nobreak >nul
start "" http://localhost:5173
echo.
echo Pronto. Se o navegador abriu antes do site subir, aperte F5.
echo Usuarios: ana.ribeiro, helena.vasconcelos, fernanda.rocha  ^|  senha: saga1234
pause
