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

echo.
echo  Si le push echoue sur .github/workflows/pages.yml :
echo    gh auth refresh -h github.com -s workflow
echo  ^(ouvre le navigateur pour confirmer les droits^)
echo.

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

set "GH_USER="
for /f "delims=" %%u in ('gh api user --jq .login 2^>nul') do set "GH_USER=%%u"
if not defined GH_USER for /f "tokens=1 delims=/" %%u in ('gh repo view --json nameWithOwner -q .nameWithOwner 2^>nul') do set "GH_USER=%%u"
if not defined GH_USER (
  echo Impossible de determiner votre identifiant GitHub. Lancez: gh auth login
  pause
  exit /b 1
)

gh api repos/%GH_USER%/%REPO_NAME%/pages >nul 2>&1
if errorlevel 1 (
  echo Activation GitHub Pages ^(premiere fois^)...
  gh api -X POST repos/%GH_USER%/%REPO_NAME%/pages -f build_type=workflow -f "source[branch]=main" -f "source[path]=/" >nul 2>&1
)

echo.
echo  URL a partager ^(PAS la page d'accueil du compte^) :
echo  https://%GH_USER%.github.io/%REPO_NAME%/
echo.
echo  https://%GH_USER%.github.io/ seul = 404 tant qu'il n'y a pas de repo USER.github.io
echo.
echo  Si besoin: GitHub ^> Settings ^> Pages ^> Source = GitHub Actions
echo.
pause
