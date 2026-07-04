# COMPRENDRE le projet — guide pour l'équipe (non-initié bienvenu)

> Ce fichier est le **point d'entrée** pour comprendre et **défendre** le projet au
> pitch. Lis-le en entier avant de toucher au code. Il décrit la **réalité du
> moteur** (vérifiée en lisant le code, pas supposée), pas une intention.
>
> Écrit la nuit du 3→4 juillet 2026 en autonomie. Le moteur n'a **pas** été modifié
> (voir §7 « Ce qui a été touché »). Tout ce qui est ajouté vit dans `app/`.

---

## 1. Le projet en 3 phrases

**Sentinel Guard** est un moteur qui répond à une question en ne s'appuyant que sur
des **sources officielles réelles** (textes de loi, questions parlementaires, données
publiques), et qui **vérifie chaque affirmation mot pour mot** contre la source avant
de la publier. Il ne fait **jamais confiance au LLM** pour juger de sa propre
fidélité : c'est un pipeline **déterministe** qui décompose, récupère, puis vérifie.
Au moindre risque (source non opposable, citation approximative, intention non
couverte…), il **refuse la publication automatique** et exige une **validation
humaine** — jamais d'hallucination déguisée en réponse.

C'est donc un **détecteur / bloqueur d'hallucination** appliqué au domaine juridique
et administratif français.

---

## 2. Rôle de chaque module (`src/sentinel_guard/`)

Source : `docs/STATUS.md`. Une ligne par module.

