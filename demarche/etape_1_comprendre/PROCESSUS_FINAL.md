# Processus final — Sentinel Guard

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
| 8 | Contrôles déterministes sur les reformulations | ✅ partiel (voir détail) |
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
| **Path B — checks logiques : négation** | ✅ implémenté + testé | [`verifier.py:118`](../../src/sentinel_guard/_4_verification/verifier.py#L118), [`:130-134`](../../src/sentinel_guard/_4_verification/verifier.py#L130) (`_hard_anchors_hold`) · test `test_interpretation_with_inverted_negation_is_refused` |
| **Path B — checks logiques : chiffres** | ✅ implémenté + testé | [`verifier.py:131-132`](../../src/sentinel_guard/_4_verification/verifier.py#L131) · test « 14 jours vs 10 jours » ([`test_verifier.py:263-271`](../../tests/test_verifier.py#L263)) |
| **Similarité lexicale ≥60%** | ✅ implémenté + testé | [`verifier.py:95`](../../src/sentinel_guard/_4_verification/verifier.py#L95), [`:149-150`](../../src/sentinel_guard/_4_verification/verifier.py#L149) (`overlap ≥ 0.6`) · test `test_unanchored_interpretation_is_refused` |
| **Path A — similarité sémantique (embeddings)** | ❌ évolution prévue | *grep `embedding\|similarity\|cosine` → vide (confirmé)* |

### Pourquoi le grep `embedding` était vide alors que « Path B » est ✅

Parce que le mécanisme ne s'appelle **pas** « embedding » : il s'appelle
`_hard_anchors_hold`, `_negation_markers`, `overlap`. C'est de la comparaison
**lexicale déterministe**, pas de la similarité **sémantique**. Les deux vérités
coexistent :

- ✅ Path B (négation + chiffres) + ancrage lexical ≥60% → **dans le code ET testé**
- ❌ embeddings sémantiques → **bien absents** (et c'est un choix, pas un oubli)

### Pourquoi l'absence d'embeddings est un choix, pas un manque

Un embedding donne un score de ressemblance **flou** (« ces phrases se ressemblent
à 87% »). C'est exactement le type de jugement que le moteur **refuse** : sa thèse
est le déterministe (le texte existe, oui ou non). Une couche sémantique serait
ajoutée **après** le déterministe et pourrait seulement **augmenter** le risque
(jamais authentifier automatiquement) — sinon elle réintroduit le flou qu'on combat.

---

## Ce qui n'est PAS implémenté (assumé)

- ❌ **Similarité sémantique par embeddings** (étape 8, Path A) — après le déterministe.
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
Preuve : [`verifier.py:162-168`](../../src/sentinel_guard/_4_verification/verifier.py#L162) (`_effectively_opposable`) + [`:191`](../../src/sentinel_guard/_4_verification/verifier.py#L191).
