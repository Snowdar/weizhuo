@echo off
setlocal
cd /d "%~dp0.."
where py >nul 2>nul
if errorlevel 1 goto python
py -3 scripts\bootstrap.py
if errorlevel 1 goto done
py -3 weizhuo\server.py
goto done
:python
where python >nul 2>nul
if errorlevel 1 goto missing
python scripts\bootstrap.py
if errorlevel 1 goto done
python weizhuo\server.py
goto done
:missing
echo Python 3.11+ is required. See README.md for installation.
:done
pause
endlocal
