# Analyse — test « arrêt Assemblée plénière du 14 avril 2006 »

Question testée :
> « Dans l'arrêt Assemblée plénière du 14 avril 2006 relatif à la responsabilité
> médicale, quelle était la troisième branche du moyen soulevé par le pourvoi et
> comment la Cour y a-t-elle répondu ? »

C'est un **triple piège** : (1) jurisprudence de la Cour de cassation, absente du
corpus ; (2) détail ultra-précis (« troisième branche du moyen ») qu'un LLM brut
inventerait ; (3) recherche par proximité qui remonte une source réelle mais
hors-sujet (piège C1).

## Comportement observé

- Route détectée : `texte_libre` (aucune référence structurée → recherche libre).
- Source récupérée : `PIONANR5L15B1900` — une **proposition de loi** sur les
  fermetures de lits/GHT, **totalement hors-sujet**, marquée
  `pertinence_non_garantie = True`.
- Décomposition Mistral : **8 intentions** (sur-décomposition).
- Claims produits par le LLM : **0 pour chaque intention** — aucune « branche du
  moyen » inventée, aucune réponse de la Cour fabriquée.
- Risque : **élevé** (automatique, piège C1). Publiable : **NON** (validation
  humaine requise).
- `compliance_status` affiché : **VALIDATED** (← trompeur, voir bugs ci-dessous).

## Ce qui a bien fonctionné (la garantie de fond)

- **Aucune hallucination de génération** : le système n'a produit aucune réponse
  inventée sur les moyens du pourvoi. C'est la garantie centrale (§2/§7).
- **Non-pertinence signalée** : `pertinence_non_garantie` + risque élevé + non
  publiable. Le contrat §1bis (fidélité ≠ pertinence) est respecté : le code ne
  garantit jamais la pertinence, et le dit explicitement.

## Analyse externe (ChatGPT) — ce qui est correct vs incorrect

Une analyse ChatGPT de cette sortie a été versée au dossier. Tri :

### Correct (vrais problèmes)
- **`VALIDATED` trompeur** : suggère un succès alors que rien n'a été validé sur
  le fond. Faux signal positif.
- **Claim de contrôle bruyant** : le claim de démonstration (titre du document
  affiché en `CITÉ_NON_OPPOSABLE ✓`) donne l'illusion d'une preuve sur une source
  hors-sujet.

### Incorrect (affirmations techniquement fausses)
- **« Le système valide une réponse » / « hallucination de récupération »** :
  FAUX. Aucune réponse n'a été produite ni validée. Ce qui est marqué `PASS`, c'est
  le titre de la source elle-même (claim de contrôle d'UI), pas une réponse aux
  « branches du moyen ». ChatGPT confond « le titre existe dans le document »
  (trivial) et « le système a répondu » (faux).
- **« Le warning est cosmétique, pas bloquant »** : FAUX. `pertinence_non_garantie`
  a élevé le risque et rendu le résultat NON PUBLIABLE. Le traitement continue
  (voulu : §10 classe C1 « borné puis délégué », pas « verrouillé »), mais rien
  n'est publiable sans humain.
- **« Mauvais index / root cause retrieval »** : imprécis. Le système n'a qu'une
  source (Moulineuse = Légifrance + parlementaire) qui **ne contient pas** la
  jurisprudence de la Cour de cassation. Ce n'est pas une recherche au mauvais
  endroit, c'est une limite de couverture correctement signalée.

### Point de fond manqué par l'analyse externe
La distinction **fidélité ≠ pertinence** (§1bis) : le code garantit la fidélité
(« ce texte existe mot pour mot »), jamais la pertinence (« c'est la bonne
source »). Reprocher au système de ne pas garantir la pertinence revient à lui
reprocher de ne pas faire ce qu'il annonce explicitement ne pas faire.

## Bugs identifiés — CORRIGÉS

Corrections d'**honnêteté d'affichage** (le fond garanti était déjà intact ; c'est
la présentation du résultat qui brouillait le message) :

1. **`_compliance_status` (audit.py)** : ne renvoie plus `VALIDATED` quand
   0 claim de réponse a été produit. `verify_claims([])` donne `verbatim_check=PASS`
   (`all([])` == True), d'où le `VALIDATED` trompeur. Nouvel état distinct
   `NO_ANSWER` (« Sans réponse » — ni succès ni refus), retourné en priorité avant
   VALIDATED/BLOCKED. Test de régression : `test_compliance_status_is_no_answer_when_zero_claims`
   (tests/test_audit.py).

2. **Claim de contrôle d'UI (ui/server.py)** : ne s'affiche plus quand
   `pertinence_non_garantie == True` (`_run_pipeline`, garde `not pertinence_non_garantie`
   avant de construire `control`). Il n'a de sens démonstratif que sur une source
   pertinente ; sur une source hors-sujet il créait une illusion de preuve.

3. **Affichage UI (ui/index.html)** : quand `pertinence_non_garantie` + 0 claim,
   affiche désormais explicitement « ⚠ Le système n'a pas pu répondre depuis une
   source fiable… » à la place du bloc de contrôle. Le statut `NO_ANSWER` est
   rendu en orange (`warn`), distinct du vert (`ok`, VALIDATED) et du rouge
   (`blocked`, BLOCKED).

Suite complète (141 tests) verte après application des 3 correctifs.

## Limite structurelle (pas un bug)

Le corpus n'inclut pas la jurisprudence de la Cour de cassation. Pour répondre à
ce type de question, il faudrait brancher une source de jurisprudence (Judilibre /
Légifrance jurisprudence) — hors périmètre actuel. Le système révèle cette limite
au lieu de la masquer par une invention.
