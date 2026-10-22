@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ===========================================
echo       POLARA - локальный поисковый прототип
echo ===========================================
echo.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 server.py
  goto end
)
where python >nul 2>nul
if %errorlevel%==0 (
  python server.py
  goto end
)
echo Python не найден. Установи Python с https://www.python.org/downloads/windows/
echo При установке отметь Add Python to PATH, затем нажми Install Now.
echo После установки закрой это окно и снова запусти start.bat.
pause
:end
echo.
echo Сервер остановлен. Нажми любую клавишу, чтобы закрыть окно.
pause >nul
