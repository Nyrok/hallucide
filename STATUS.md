# Statut d'implémentation — Sentinel-Guard v3

Dernière mise à jour : voir date du commit. 140 tests passent (`python -m pytest`).

Estimation globale : **~87%** de la spec v3 implémentée. Le cœur de la garantie (§2, §4, §6, §7, §14, §15) est complet et vérifié en conditions réelles. L'infrastructure de mesure (§12), y compris la calibration inter-annotateur, est codée et testée ; il ne manque que de vraies annotations humaines pour l'exercer en conditions réelles. Le seul point structurellement hors de portée du code seul reste D1-D3/C3/E3, que la spec elle-même classe limite mathématique du contrôle déterministe (§10).

## Par section

| Section | % | Module(s) | État |
|---|---|---|---|
| §1bis Glossaire | 100% | `types.py` | Les 5 `ClaimStatus` respectent strictement les 3 niveaux fidélité/pertinence/interprétation |
| §2 Plancher de risque | ~95% | `triage.py`, `orchestration.py` | `max(LLM, plancher)` automatique : couverture (E4), slot inféré (A3), troncature (B2), pertinence non garantie (C1) — aucun n'est contournable par l'appelant |
| §3 Abstraction moteur | ~95% | `llm.py`, `gemini.py`, `mistral.py`, `litellm_provider.py` | Gemini + Mistral réels (wrappers HTTP maison), plus `LiteLLMModelProvider` (§17.1) — trois implémentations concrètes de `ModelProvider`, toutes vérifiées en direct |
| **§4 Flux complet** | **100%** | `orchestration.py`, `core.py`, `coverage.py`, `multi_hop.py`, `human_validation.py` | Toutes les étapes 0-10 implémentées et testées, multi-saut réel inclus |
| §4bis Structuré/texte libre | ~90% | `moulineuse.py`, `datagouv.py`, `slot_provenance.py` | Routes structurées + repli texte libre marqué "pertinence non garantie" |
| §4ter Multi-saut | 100% | `multi_hop.py`, `retrieval.py` | Prouvé en direct sur 2 hops réels (Code civil → Code de la construction) |
| §5 Rôle LLM | ~65% | `llm.py` | Mécanique opérationnelle avec vrais LLM ; texte exact des 4 règles du prompt B pas repris littéralement |
| §6 Forçage récupération | ✅ 100% | `orchestration.py`, `llm.py` | Satisfait par choix architectural : l'orchestrateur appelle toujours MCP directement (§4 étape 4), jamais le LLM — c'est la voie "backend local sans forçage" explicitement autorisée par §6 comme équivalente au forçage natif, appliquée à tous les backends. `PromptBasedDecomposer`/`PromptBasedIntentGenerator` n'ont donc aucun outil à forcer, code nettoyé en conséquence |
| §6bis Moulineuse | ~85% | `moulineuse.py` | 3 routes prouvées en direct (code_article, pastille refus, texte_libre) ; pastille jamais testée en direct sur un chemin heureux |
| §6ter Opposabilité/data.gouv | ~92% | `datagouv.py`, `moulineuse.py`, `file_retrieval.py` | Sources réelles branchées et prouvées en direct : normatif (Moulineuse), donnée tabulaire (data.gouv API), donnée non-tabulaire (fichiers CSV/ZIP téléchargés — couvre l'INSEE dont la plupart des ressources ne sont PAS dans l'API tabulaire) |
| §7 Vérificateur déterministe | ~95% | `verifier.py`, `normalization.py` | Contiguïté, anti-épissage, opposabilité, anti-troncature (1 bug d'occurrence multiple corrigé) |
| §7bis Refus | 90% | `exceptions.py`, `verifier.py` | Levée systématique, jamais de devinette |
| §8 Registre | ~90% | `audit.py` | `passage_hashes` rejouables, intégré dans la façade unifiée |
| §9 API vs local | N/A | — | Narratif, satisfait par construction (agnostique au provider) |
| §10 Matrice des pièges | ~70% | multiples | A1,A2,A3,B1,B2,B4,C1,C2,E1,E2,E4,F1 traités. **D1-D3,C3,E3 hors de portée du code seul** (jugement humain par construction, cf. §10 de la spec) |
| §12 Mesure | ~95% | `measurement.py`, `trap_dataset.py`, `calibration.py` | Banc réel sur vérificateur+triage : 100% blocage correct, 0% sur-refus, 0% faux négatifs. Kappa de Cohen inter-annotateur implémenté et testé (accord parfait, partiel, désaccord systématique) — reste à exercer avec de vraies annotations humaines sur le gold standard, ce qui est une activité humaine, pas un manque de code |
| §13 Déploiement souverain | ~40% | `sovereign_log.py` | §13.4 (cloisonnement logs) codé et câblé dans `SentinelGuard`. §13.1-13.3,13.5 narratif/DSI, non codable |
| §14 Invariants | ~80% | multiples | Majorité vérifiable par construction/tests. INV-009 narratif, INV-014 pas de scan d'imports dédié |
| §15 Interfaces canoniques | ~95% | `types.py` | Correspondance quasi exacte avec les pseudo-types de la spec |
| §16 Priorité des règles | N/A | — | Respecté par construction du code |
| §17 Dépendances externes | ~75% | `mcp_client.py`, `litellm_provider.py` | `mcp` épinglé. LiteLLM implémenté (`litellm` + `truststore` en optional-dependency `litellm`), vérifié en direct sur Mistral. deepeval/ragas/doccano absents par choix (cohérent INV-014, mesure hors-runtime) |

## Pièges de la matrice §10 — détail

| Piège | Statut | Mécanisme |
|---|---|---|
| A1 — référence inventée | ✅ verrouillé | lookup, `verifier.py` |
| A2 — prémisse fausse | ✅ verrouillé | lookup échoue → refus |
| A3 — référence inférée | ✅ borné | `slot_provenance.py`, élévation auto du risque |
| B1 — citation exacte | ✅ verrouillé | contiguïté, `verifier.py` |
| B2 — citation tronquée | ✅ borné | `_detect_adjacent_truncation`, élévation auto |
| B3 — paraphrase distordue | ✅ borné | ellipsis → `INTERPRÉTATION` |
| B4 — épissage de fragments | ✅ verrouillé | règle de contiguïté stricte |
| C1 — source hors-sujet | ✅ borné | route texte_libre, `pertinence_non_garantie` |
| C2 — source périmée | ✅ borné | `ETAT`/`opposable`, testé avec cas synthétiques |
| C3 — mauvaise juridiction | ❌ non traité | nécessite corpus multi-juridictionnel réel |
| D1 — interprétation déguisée | ❌ hors de portée | jugement humain par construction (spec §10) |
| D2 — synthèse fallacieuse | ❌ hors de portée | idem, limite mathématique explicite |
| D3 — fausse attribution | ❌ hors de portée | idem |
| E1 — N questions → 1 requête | ✅ verrouillé | décomposition, `orchestration.py` |
| E2 — multi-saut non suivi | ✅ verrouillé | bornes §4ter, `retrieval.py` |
| E3 — référent manquant | ❌ non traité | nécessite un tour de dialogue, pas une fonction pure |
| E4 — intention oubliée | ✅ borné | `coverage.py`, élévation auto du risque |
| F1 — verbatim non opposable | ✅ verrouillé | dérivation `opposable`, `CITÉ_NON_OPPOSABLE` |

## Modules (`src/sentinel_guard/`)

| Module | Rôle |
|---|---|
| `types.py` | Pseudo-types canoniques (§15) |
| `normalization.py` | Normalisation texte/numérique (§7) |
| `verifier.py` | Vérificateur déterministe (§7) |
| `triage.py` | Plancher de risque (§2) |
| `coverage.py` | Echo-back + contrôle de couverture (§4 étape 1bis) |
| `slot_provenance.py` | Discriminateur slot copié/inféré (§4bis, A3) |
| `retrieval.py` | Bornes multi-saut génériques (§4ter) |
| `multi_hop.py` | Sélection de renvois réels Moulineuse (§4ter) |
| `mcp_client.py` | Façade synchrone sur le SDK MCP |
| `moulineuse.py` | RetrievalProvider Moulineuse réel (§6bis) : 4 routes — code_article, pastille, texte_libre, parlement_question |
| `datagouv.py` | RetrievalProvider data.gouv API tabulaire (§6ter) |
| `file_retrieval.py` | RetrievalProvider fichiers CSV/ZIP non-tabulaires (§6ter) : télécharge + parse défensivement (détection ZIP/encodage/séparateur), adressage de cellule par filtres multi-colonnes |
| `multi_source.py` | Aiguillage entre les deux sources |
| `orchestration.py` | Boucle principale (§4) |
| `llm.py` | Abstraction LLM, prompts, parsing JSON |
| `gemini.py` / `mistral.py` | Providers LLM réels (wrappers HTTP maison) |
| `litellm_provider.py` | Provider LLM via LiteLLM (§17.1), auto-détection du magasin de certificats OS |
| `human_validation.py` | Registre de décisions humaines (§4 étape 9) |
| `audit.py` | Registre de conformité, hashes rejouables (§8) |
| `sovereign_log.py` | Cloisonnement conformité/accès (§13.4) |
| `core.py` | Façade unifiée `SentinelGuard` |
| `measurement.py` / `trap_dataset.py` | Banc de mesure (§12) |
| `calibration.py` | Kappa de Cohen inter-annotateur, validation du gold standard (§12) |
| `exceptions.py` | Hiérarchie d'exceptions |

## Ce qui reste

### Bugs d'honnêteté d'affichage — CORRIGÉS

Révélés par le test « arrêt Assemblée plénière du 14 avril 2006 » (voir
`ANALYSE_TEST_JURISPRUDENCE.md` pour le détail complet). La garantie de fond était
déjà intacte (aucune hallucination, non-pertinence signalée, résultat non
publiable) ; c'était la **présentation** du résultat qui brouillait le message :

1. **`_compliance_status` renvoyait `VALIDATED` quand 0 claim de réponse était
   produit** (`audit.py`) — `verify_claims([])` donne `verbatim_check=PASS` car
   `all([])==True`. Corrigé : nouvel état `NO_ANSWER`, retourné en priorité quand
   `result.verification.claims` est vide. Test de régression :
   `test_compliance_status_is_no_answer_when_zero_claims`.
2. **Le claim de contrôle d'UI s'affichait même sur une source hors-sujet**
   (`ui/server.py`) — corrigé : masqué quand `pertinence_non_garantie == True`.
3. **L'UI affichait un statut « vert » en bout de chaîne « pertinence non garantie
   + 0 réponse »** (`ui/index.html`) — corrigé : message explicite « ⚠ Le système
   n'a pas pu répondre depuis une source fiable… », statut `NO_ANSWER` rendu en
   orange (distinct du vert VALIDATED et du rouge BLOCKED).

Suite complète : 141 tests passants après correction.

### Structurellement non résoluble par du code seul

- **D1-D3, C3, E3** — la spec elle-même déclare ces pièges limite mathématique/humaine du contrôle déterministe (§10) : interprétation déguisée, synthèse fallacieuse, fausse attribution, mauvaise juridiction, référent manquant nécessitent soit un jugement humain par construction, soit un vrai tour de dialogue, soit un corpus multi-juridictionnel réel.

### Limites de couverture des sources (pas des bugs)

- **Jurisprudence** (Cour de cassation, arrêts + moyens) absente du corpus — Moulineuse expose Légifrance (codes/JORF) + parlementaire, pas les arrêts. Brancher Judilibre / Légifrance jurisprudence serait une extension.
- **XLSX/XLS et ressources pointant vers des pages HTML** non couverts par `FileRetrievalProvider` (CSV/ZIP-CSV uniquement).

La calibration inter-annotateur (§12) a désormais son outillage complet (`calibration.py`, kappa de Cohen testé) ; il ne reste que l'activité humaine elle-même (annoter un sous-ensemble du gold standard avec 2+ annotateurs réels), qui n'est plus un manque de code.

Gemini, Mistral et LiteLLM ont tous été confirmés fonctionnels de bout en bout (décomposition → génération de claims → `AUTHENTIFIÉ`) en conditions réelles.

## Historique des corrections notables

- **Bug de troncature (B2)** : `_detect_adjacent_truncation` ne vérifiait que la première occurrence d'une citation répétée dans un passage, pouvant manquer une troncature sur la bonne occurrence. Corrigé pour vérifier toutes les occurrences.
- **APIs Gemini/Mistral cassées** : URLs et modèles inventés, jamais vérifiés en direct (contrairement à Moulineuse/data.gouv). Corrigées contre les vraies API (endpoints, modèles actuels, format de payload), plus un fix générique de parsing JSON enveloppé en markdown et la désactivation du mode "thinking" de Gemini 2.5 qui tronquait les réponses courtes.
- **Filtre multi-saut trop large** : `select_next_hop` suivait initialement des renvois `MODIFIE` vers des ordonnances JORF non récupérables par la route `code_article`. Corrigé en filtrant aussi sur `@naturetexte == "CODE"`.
- **Conflit `SentinelGuard.confidential`** : un paramètre configurable produisait des entrées de log rejetées par le `SovereignLogStore` (qui refuse toute entrée avec `query` par construction). Résolu en supprimant l'option — utiliser `SentinelGuard` implique le mode souverain par construction.
- **Vestige `tool_choice` incohérent (§6)** : `PromptBasedDecomposer`/`PromptBasedIntentGenerator` calculaient `tool_choice="required" if supports_forced_tool_calling else None` tout en passant systématiquement `tools=[]` — forcer un outil qui n'est jamais déclaré n'a aucun effet. Nettoyé : ces classes n'appellent jamais MCP elles-mêmes (l'orchestrateur le fait toujours en amont), donc `tool_choice=None` sans condition, avec le choix architectural documenté en commentaire.
- **LiteLLM bloqué par l'environnement puis débloqué (§17)** : `litellm.completion()` échouait en `SSL: CERTIFICATE_VERIFY_FAILED` via `httpx`/`certifi`, alors que les wrappers `urllib` de `gemini.py`/`mistral.py` fonctionnaient. Cause confirmée : Avast Antivirus fait de l'inspection HTTPS et installe son certificat racine (`CN=Avast Web/Mail Shield Root`) dans le magasin Windows natif (`Cert:\LocalMachine\Root`, utilisé par `urllib`), jamais dans le bundle Mozilla embarqué de `certifi` (utilisé par `httpx`). `SSL_CERT_FILE` ne suffisait pas. Débloqué avec le paquet `truststore`, qui patche `ssl` pour utiliser l'API native de l'OS (`SChannel` sous Windows) au lieu du bundle certifi — portable sur toute machine avec inspection HTTPS (antivirus ou proxy d'entreprise), sans export manuel de certificat. `LiteLLMModelProvider` l'injecte automatiquement à l'initialisation. Vérifié en direct sur Mistral via LiteLLM.

## Relecture complète — 6 angles morts trouvés et corrigés

Relecture systématique de tous les modules, chaque bug confirmé par un test reproductible en direct puis corrigé avec test de non-régression :

1. **`visited_documents` partagé entre intentions (orchestration.py)** — deux questions légitimes sur le même article faisaient planter tout le pipeline en `Document already visited`. Confusion entre INV-006 (borner le multi-saut *dans* une intention) et INV-002 (étanchéité *entre* intentions). Corrigé : l'état de récupération est réinitialisé par intention, le budget global reste partagé.
2. **Couverture aveugle aux chiffres courts (coverage.py)** — `len(t) > 1` filtrait tous les tokens d'un caractère, rendant "article 6" invisible au contrôle E4 (`ratio=1.0` malgré une intention oubliée). Corrigé : les chiffres isolés sont désormais significatifs.
3. **A3 désarmé sur numéros courts (slot_provenance.py)** — test de sous-chaîne brute : l'article "16" inféré était déclaré "copié" car "16" ⊂ "2016". Corrigé : comparaison par mot entier (tokenisation), en préservant la tolérance au formatage variable ("L. 1232-6" ↔ "L1232-6") et les slots multi-mots.
4. **Faux positifs de troncature (verifier.py)** — `startswith(connector)` sans frontière de mot : "sauferie" déclenchait le drapeau "sauf". Corrigé : vérification de frontière (espace/ponctuation/fin de chaîne) après le connecteur.
5. **Refus jamais journalisé (audit.py + orchestration.py)** — `verify_claims` levait une exception, donc un refus (§7bis) plantait `Orchestrator.run` avant journalisation et `compliance_status="BLOCKED"` était du code mort. Corrigé : l'exception `VerificationError` porte désormais le `VerificationResult` complet, et l'orchestrateur capture le refus pour en faire un résultat BLOCKED journalisable à risque élevé — les autres intentions continuent (schéma §4 étape 8).
6. **McpToolClient non robuste à l'inspection SSL (mcp_client.py)** — le SDK `mcp` utilise `httpx`, donc les appels Moulineuse/data.gouv échouaient en `CERTIFICATE_VERIFY_FAILED` dès qu'Avast inspectait le HTTPS. Corrigé : `ensure_system_trust_store()` factorisé dans `trust.py` et injecté par `McpToolClient` comme par `LiteLLMModelProvider`. Moulineuse revérifié en direct.

## Extensions issues des tests utilisateur

- **Route question parlementaire (§6bis/§6ter)** : `MoulineuseRetrievalProvider.route="parlement_question"` via `get_parlement_item` (QE/QOSD/QG). Non opposable par nature → `CITÉ_NON_OPPOSABLE`, jamais `AUTHENTIFIÉ`. Testé en direct sur la QOSD n°812 : le système a démontré le piège A2 (prémisse fausse) en refusant d'inventer une commune absente du texte officiel.
- **Faux négatif sur les paraphrases fidèles corrigé (§5/§7)** : le vérificateur exigeait un verbatim exact et bloquait toute reformulation correcte en `NON_AUTHENTIFIÉ`. Corrigé sur deux volets : (1) le prompt B distingue désormais citation exacte (`AUTHENTIFIÉ`) et reformulation (`INTERPRÉTATION`) ; (2) le vérificateur accepte une `INTERPRÉTATION` si ses termes sont **ancrés** dans le passage (recouvrement lexical déterministe ≥60%), sinon c'est une invention pure → `NON_AUTHENTIFIÉ`. Le mot `AUTHENTIFIÉ` reste réservé au verbatim exact (§7). Découvert parce qu'un vrai LLM produit des paraphrases, ce que les mocks ne montraient pas.
- **`FileRetrievalProvider` pour les ressources non-tabulaires (§6ter)** : la plupart des ressources INSEE ne sont PAS dans l'API tabulaire de data.gouv (elles pointent vers des fichiers/pages externes). Ce provider télécharge le fichier, détecte défensivement son vrai format (magic bytes — le MIME déclaré ment : INSEE annonce `text/csv` pour un ZIP), extrait le CSV de données (refuse si ambigu), et adresse une cellule par filtres multi-colonnes (refus si 0 ou >1 ligne). Testé en direct : 891 naissances (dép. 06, juillet 2025) → `DONNÉE_TRACÉE`. XLSX/HTML non couverts (limite documentée). Branché dans `MultiSourceRetrievalProvider` (clé `filters`).
- **Démonstrateur web (`ui/`)** : serveur `http.server` stdlib (zéro dépendance web) + page HTML unique. Champ question → décomposition Mistral → récupération réelle (4 routes normatives + 2 routes donnée) → vérification → statuts colorés + journal §8. Lancement : `python ui/server.py` puis http://localhost:8765. Quand le LLM ne produit rien (sur-refus fréquent de mistral-small, §12), un claim de contrôle déterministe extrait du passage démontre visuellement la garantie du vérificateur.
