# app/ — front de chat DSFR et backend HTTP

Interface web branchée sur le moteur Hallucide. Le moteur
(`src/hallucide/`) et le démonstrateur historique (`ui/`) ne sont pas
modifiés : cette couche les consomme, elle ne les remplace pas.

## Lancer

```bash
# depuis la racine, environnement activé (voir README principal)
python -m app.server        # http://localhost:8770
```

- Avec une clé API dans `.env` (Claude par défaut) : vérification réelle en direct.
- Sans clé : l'interface affiche « moteur non connecté ». Aucun résultat n'est
  jamais simulé.

Port configurable : `WEBAPP_PORT=8888 python -m app.server`.

## Ce que fait cette couche, et ce qu'elle ne fait pas

| Fait | Ne fait pas |
|---|---|
| Appelle le vrai moteur via `Hallucide.ask` (réutilise `ui/server.py`) | Ne re-vérifie rien, ne juge rien |
| Traduit le statut déterministe du moteur en score 0-100 + couleur | N'invente aucun statut ni champ |
| Affiche le passage source réel, la source, le journal de conformité | Ne masque ni ne reformule les données du moteur |
| Marque « revue humaine requise » quand `published == False` | Ne prend aucune décision d'approbation/rejet |

## Organisation des fichiers

```
app/
├── README.md          ce fichier
├── __init__.py
├── server.py          backend stdlib : GET / (front) + POST /ask + POST /resolve
│                      réutilise ui/server.py puis enrichit le JSON réel
│                      avec les scores (presentation.py)
├── presentation.py    statut moteur → score 0-100 + bande de couleur
│                      (déterministe, testable : python -m app.presentation)
└── static/            front DSFR (CDN 1.14.4, comportement JS maison)
    ├── index.html     en-tête, fil de chat, saisie, panneau de traçabilité
    ├── style.css      layout chatbox + classes hd-* (couleurs de statut)
    └── app.js         /resolve puis /ask, prose annotée, donut, accordéons
```

## Le score 0-100 (`presentation.py`)

Le score est un habillage déterministe du statut du moteur, pas une nouvelle
logique de confiance. Valeurs fixes, reproductibles :

| Statut moteur | Score | Bande |
|---|---|---|
| `AUTHENTIFIÉ` (risque faible, publié) | 96 | vérifié (vert) |
| `DONNÉE_TRACÉE` | 88 | donnée tracée (bleu) |
| `CITÉ_NON_OPPOSABLE` | 55 | prudence (orange) |
| `INTERPRÉTATION` | 50 | prudence (orange) |
| `NON_AUTHENTIFIÉ` | 20 | risque (rouge) |
| `NO_ANSWER` | 5 | risque (rouge) |
| `published == False` (quel que soit le statut) | plafonné à 45 | prudence ou risque, badge « revue humaine requise » |

Le score d'une intention est celui de son claim le plus faible : le maillon
faible gouverne, comme dans le moteur qui bloque au moindre signal.

## Flux d'un échange

1. `POST /resolve` détecte la route (`code_article`, `parlement_question`,
   `commissions`, `donnee`, `texte_libre`) et pré-remplit les champs.
2. Route auto-remplissable : `POST /ask` direct. Route parlementaire : choix
   d'un candidat UID. Route donnée : petit formulaire.
3. `POST /ask` lance le pipeline réel. Le front affiche la prose annotée
   (soulignage par statut), le donut de confiance global, puis un accordéon par
   affirmation avec sa source et sa traçabilité complète.

## Choix d'architecture

- stdlib uniquement (`http.server`) : zéro dépendance à installer. Migration
  FastAPI triviale si besoin, les deux handlers sont isolés.
- Réutilisation de `ui/server.py` : une seule source de vérité pour appeler le
  moteur et sérialiser un `AskResult` (claim de contrôle de secours, garde
  `pertinence_non_garantie`).
- Accordéons DSFR pilotés par `app.js` : le JS DSFR instancie mal du DOM
  injecté dynamiquement, seul le CSS DSFR est chargé.
