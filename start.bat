@echo off
cd /d "%~dp0"
echo Generation des donnees...
python build_site_data.py
if errorlevel 1 pause & exit /b 1
cd siteecho.
echo ========================================
echo  Lachance Scouting — NHL 2026 Draft
echo  Ouvrez: http://localhost:8080
echo ========================================
echo.
start "" "http://localhost:8080"
python -m http.server 8080
