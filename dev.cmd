@echo off
REM Run the site with the PIOB conda env (no need to activate manually).
cd /d "%~dp0"
conda run -n PIOB python manage.py migrate --noinput
if errorlevel 1 exit /b 1
conda run -n PIOB python manage.py runserver
