# Processus final — Hallucide

> Le pipeline complet, étape par étape, avec le **statut réel d'implémentation**
> vérifié **dans le code source** (pas dans la spec ni la doc). Chaque ✅ renvoie
> à une ligne de code réelle ; chaque ❌ est une évolution prévue, assumée.
>
> Établi le 4 juillet 2026, en relisant `verifier.py` ligne par ligne.

---

## Vue d'ensemble

| # | Étape | Statut |
|---|---|---|
| 1 | L'utilisateur pose sa question | ✅ implémenté |
| 2 | Décomposition en intentions atomiques | ✅ implémenté |
| 3 | Extraction des mots-clés / entités | ✅ implémenté |
| 4 | Récupération des sources officielles (Moulineuse + data.gouv) | ✅ implémenté |
| 5 | Envoi à l'IA (question + sources, prompt-cadre imposé) | ✅ implémenté — ⚠️ pas lancé en live |
| 6 | L'IA génère les affirmations depuis le passage source uniquement | ✅ implémenté |
| 7 | Vérification verbatim déterministe + contrôle d'opposabilité | ✅ implémenté |
| 8 | Contrôles déterministes sur les reformulations (négation, chiffres, lexical, proximité) | ✅ implémenté (embeddings de modèle non retenus) |
| 9 | Vérification factuelle complémentaire (NLI / juge contraint) | ❌ évolution prévue |
| 10 | Plancher de risque | ✅ implémenté |
| 11 | Statut par affirmation + marquage « intervention humaine requise » | ✅ implémenté |
| 12 | Affichage final : réponse annotée, score/couleur, traçabilité | ✅ implémenté — ⚠️ rendu jamais vu en navigateur |

---

## Détail de l'étape 8 (le point le plus subtil)

L'étape 8 attrape les **reformulations** que le mot-à-mot (étape 7) laisse passer.
Elle se décompose en trois sous-parties, dont **deux sont déjà implémentées** :

| Sous-partie | Statut | Preuve (code réel) |
|---|---|---|
| **Path B — checks logiques : négation** | ✅ implémenté + testé | [`verifier.py:118`](../../src/hallucide/_4_verification/verifier.py#L118), [`:130-134`](../../src/hallucide/_4_verification/verifier.py#L130) (`_hard_anchors_hold`) · test `test_interpretation_with_inverted_negation_is_refused` |
| **Path B — checks logiques : chiffres** | ✅ implémenté + testé | [`verifier.py:131-132`](../../src/hallucide/_4_verification/verifier.py#L131) · test « 14 jours vs 10 jours » ([`test_verifier.py:263-271`](../../tests/test_verifier.py#L263)) |
| **Similarité lexicale ≥60%** | ✅ implémenté + testé | [`verifier.py:95`](../../src/hallucide/_4_verification/verifier.py#L95), [`:149-150`](../../src/hallucide/_4_verification/verifier.py#L149) (`overlap ≥ 0.6`) · test `test_unanchored_interpretation_is_refused` |
| **Path A — proximité de reformulation (déterministe)** | ✅ implémenté + testé (4 juillet) | [`semantic_similarity.py`](../../src/hallucide/_4_verification/semantic_similarity.py) : Jaccard tokens + trigrammes de caractères, sans ML ni API · [`tests/test_semantic_similarity.py`](../../tests/test_semantic_similarity.py) (16 cas) |
| **Path A — similarité par embeddings (modèle)** | ❌ non retenu | choix assumé : un embedding réintroduit un score flou de modèle. La version déterministe ci-dessus couvre le besoin sans le flou. |

### Pourquoi le grep `embedding` était vide alors que « Path B » est ✅

Parce que le mécanisme ne s'appelle **pas** « embedding » : il s'appelle
`_hard_anchors_hold`, `_negation_markers`, `overlap`. C'est de la comparaison
**lexicale déterministe**, pas de la similarité **sémantique**. Les deux vérités
coexistent :

- ✅ Path B (négation + chiffres) + ancrage lexical ≥60% → **dans le code ET testé**
- ❌ embeddings sémantiques → **bien absents** (et c'est un choix, pas un oubli)

### Path A implémenté en déterministe (4 juillet)

Plutôt que des embeddings (score flou de modèle), Path A est implémenté comme une
**proximité lexicale calculable** : Jaccard des tokens de contenu + Jaccard des
trigrammes de caractères, dans `semantic_similarity.py`. 100% reproductible, aucun
ML, aucun réseau — deux appels sur les mêmes entrées donnent toujours le même nombre.

**Contrat de sûreté** (respecté par construction, testé) : cette couche ne peut que
**augmenter le risque** — elle marque une reformulation (`INTERPRÉTATION`) jugée trop
éloignée de la source pour passer sans regard humain. Elle n'authentifie **jamais**,
ne rattrape **jamais** un `NON_AUTHENTIFIÉ`, ne touche **jamais** un claim verbatim.

**Branchement (additif, sans modifier le moteur)** : `semantic_floor_conditions(...)`
renvoie une liste de booléens (un par claim) à passer, par un OU logique, dans le
paramètre `floor_conditions` **déjà existant** de `Hallucide.ask`. Le cœur du
moteur n'est pas modifié ; les 175 tests d'origine restent verts, et 16 nouveaux
tests couvrent cette couche.

### Pourquoi pas d'embeddings de modèle

Un embedding donne un score de ressemblance **flou** (« ces phrases se ressemblent
à 87% »), issu d'un modèle. C'est exactement le type de jugement que le moteur
**refuse** : sa thèse est le déterministe. La version lexicale ci-dessus couvre le
même besoin (attraper les reformulations éloignées) **sans** ce flou.

---

## Ce qui n'est PAS implémenté (assumé)

- ❌ **Similarité par embeddings de modèle** (étape 8) — non retenue ; remplacée par la proximité déterministe (voir ci-dessus).
- ❌ **NLI / juge contraint** sur cas ambigus (étape 9) — complément, pas remplacement.
- ❌ **Logprobs** — écarté (voir note ci-dessous).
- ⚠️ **Live jamais lancé** — clé API à brancher.
- ⚠️ **Rendu front jamais vu en navigateur.**

### Note sur les logprobs
Les logprobs sont une **sortie du modèle** (la probabilité qu'il assigne à chaque
token). On ne peut pas les « coder en dur » sans les **inventer** — et inventer un
score de confiance dans un projet anti-hallucination serait exactement la faute
qu'on dénonce. Un vrai logprob se lit sur la réponse de l'API du modèle, il ne se
fabrique pas côté vérificateur.

---

## Invariant transversal (défense en profondeur)

Le vérificateur ne fait **pas confiance** aux étapes d'amont : même si la
récupération marque une source « opposable », si son état n'est pas `VIGUEUR`
(texte abrogé), elle retombe en `CITÉ_NON_OPPOSABLE` — jamais `AUTHENTIFIÉ`.
Preuve : [`verifier.py:162-168`](../../src/hallucide/_4_verification/verifier.py#L162) (`_effectively_opposable`) + [`:191`](../../src/hallucide/_4_verification/verifier.py#L191).
