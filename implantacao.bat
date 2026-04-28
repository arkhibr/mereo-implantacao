@echo off
REM Wrapper do CLI de implantacao (Windows).
REM
REM Usa o python do .venv local quando existir. Caso contrario, usa o
REM python do PATH. O carregamento do .env e feito pelo proprio cli.py.

setlocal
set "DIR=%~dp0"

if exist "%DIR%.venv\Scripts\python.exe" (
    "%DIR%.venv\Scripts\python.exe" "%DIR%cli.py" %*
    exit /b %ERRORLEVEL%
)

python "%DIR%cli.py" %*
exit /b %ERRORLEVEL%
