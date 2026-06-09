# Import vers Google Sheets + Google Docs

## Contenu généré

| Fichier | Description |
|---------|-------------|
| `NHL_2026_Classement_Complet.csv` | Classement BPA de 324 joueurs avec notes par catégorie |
| `analyses_joueurs/` | 324 analyses individuelles (Markdown → Google Docs) |
| `data/rankings.json` | Données brutes JSON |

## Étape 1 — Google Sheet (5 min)

1. Ouvrir [Google Sheets](https://sheets.google.com) → **Nouveau**
2. **Fichier → Importer → Téléverser** → sélectionner `NHL_2026_Classement_Complet.csv`
3. Type d'import : **Remplacer la feuille actuelle**
4. Séparateur : **Virgule** | Encodage : **UTF-8**

### Mise en forme recommandée

- Ligne 1 : **Format → Alterner les couleurs**
- Colonne `Note_Globale` : tri décroissant (déjà ordonné)
- **Geler** la ligne 1 et les colonnes A-B
- Format conditionnel sur `Note_Globale` :
  - ≥ 90 : vert
  - 75–89 : jaune
  - < 75 : gris

## Étape 2 — Google Docs par joueur (bulk)

### Option A — Google Drive (recommandé)

1. Ouvrir [Google Drive](https://drive.google.com)
2. Créer un dossier : `NHL 2026 — Analyses joueurs`
3. Glisser-déposer tout le dossier `analyses_joueurs/` dans Drive
4. Sélectionner tous les `.md` → clic droit → **Ouvrir avec → Google Docs**
   - Google convertit automatiquement Markdown en Doc

### Option B — Script automatique (Google Apps Script)

Dans votre Google Sheet : **Extensions → Apps Script**, coller le contenu de `google_apps_script.gs`, exécuter `convertAllAnalysesToDocs`.

## Étape 3 — Lier les Docs au Sheet

Une fois les Docs créés dans Drive :

1. Pour chaque joueur, copier l'URL du Google Doc
2. Coller dans la colonne `Lien_Analyse_Google_Doc` du Sheet
3. Ou exécuter le script Apps Script qui met à jour les liens automatiquement

## Système de notation (BPA — position-agnostique)

| Catégorie | Poids |
|-----------|-------|
| Patinage | 12% |
| Habiletés rondelle | 14% |
| Tir | 10% |
| Vision / IQ hockey | 14% |
| Jeu défensif | 12% |
| Compétitivité / moteur | 10% |
| Outils physiques | 8% |
| Production / résultats | 10% |
| Potentiel / plafond | 6% |
| Probabilité NHL | 4% |

**Note globale /100** = somme pondérée (échelle 1–10 par catégorie).

Sources : Daily Faceoff Top 100 (mai 2026), Elite Prospects Consensus Scout Poll, NHL Central Scouting.

## Top 15 BPA actuel

Voir `NHL_2026_Classement_Complet.csv` — régénérer avec :

```powershell
python generate_draft_board.py
```
