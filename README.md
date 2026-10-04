# KukuTrack

KukuTrack est une petite application locale pour suivre un lot de poulets de chair.
Elle aide à enregistrer les informations du lot et ses rappels au fil des jours.
Elle est pensée pour rester utilisable sans connexion Internet.

## Installation

```bash
pip install -r requirements.txt
```

## Lancer l'application

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Ouvrez ensuite `http://127.0.0.1:8000` sur l'ordinateur.

## Ouvrir depuis un téléphone sur le même Wi-Fi

Lancez l'application avec la commande ci-dessus, puis trouvez l'adresse IP locale
de l'ordinateur (par exemple `192.168.1.25`). Sur le téléphone connecté au même
Wi-Fi, ouvrez `http://192.168.1.25:8000`. Vous pourrez ensuite choisir
« Ajouter à l'écran d'accueil » dans le navigateur.

## Vérifications

```bash
pytest
ruff check .
```

## Données de démonstration

Pour remplir une base avec un lot **entièrement fictif** nommé `DEMO (fake data)` :

```bash
python scripts/seed_demo.py
```

La commande refuse de créer un second lot DEMO. Pour supprimer uniquement ce lot
DEMO puis le recréer, utilisez `python scripts/seed_demo.py --reset`. Vous pouvez
aussi cibler une autre base avec `python scripts/seed_demo.py --db chemin/vers/demo.db`.
