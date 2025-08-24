# HSE Pilot (Railway-ready)

Petit outil de suivi HSE (politique HSE, risques, audits, incidents, formations, FDS, déchets, GMAO-lite, équipe/absences) — thème sombre, déployable sur Railway (Hobby).

## Lancer en local
```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export FLASK_SECRET="change-me"
python app.py
# Ouvrir http://localhost:5000
```

## Déploiement sur Railway (Hobby)
1. Créez un nouveau repo GitHub et poussez ce dossier.
2. Sur Railway: New Project → Deploy from GitHub → sélectionnez le repo.
3. Variables d'environnement à définir :
   - `FLASK_SECRET`: une valeur aléatoire
4. Railway détecte Python. Le `Procfile` lance `gunicorn app:app`.
5. Après le build, ouvrez l'URL publique.

### Notes
- Base SQLite (`hse.db`) stockée sur le disque éphémère du service. Pour de la persistance forte, utilisez un add-on Postgres et définissez `DATABASE_URL`.
- Les bibliothèques CSS/JS (Tailwind, Chart.js) sont chargées via CDN.
- Initiales utilisateur : champ en haut à droite (stocké en session).

## Modules inclus
- Tableau de bord avec KPIs & graphiques
- Plan d’action (CRUD)
- Analyse des risques (CRUD, niveau = gravité × probabilité)
- Audits (CRUD)
- Incidents / dysfonctionnements (CRUD + RCA/AC)
- Formations (CRUD)
- Fiches de Données de Sécurité (CRUD + dates de révision)
- Déchets (CRUD + agrégation kg)
- Moyens de contrôle — GMAO-lite (CRUD + dates contrôles)
- Équipe & Absences (CRUD)

## Personnalisation
- Navigation dans `templates/layout.html`
- Styles via Tailwind (thème sombre par défaut)
- Ajout de champs : modifiez le modèle dans `app.py` et les formulaires associés

Bon déploiement 🚀
