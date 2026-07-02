# Sentinel Guard

Orchestrateur de gouvernance pour la fidélité documentaire (spec v4) : un pipeline déterministe qui décompose une question, récupère des passages depuis des sources officielles réelles, et vérifie chaque citation mot pour mot avant publication — sans jamais faire confiance au LLM pour juger de sa propre fidélité. Le **mode document** (v4) étend la garantie aux notes, synthèses et amendements : un document est une liste de claims vérifiés un à un, jamais un « document vérifié » en bloc.

173 tests, exemples exécutables + démonstrateur web. Statut détaillé section par section : voir `STATUS.md` ; spécification : `sentinel-guard-spec-v4.md`.

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
- **Marquage « intervention humaine requise » (§4 étape 9)** : tout résultat à risque élevé porte un marquage visuel explicite (badge 🧑‍⚖️ + motifs possibles + clé de validation `intent_id`/`passage_hash`) et reste « NON PUBLIABLE en l'état ». La décision d'approbation/rejet ne se prend pas dans cette page : elle relève du circuit de validation de l'institution, via le `HumanValidationRegistry` du cœur.
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

- Une citation publiée `AUTHENTIFIÉ` existe mot pour mot dans la source officielle **opposable** récupérée (§7) — et le vérificateur re-contrôle lui-même le cycle de vie (`etat` ≠ VIGUEUR → jamais `AUTHENTIFIÉ`, défense en profondeur C2).
- Le plancher de risque ne peut jamais descendre sous `élevé` une fois qu'une condition déterministe est détectée (§2/INV-011) : référence inférée, troncature, pertinence non garantie, couverture insuffisante, claim `INTERPRÉTATION` ou `CITÉ_NON_OPPOSABLE`, sélection ambiguë entre plusieurs candidats, ou query unique partagée entre plusieurs intentions (E1 dégradé).
- Une `INTERPRÉTATION` doit ancrer **tous** ses marqueurs de négation et **toutes** ses valeurs chiffrées dans la source (ancres dures anti-distorsion B3), en plus du recouvrement lexical ≥60%.
- L'opposabilité dérive du type de document et de son cycle de vie, jamais d'un flag de requête ni du modèle (INV-010).
- **Mode document (v4, §7ter)** : un document n'a jamais de statut agrégé — chaque claim garde le sien (INV-015) ; un document en mode production est toujours à risque élevé, une synthèse de source normative aussi (INV-016) ; une synthèse doit couvrir ou déclarer omise chaque unité structurelle segmentée par le code — l'omission silencieuse (piège B5) bloque la publication (INV-017).
- Une intention à risque élevé n'est jamais publiée sans décision humaine explicite, capturée et journalisée (§4 étape 9).
- Le journal de conformité ne contient jamais la question posée ni une identité (§13.4) — garde-fou vérifié par assertion, pas par convention.

## Tests

```bash
python -m pytest
```

**173 tests automatisés**, dont 16 tests du mode document v4 (`tests/test_document.py` — INV-015/016/017, piège B5, segmentation, mesure par mode ; démo exécutable : `python examples/run_document_mode.py`) et 16 tests de non-régression couvrant la seconde relecture (voir `STATUS.md`, « Relecture 2 ») : plancher de risque sur les statuts faibles (`INTERPRÉTATION`/`CITÉ_NON_OPPOSABLE`), ancres dures négation/chiffres, suppression de `opposable_override`, mode dégradé E1 (query partagée), re-contrôle d'abrogation dans le vérificateur, sélection ambiguë, insensibilité casse/ponctuation de bord, virgule décimale.

### Tests en conditions réelles (démonstrateur, 2026-07-02)

Deux scénarios joués en direct contre les sources réelles (Moulineuse + Mistral), validant la chaîne complète jusqu'à la décision humaine :

| Scénario | Ce qui s'est passé | Verdict |
|---|---|---|
| **Prémisse fausse (A2)** — « Teneur de la QOSD n° 0812 sur la fermeture d'une trésorerie, quelle commune ? » (la vraie QOSD 812 porte sur les contrats aidés) | Le système a récupéré le vrai texte officiel, n'a **pas** inventé la commune demandée (`NO_ANSWER`, zéro hallucination), source non opposable + 3 intentions sur 1 requête → risque élevé, panneau de validation humaine sur chaque intention | ✅ conforme — décision attendue : rejet |
| **N questions → 1 requête (E1)** — « Que dit l'article 1103 du code civil et quelle est la règle de bonne foi ? » | 2 intentions détectées (couverture 100%), la requête unique (art. 1103) a servi les deux : intention 1 correcte (verbatim `AUTHENTIFIÉ`, opposable), intention 2 hors sujet (la bonne foi est à l'art. 1104) mais **bloquée** par le plancher E1 + slot inféré (A3) → validation humaine | ✅ conforme — décisions attendues : approbation (1), rejet (2) |

Le second scénario matérialise le cas que les corrections visaient : un passage authentique, exact et opposable, présenté en réponse à une question à laquelle il ne répond pas — chaque élément est vrai isolément, et c'était publiable automatiquement avant le plancher E1. Le contrôle revient désormais à l'humain.

## Exemples

Scripts exécutables dans `examples/` (certains nécessitent `.env`, voir plus haut ; Moulineuse/data.gouv ne demandent pas de clé) :

```bash
python examples/run_sentinel_guard.py
```
