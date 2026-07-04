# 🗺️ La démarche, rangée par étapes

Point d'entrée unique pour l'équipe. On construit **par-dessus un moteur existant
qu'on ne modifie pas** ; notre travail est découpé en **étapes**, une par dossier.

```
demarche/
├── README.md                 ← cette carte
│
├── etape_1_comprendre/       ← ÉTAPE 1 : comprendre l'existant (aucun code, que de la doc)
│   └── COMPRENDRE.md            le moteur expliqué : modules, flux d'une question,
│                                champs réels d'AskResult, statuts, phrase de pitch,
│                                écarts cahier ↔ réel.
│
├── etape_2_front/            ← ÉTAPE 2 : le front de chat futuriste (NOTRE code)
│   ├── presentation.py         couche « à nous » : statut moteur → score 0-100 + couleur
│   ├── server.py               backend /ask + /resolve (réutilise le moteur, l'enrichit)
│   ├── static/                 le front (chat, jauges, panneau de traçabilité)
│   │   ├── index.html
│   │   ├── style.css
│   │   └── app.js
│   └── README.md               doc détaillée de l'étape 2
│
└── suivi/
    └── BLOCAGES.md           ← SUIVI : ce qui reste à faire / décisions humaines
```

## L'existant (non déplacé, à la racine)

Le moteur reçu **reste à la racine** : c'est la base sur laquelle on construit, pas
une étape qu'on a produite. Le déplacer casserait ses imports et sa logique `.env`
(et le cahier interdit d'y toucher).

| À la racine | Rôle |
|---|---|
| `src/sentinel_guard/` | le moteur de vérification déterministe |
| `tests/` | 175 tests (`python -m pytest`) |
| `examples/` | scripts de démonstration par brique |
| `ui/` | démonstrateur web historique (fallback, intact) |
| `README.md` | présentation du moteur |
| `STATUS.md` | état d'avancement section par section |
| `sentinel-guard-spec-v4.md` | la spécification complète |
| `ANALYSE_TEST_JURISPRUDENCE.md` | analyse d'un test réel (cité par le code du moteur) |

## Par où commencer (demain, cerveau frais)

1. **Installer + tester** (5 min) :
   ```bash
   python -m venv .venv
   # Windows : .venv\Scripts\Activate.ps1   |  Linux/mac : source .venv/bin/activate
   python -m pip install -e ".[test]"
   python -m pytest -q                          # attendu : 175 passed
   ```
2. **Lire** [`etape_1_comprendre/COMPRENDRE.md`](etape_1_comprendre/COMPRENDRE.md)
   pour comprendre et pouvoir **défendre** le projet au pitch.
3. **Lancer le front** (nécessite `MISTRAL_API_KEY` dans `.env` à la racine) :
   ```bash
   python -m demarche.etape_2_front.server        # http://localhost:8770
   ```
4. **Regarder** [`suivi/BLOCAGES.md`](suivi/BLOCAGES.md) : les points à finir.

## Pourquoi le code de l'étape 2 est un package Python

`etape_2_front/` est un **package** (`__init__.py`) : on le lance avec
`python -m demarche.etape_2_front.server` (noms de dossiers en `snake_case`, sans
tiret, pour rester des identifiants Python valides). Le serveur retrouve la racine
du dépôt tout seul (recherche du `pyproject.toml`), donc il lit bien le `.env` et le
moteur `src/` quel que soit l'endroit d'où on le lance.