| Module | Rôle en une phrase |
|---|---|
| `types.py` | Les types de base : `Intent`, `Passage`, `Claim`, `ClaimStatus`, `RiskTier`, `OrchestrationResult`… |
| `normalization.py` | Nettoie le texte et les nombres avant comparaison (casse, ponctuation, virgule décimale). |
| `verifier.py` | **Le cœur** : vérifie qu'une citation existe *mot pour mot* dans la source (contiguïté, anti-troncature, ancres négation/chiffres). |
| `triage.py` | Le **plancher de risque** : une fois un signal de danger détecté, le risque ne peut plus redescendre. |
| `coverage.py` | Vérifie qu'aucune intention de la question n'a été oubliée (echo-back + couverture). |
| `slot_provenance.py` | Distingue une référence *copiée* de la question d'une référence *inférée* par le modèle (piège A3). |
| `retrieval.py` | Bornes génériques du multi-saut (ne pas boucler, ne pas dépasser le budget). |
| `multi_hop.py` | Suit les renvois réels entre textes (« voir article … ») sur la source Moulineuse. |
| `mcp_client.py` | Façade technique pour appeler les serveurs de données (protocole MCP). |
| `moulineuse.py` | Récupère le **normatif/parlementaire** réel (`mcp.code4code.eu`) : articles de code, pastilles, texte libre, questions parlementaires. |
| `datagouv.py` | Récupère une **donnée chiffrée** tracée via l'API tabulaire de data.gouv. |
| `file_retrieval.py` | Récupère une donnée depuis un **fichier CSV/ZIP** téléchargé (couvre l'INSEE). |
| `multi_source.py` | Aiguille la question vers la bonne source de récupération. |
| `orchestration.py` | La **boucle principale** qui enchaîne décomposition → récupération → vérification. |
| `llm.py` | Abstraction du LLM : prompts de décomposition, parsing du JSON renvoyé. |
| `gemini.py` / `mistral.py` | Les deux **LLM réels** branchés (appels HTTP maison). |
| `litellm_provider.py` | Variante d'accès au LLM via LiteLLM (optionnel). |
| `document.py` | Mode document v4 : traite une note/synthèse/amendement comme une liste de claims vérifiés un à un. |
| `human_validation.py` | Registre des **décisions humaines** (approbation/rejet) sur les cas à risque. |
| `audit.py` | **Journal de conformité** rejouable (hashes de passages), sans la question ni d'identité. |
| `sovereign_log.py` | Cloisonne les journaux (conformité vs accès) — mode souverain. |
| `core.py` | La **façade** `SentinelGuard.ask(...)` qui câble tout le reste. |
| `measurement.py` / `trap_dataset.py` | Banc de mesure (taux de blocage, sur-refus) sur des cas pièges. |
| `calibration.py` | Kappa de Cohen entre annotateurs humains (qualité du jeu de référence). |
| `exceptions.py` | Les exceptions du moteur. |

---

## 3. Le flux complet d'une question, étape par étape

```
Question de l'utilisateur
   │
   ▼
[1] DÉCOMPOSITION  (llm.py + orchestration.py)
    Le LLM (Mistral/Gemini) découpe la question en une ou plusieurs INTENTIONS
    (sous-questions atomiques). Ex : « art. 1103 ET règle de bonne foi » → 2 intentions.
   │
   ▼
[1bis] COUVERTURE  (coverage.py)
    On vérifie qu'on n'a oublié aucun morceau de la question (echo-back + ratio de
    couverture). Une intention oubliée → risque élevé.
   │
   ▼
[2] RÉCUPÉRATION RÉELLE  (multi_source.py → moulineuse.py / datagouv.py / file_retrieval.py)
    Pour chaque intention, on va chercher le vrai PASSAGE dans la source officielle
    (jamais inventé par le LLM). Le passage porte : source_id, source_type,
    opposable (oui/non), et des metadata (titre, état du texte…).
   │
   ▼
[3] VÉRIFICATION DÉTERMINISTE  (verifier.py + normalization.py)
    Chaque affirmation (CLAIM) est comparée MOT POUR MOT au passage :
      - existe verbatim et opposable  → AUTHENTIFIÉ
      - existe verbatim mais non opposable → CITÉ_NON_OPPOSABLE
      - reformulation ancrée (négations + chiffres présents, recouvrement ≥60%) → INTERPRÉTATION
      - donnée chiffrée = cellule exacte → DONNÉE_TRACÉE
      - sinon → NON_AUTHENTIFIÉ
    NB : les checks « négation » et « chiffres » (ancres dures) et l'ancrage
    lexical ≥60% sont DÉJÀ implémentés et testés (verifier.py:118, :130-134,
    :149-150). Seule la similarité SÉMANTIQUE par embeddings reste à faire.
    Détail complet et statut par sous-étape : voir PROCESSUS_FINAL.md.
   │
   ▼
[4] PLANCHER DE RISQUE  (triage.py)
    Tout signal de danger (référence inférée, troncature, pertinence non garantie,
    couverture insuffisante, INTERPRÉTATION/CITÉ_NON_OPPOSABLE, sélection ambiguë,
    une seule requête partagée entre plusieurs intentions) force le risque à ÉLEVÉ.
   │
   ▼
[5] DÉCISION DE PUBLICATION  (human_validation.py + core.py)
    - risque FAIBLE  → published = True  (affichable)
    - risque ÉLEVÉ   → published = False (🧑‍⚖️ intervention humaine requise, NON PUBLIABLE)
   │
   ▼
[6] JOURNALISATION  (audit.py + sovereign_log.py)
    Une entrée de conformité rejouable par intention (hash du passage), SANS la
    question ni d'identité.
   │
   ▼
AskResult
```

---

## 4. Comment appeler le moteur

Point d'entrée unique (`core.py`) :

```python
from sentinel_guard import SentinelGuard, MistralModelProvider

guard = SentinelGuard(model_provider=MistralModelProvider(api_key="sk-..."))
result = guard.ask(message="Que dit l'article 1103 du code civil ?",
                   query={"route": "code_article", "article": "1103", "code": "code civil"})
```

`query` est **structurée** et dépend de la route choisie (voir `ui/server.py::_build_query`
pour les 5 routes réelles : `code_article`, `parlement_question`, `texte_libre`,
`donnee`, `fichier`).

### Champs de `AskResult` (lus dans `core.py`)

| Champ | Type | Contenu |
|---|---|---|
| `orchestration` | `OrchestrationResult` | Le résultat détaillé (voir ci-dessous). |
| `compliance_entries` | tuple[`ComplianceLogEntry`] | 1 entrée de journal par intention (même ordre que `results`). |
| `session_ref` | `str` | Référence de session (traçabilité). |
| `published` | tuple[`bool`] | 1 booléen par intention : `True` = affichable, `False` = validation humaine requise. |

`OrchestrationResult` (`types.py`) contient :
- `intents` : tuple d'`Intent` (`id`, `question`).
- `results` : tuple d'`IntentExecutionResult`, chacun avec :
  - `intent` (l'`Intent`),
  - `passage` : `Passage(source_id, source_type, opposable, text, metadata)`,
  - `verification` : `VerificationResult(verbatim_check, claims)` où chaque `Claim` a `ref`, `status`, `truncation_flagged`,
  - `risk_tier` : `RiskTier.FAIBLE` ou `RiskTier.ÉLEVÉ`.
- `echo_back`, `coverage_passed`, `coverage_ratio`, `coverage_missing_tokens`.

`ComplianceLogEntry` (`audit.py`) contient notamment : `passage_hashes`,
`compliance_status`, `human_validation`, `verbatim_check`, et `to_dict()` pour la
sérialisation JSON.

---

## 5. Les statuts — ATTENTION, distinction importante

Le cahier des charges parlait de « 6 statuts ». **C'est une imprécision.** En réalité
il y a **deux niveaux** :

### a) Les 5 `ClaimStatus` (`types.py`) — statut d'UNE affirmation

| Statut | Signification |
|---|---|
| `AUTHENTIFIÉ` | La citation existe **mot pour mot** dans une source **opposable** en vigueur. C'est la preuve forte. |
| `CITÉ_NON_OPPOSABLE` | Citation exacte, mais la source n'est **pas opposable** (ou texte abrogé). Vrai, mais pas invocable juridiquement. |
| `INTERPRÉTATION` | Reformulation ancrée dans la source (négations + chiffres présents, recouvrement ≥60%). Plus faible → passe par l'humain. |
| `DONNÉE_TRACÉE` | Une donnée chiffrée retrouvée à la **cellule exacte** d'une source publique (data.gouv/INSEE). |
| `NON_AUTHENTIFIÉ` | Non retrouvé mot pour mot → **potentielle hallucination**, bloqué. |

### b) `NO_ANSWER` — c'est un `compliance_status`, PAS un `ClaimStatus`

Défini dans `audit.py::_compliance_status` : quand le LLM n'a produit **aucune
affirmation** (ex. source hors sujet), le journal note `NO_ANSWER` — « aucune réponse
fiable ». C'est un **excellent** signe anti-hallucination (le système préfère se taire
plutôt qu'inventer), mais ce n'est pas un statut de claim.

Les trois `compliance_status` possibles (`audit.py`) :
- `VALIDATED` : des claims produits ET vérifiés (`verbatim_check == PASS`).
- `BLOCKED` : des claims produits mais la vérification a échoué.
- `NO_ANSWER` : aucun claim produit.

> **Conséquence concrète** pour la couche d'affichage (`app/`) : la fonction de
> score doit lire le **statut du claim** ET le **compliance_status** (pour couvrir
> `NO_ANSWER`). C'est ce qui est fait dans `app/presentation.py`.

---

## 6. La phrase de défense au pitch

> **« Ici, c'est le code qui prouve, pas le modèle. »**
>
> Une citation `AUTHENTIFIÉ` existe **mot pour mot** dans la source officielle
> opposable — le vérificateur (`verifier.py`) le re-contrôle lui-même, y compris le
> cycle de vie du texte (un texte abrogé ne peut jamais être `AUTHENTIFIÉ`).
> Au **moindre** signal de risque, le système ne publie **rien** automatiquement : il
> exige une **validation humaine** explicite et journalisée. Le LLM ne juge jamais de
> sa propre fidélité ; il ne fait que proposer, le code dispose.

Deux cas réels déjà joués (voir `README.md`) qui matérialisent la garantie :
1. **Prémisse fausse** : question sur une QOSD dont le contenu était faux → le système
   n'a **pas** inventé la réponse attendue (`NO_ANSWER`, zéro hallucination).
2. **Bonne réponse à la mauvaise question** : un passage authentique et exact présenté
   pour une question à laquelle il ne répond pas → **bloqué** par le plancher de
   risque, renvoyé à l'humain.

---

## 7. Ce qui a été touché (transparence)

**Mise à jour du 4 juillet** : sur décision de l'équipe, on est passé de « ne rien
toucher au moteur » à « étendre le moteur de façon additive et prouvée ». Deux
changements dans `src/sentinel_guard/`, tous deux **additifs** (rien de retiré,
comportement d'origine inchangé, 175 tests d'origine préservés) :

- **Réorganisation par étapes** : les 27 modules rangés en dossiers `_1_…` à
  `_7_…` + `core_types/`, `llm_providers/`, `analysis/` (voir `REORGANISATION.md`
  à la racine). Aucune logique modifiée, seulement des déplacements + imports.
- **Nouveau module `_4_verification/semantic_similarity.py`** (étape 8, Path A) :
  proximité de reformulation déterministe (Jaccard tokens + trigrammes), sans ML.
  Additif : il ne peut qu'**augmenter** le risque, jamais authentifier. 16 tests
  dédiés (`tests/test_semantic_similarity.py`). Détail : `PROCESSUS_FINAL.md`.

**Modification d'emballage (hors moteur), nécessaire pour l'install :**

- **`pyproject.toml`** : le champ `authors` était au format Poetry (`["… <email>"]`),
  invalide pour setuptools/PEP 621 → l'installation `pip install -e .[test]`
  **échouait**. Corrigé en `authors = [{name = "…", email = "…"}]`, et ajout de la
  découverte de packages pour le layout `src/` (`[tool.setuptools.packages.find]`).
  Sans ça, impossible de lancer les tests. **Ce n'est pas le moteur, c'est l'emballage.**

**Écarts entre le cahier et la réalité du code (à connaître pour le pitch) :**

1. **« 6 statuts »** → en fait **5 `ClaimStatus`** + `NO_ANSWER` qui est un
   `compliance_status` (voir §5). Le cahier confondait les deux niveaux.
2. **« 173 tests »** → en réalité **175 tests passent** (vérifié : `pytest -q` →
   `175 passed`).
3. Le serveur existant `ui/server.py` **fait déjà** l'appel au moteur et la
   sérialisation JSON d'un `AskResult` (routes `/ask` et `/resolve`). La nouvelle
   couche `app/` **réutilise cette logique éprouvée** plutôt que de la réécrire
   (elle contient des subtilités correctes : claim de contrôle de secours,
   garde `pertinence_non_garantie`).

Aucun autre bug bloquant trouvé dans le moteur.

---

## 8. Vérifier soi-même (5 minutes)

```bash
python -m venv .venv
# Windows : .venv\Scripts\Activate.ps1   |  Linux/mac : source .venv/bin/activate
python -m pip install -e ".[test]"
python -m pytest -q          # attendu : 175 passed

# Démo moteur historique (nécessite MISTRAL_API_KEY dans .env) :
python -m ui.server          # http://localhost:8765

# Nouvelle interface de chat futuriste (voir app/README.md) :
python -m app.server      # http://localhost:8770
```
