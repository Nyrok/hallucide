# webapp/ — interface de chat futuriste (couche de présentation)

Interface web moderne branchée sur le moteur Sentinel Guard. **Le moteur
(`src/sentinel_guard/`) et le démonstrateur historique (`ui/`) ne sont pas
modifiés** : cette couche les *consomme*, elle ne les remplace pas.

> À lire d'abord : [`../COMPRENDRE.md`](../COMPRENDRE.md) (comprendre le moteur).

## Lancer

```bash
# depuis la racine, environnement activé (voir README principal)
python -m webapp.server        # http://localhost:8770
```

- Avec `MISTRAL_API_KEY` dans `.env` → vérification réelle en direct.
- **Sans** clé → l'interface affiche explicitement « moteur non connecté ».
  Aucun résultat n'est jamais simulé (règle impérative anti-hallucination).

Port configurable : `WEBAPP_PORT=8888 python -m webapp.server`.

## Ce que fait cette couche (et ce qu'elle ne fait PAS)

| Fait | Ne fait PAS |
|---|---|
| Appelle le vrai moteur via `SentinelGuard.ask` (réutilise `ui/server.py`) | Ne re-vérifie rien, ne juge rien |
| Traduit le **statut déterministe** du moteur en **score 0-100 + couleur** | N'invente aucun statut ni champ |
| Affiche le passage source réel, la source, le journal de conformité | Ne masque ni ne reformule les données du moteur |
| Marque « intervention humaine requise » quand `published == False` | Ne prend aucune décision d'approbation/rejet (hors interface) |

## Organisation des fichiers

```
webapp/
├── README.md          ← ce fichier
├── __init__.py
├── server.py          ← backend stdlib : GET / (front) + POST /ask + POST /resolve
│                         réutilise ui/server.py (_run_pipeline, detect_route, resolve_parlement_uid)
│                         puis ENRICHIT le JSON réel avec les scores (presentation.py)
├── presentation.py    ← COUCHE « À NOUS » : statut moteur → score 0-100 + bande de couleur
│                         (déterministe, testable : `python -m webapp.presentation`)
└── static/            ← front (aucune dépendance, aucun asset externe)
    ├── index.html     ← structure : en-tête, fil, saisie, panneau de traçabilité
    ├── style.css      ← design sombre futuriste (dégradés, jauges conic-gradient, bandes de couleur)
    └── app.js         ← logique : /resolve → /ask, rendu des cartes, panneau de traçabilité
```

## Le score 0-100 (couche `presentation.py`)

Le score est un **habillage déterministe** du statut du moteur, pas une nouvelle
logique de confiance. Mapping (valeurs fixes, reproductibles) :

| Statut moteur | Score | Bande / couleur |
|---|---|---|
| `AUTHENTIFIÉ` (risque faible, publié) | 96 | 🟢 vérifié |
| `DONNÉE_TRACÉE` | 88 | 🔵 donnée tracée |
| `CITÉ_NON_OPPOSABLE` | 55 | 🟠 prudence |
| `INTERPRÉTATION` | 50 | 🟠 prudence |
| `NON_AUTHENTIFIÉ` | 20 | 🔴 risque |
| `NO_ANSWER` (aucune affirmation) | 5 | 🔴 risque |
| **`published == False`** (quel que soit le statut) | plafonné à 45 | 🟠/🔴 + badge 🧑‍⚖️ |

Le score d'une **intention** = celui de son claim le plus faible (le maillon
faible gouverne — cohérent avec l'esprit du moteur qui bloque au moindre signal).

**Phrase de pitch** : « ce chiffre ne juge rien, il traduit en couleur un statut
que le code a déjà établi mot pour mot ».

## Flux d'un échange (côté front)

1. `POST /resolve` → détecte la route (`code_article`, `parlement_question`,
   `donnee`, `texte_libre`) et pré-remplit les champs.
2. Route auto-remplissable (`code_article`, `texte_libre`) → `POST /ask` direct.
   Route parlementaire → choix d'un candidat UID. Route donnée → petit formulaire.
3. `POST /ask` → pipeline réel + scores → une carte par intention (jauge, badge,
   claims), avec panneau de traçabilité au clic (passage source, source, journal).

## Choix d'architecture

- **stdlib uniquement** (`http.server`) : zéro dépendance à installer, l'équipe
  lance la démo sans friction. Le cahier suggérait FastAPI ; on a préféré la
  robustesse zéro-install (le moteur et `ui/` prouvent déjà que stdlib suffit).
  Migration vers FastAPI triviale si besoin (les 2 handlers sont isolés).
- **réutilisation de `ui/server.py`** : une seule source de vérité pour appeler
  le moteur et sérialiser un `AskResult`. On n'a pas dupliqué cette logique
  (elle contient des subtilités correctes : claim de contrôle de secours,
  garde `pertinence_non_garantie`).
