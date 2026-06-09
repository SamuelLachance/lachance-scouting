# Lachance Scouting

Repêchages NHL — classement NORTHSTAR (Star Probability Index), repêchage par repêchage à partir de 2026.

## Site en ligne

Après publication sur GitHub Pages :

**https://VOTRE-UTILISATEUR.github.io/lachance-scouting/**

(Remplacez `VOTRE-UTILISATEUR` et le nom du repo si différent.)

## Publier / partager

Double-cliquez **`publier-github.bat`** ou :

```powershell
gh auth login
gh repo create lachance-scouting --public --source=. --remote=origin --push
```

Le workflow `.github/workflows/pages.yml` déploie automatiquement le dossier `site/` à chaque push sur `main`.

## Développement local

```powershell
python build_site_data.py
start.bat
```

Ouvrir http://localhost:8080

## Mettre à jour le classement

```powershell
python scripts/fetch_scouting_reports.py
python generate_draft_board.py
python build_site_data.py
git add .
git commit -m "Mise à jour classement"
git push
```
