@echo off
rem Apaga os dados e gera de novo a base sintetica, com datas a partir de hoje.
rem Use antes de uma apresentacao, para a agenda do dia estar cheia.
chcp 65001 >nul
cd /d "%~dp0"
if not exist venv ( echo Rode o iniciar.bat primeiro. & pause & exit /b 1 )
echo Isto apaga tudo o que foi cadastrado no SAGA local e recria os dados de demonstracao.
choice /m "Continuar"
if errorlevel 2 exit /b 0
venv\Scripts\python manage.py migrate -v 0
venv\Scripts\python manage.py seed --limpar
pause
