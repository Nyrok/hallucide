# Sentinel Guard

Orchestrateur de gouvernance pour la fidélité documentaire (spec v3) : un pipeline déterministe qui décompose une question, récupère des passages depuis des sources officielles réelles, et vérifie chaque citation mot pour mot avant publication — sans jamais faire confiance au LLM pour juger de sa propre fidélité.

141 tests, exemples exécutables + démonstrateur web. Statut détaillé section par section : voir `STATUS.md`.

## Prérequis

- Python 3.11+
- Une clé API Mistral (obligatoire pour l'UI et la plupart des exemples) et/ou Gemini (`.env`, voir plus bas)

## Installation

```bash
python -m venv .venv
```

Windows (PowerShell) :
```powershell
.venv\Scripts\Activate.ps1
```
Linux/macOS :
```bash
source .venv/bin/activate
```

Puis, dans l'environnement activé :
```bash
python -m pip install -e .[test]
```

## Configuration (`.env`)

Copier le template et renseigner au moins `MISTRAL_API_KEY` :

```bash
cp .env.example .env    # Windows: Copy-Item .env.example .env
```

```
MISTRAL_API_KEY=sk-...
GEMINI_API_KEY=...      # optionnelle, pour les exemples/tests Gemini
```

`.env` n'est jamais versionné (voir `.gitignore`) — ne jamais committer de vraie clé.

## Démarrage du serveur / démonstrateur web

Le serveur UI (`ui/server.py`) lit `.env` à la racine du projet, décompose la question via Mistral, interroge les sources réelles (Moulineuse/data.gouv), vérifie chaque claim, puis sert le résultat sur une page web locale.

```bash
python -m ui.server
```

Puis ouvrir **http://localhost:8765** dans un navigateur.

- Saisir une question, ou cliquer « 🔎 Détecter la source automatiquement » pour laisser le système proposer la route (article de code / question parlementaire / donnée chiffrée / recherche libre) et résoudre l'UID si besoin.
- Chaque intention affiche un statut coloré (`AUTHENTIFIÉ` / `CITÉ_NON_OPPOSABLE` / `NON_AUTHENTIFIÉ` / `INTERPRÉTATION` / `DONNÉE_TRACÉE` / `NO_ANSWER`) et le journal de conformité rejouable (§8).
- Arrêt : `Ctrl+C` dans le terminal où le serveur tourne.

Si le port 8765 est déjà occupé (serveur précédent non arrêté), le retrouver et l'arrêter avant de relancer :
```powershell
Get-NetTCPConnection -LocalPort 8765 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

## Architecture

```
Client → SentinelGuard.ask() → Orchestrator (décompose, récupère, vérifie)
              ├── MultiSourceRetrievalProvider
              │     ├── MoulineuseRetrievalProvider  (normatif/parlementaire, MCP réel)
              │     ├── DataGouvRetrievalProvider    (donnée tabulaire, MCP réel)
              │     └── FileRetrievalProvider        (fichier CSV/ZIP non-tabulaire)
              ├── verifier.py        (contrôle verbatim déterministe, §7)
              ├── triage.py          (plancher de risque, §2)
              ├── human_validation.py (validation humaine, §4 étape 9)
              └── SovereignLogStore  (journaux cloisonnés conformité/accès, §13.4)
```

## Sources réelles branchées

- **Moulineuse** (`mcp.code4code.eu`) : articles de code consolidés (route SQL multi-étapes), articles parlementaires pastillés, questions parlementaires (QE/QOSD/QG), recherche plein texte avec repli "pertinence non garantie", multi-saut réel via les renvois `LIENS`.
- **data.gouv.fr** (`mcp.data.gouv.fr`) : données chiffrées tracées via l'API tabulaire (dataset → ressource → cellule filtrée), statut `DONNÉE_TRACÉE`.
- **Fichiers CSV/ZIP** téléchargés directement pour les ressources data.gouv non indexées par l'API tabulaire (couvre l'INSEE) — détection défensive du format, adressage de cellule par filtres multi-colonnes.
- **Gemini** (`generativelanguage.googleapis.com`) et **Mistral** (`api.mistral.ai`) : LLM réels pour la décomposition et la génération de claims.

Toutes vérifiées en conditions réelles, pas seulement en mocks (voir `examples/`).

## Garanties (ce que le code prouve, pas le modèle)

- Une citation publiée `AUTHENTIFIÉ` existe mot pour mot dans la source officielle **opposable** récupérée (§7).
- Le plancher de risque ne peut jamais descendre sous `élevé` une fois qu'une condition déterministe (référence inférée, troncature, pertinence non garantie, couverture insuffisante) est détectée (§2/INV-011).
- Une intention à risque élevé n'est jamais publiée sans décision humaine explicite, capturée et journalisée (§4 étape 9).
- Le journal de conformité ne contient jamais la question posée ni une identité (§13.4) — garde-fou vérifié par assertion, pas par convention.

## Tests

```bash
python -m pytest
```

## Exemples

Scripts exécutables dans `examples/` (certains nécessitent `.env`, voir plus haut ; Moulineuse/data.gouv ne demandent pas de clé) :

```bash
python examples/run_sentinel_guard.py
```
