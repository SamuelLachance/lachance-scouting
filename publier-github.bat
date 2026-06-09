@echo off
cd /d "%~dp0"
echo.
echo  ========================================
echo   Lachance Scouting - Publication GitHub
echo  ========================================
echo.

where gh >nul 2>&1
if errorlevel 1 (
  echo Installez GitHub CLI: https://cli.github.com/
  echo Puis relancez ce script.
  pause
  exit /b 1
)

gh auth status >nul 2>&1
if errorlevel 1 (
  echo Connexion GitHub requise...
  gh auth login
)

if not exist .git (
  git init -b main
)

git add .
git -c user.name="Lachance Scouting" -c user.email="noreply@users.noreply.github.com" commit -m "Mise a jour Lachance Scouting" 2>nul

set /p REPO_NAME="Nom du repo GitHub (ex: lachance-scouting): "
if "%REPO_NAME%"=="" set REPO_NAME=lachance-scouting

git remote get-url origin >nul 2>&1
if errorlevel 1 (
  gh repo create %REPO_NAME% --public --source=. --remote=origin --push
) else (
  git push -u origin main
)

for /f "delim=" %%u in ('gh api user -q .login 2^>nul') do set GH_USER=%%u

echo.
echo  Site en ligne sous 1 a 2 minutes:
echo  https://%GH_USER%.github.io/%REPO_NAME%/
echo.
echo  Si besoin: GitHub ^> Settings ^> Pages ^> Source = GitHub Actions
echo.
pause
