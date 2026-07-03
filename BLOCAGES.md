# BLOCAGES — ce qui reste à faire / ce que je n'ai pas pu terminer

> Rédigé la nuit du 3→4 juillet 2026 en autonomie. Liste honnête des points où
> je suis bloqué ou qui demandent une décision/action humaine. Classés par
> priorité pour la reprise de demain 9h.

---

## 🔴 Bloquant pour la démo — à traiter en priorité

### 1. Pas de clé API → pipeline live jamais exécuté cette nuit
- **État** : `.env` est absent (seulement `.env.example`). Sans `MISTRAL_API_KEY`,
  impossible d'appeler le vrai moteur.
- **Ce qui est prouvé quand même** : les 175 tests passent ; la couche de score
  est testée (`python -m webapp.presentation`) ; le backend est testé de bout en
  bout sur un `AskResult` réaliste (enrichissement OK) ; l'endpoint `/ask` renvoie
  correctement « moteur non connecté » sans clé ; `/resolve` détecte les routes.
- **Ce qui n'est PAS prouvé** : une vraie question posée en direct contre
  Moulineuse + Mistral, de bout en bout dans la nouvelle UI.
- **Action équipe** : `cp .env.example .env`, coller une `MISTRAL_API_KEY`,
  lancer `python -m webapp.server`, poser une vraie question (ex. « Que dit
  l'article 1103 du code civil ? ») et vérifier l'affichage réel.

### 2. Vérification visuelle du front non faite
- **État** : le front est servi correctement (HTTP 200 sur `/`, `/static/*`) et sa
  structure est validée, mais je n'ai pas pu **voir** le rendu dans un navigateur
  (pas de navigateur dans mon environnement, et impossible de le prévisualiser
  hors-ligne puisqu'il appelle un backend live).
- **Action équipe** : ouvrir http://localhost:8770, vérifier le rendu (jauges,
  couleurs, panneau de traçabilité au clic) et ajuster le CSS au goût.

---

## 🟠 Décisions / câblage à faire

### 3. Sélecteur de modèle : Gemini non câblé
- **État** : le backend réutilise `ui/server.py::_run_pipeline`, qui instancie
  **en dur** `MistralModelProvider`. J'ai **désactivé** l'option Gemini dans le
  front (« à câbler ») plutôt que de la laisser utiliser Mistral en silence — ce
  serait une tromperie contraire à l'esprit du projet.
- **Pour câbler Gemini** (2 options) :
  - (a) étendre `_run_pipeline(message, route, form, model=...)` pour choisir le
    provider — mais cela modifie `ui/server.py` (toléré ? c'est le démonstrateur,
    pas le moteur `src/`) ;
  - (b) faire construire le `SentinelGuard` directement dans `webapp/server.py`
    selon le modèle choisi, au prix d'une petite duplication de la sérialisation.
  - Recommandation : (a), c'est le moins de code et `ui/` n'est pas le moteur.

### 4. Routes « donnée » / « fichier » : identifiants manuels
- **État** : ces routes (data.gouv/INSEE, statut `DONNÉE_TRACÉE`) ne sont pas
  auto-détectables depuis la question — le front affiche un formulaire à remplir
  (`dataset_id`, `resource_id`, colonne cible…), mais il faut de **vrais IDs**.
- **Action équipe** : pour démontrer un cas `DONNÉE_TRACÉE` vert/bleu, préparer à
  l'avance un dataset data.gouv connu (voir `examples/run_datagouv.py` pour un cas
  qui marche) et noter ses identifiants.

---

## 🟡 Mineur / cosmétique

### 5. Fins de ligne LF→CRLF (Windows)
- Git affiche des avertissements `LF will be replaced by CRLF`. Sans conséquence,
  mais on peut ajouter un `.gitattributes` (`* text=auto eol=lf`) pour figer les
  fins de ligne côté équipe (utile si des Linux/Mac rejoignent).

### 6. Python 3.11.0rc2 sur la machine Windows
- La machine tourne sur une **release candidate** de Python 3.11 (`3.11.0rc2`).
  Les tests passent, mais installer un 3.11.x stable (ou 3.12) est plus sûr pour
  la démo.

---

## ✅ Fait cette nuit (rappel)
- Fix packaging (`pyproject.toml`) → install `pip install -e .[test]` fonctionne.
- 175 tests vérifiés (le cahier disait 173).
- `COMPRENDRE.md` (Partie 1) : moteur expliqué, champs réels, statuts, écarts
  cahier/réel, phrase de pitch.
- `webapp/` (Partie 2) : couche de score `presentation.py` (testée), backend
  `server.py` (`/ask` + `/resolve`, réutilise le moteur, « moteur non connecté »
  explicite), front de chat futuriste (`static/`), `README.md`.
- Moteur `src/sentinel_guard/` et démonstrateur `ui/` : **non modifiés**.
- Commits séparés par étape (voir `git log`).
