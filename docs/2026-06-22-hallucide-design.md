# Hallucide — Design (PoC)

Hackathon "IA et Hallucination", défi Assemblée nationale. Porteur : Hamza Konte.

## Nom
**Hallucide** : *hallucination* + *-cide* (tuer, comme pesticide) + écho *lucide* (lucidité). Le tueur d'hallucinations qui rend l'IA lucide. Vérifié libre sur "<nom> AI".

## Problème (consigne)
Les IA génératives produisent des réponses inexactes ou non sourcées, et hallucinent jusqu'à leurs propres justifications : une illusion de fiabilité sans ancrage réel. En contexte institutionnel, distinguer une info vérifiée d'un contenu généré est difficile.

## Solution
Un **middleware de confiance** entre l'IA et l'utilisateur. La réponse est interceptée avant affichage, découpée en affirmations atomiques, puis passée par deux couches complémentaires, et n'est affichée qu'annotée : **vérifié / inféré / incertain**.

Thèse centrale : les deux couches sont complémentaires, pas redondantes.
- Les **logprobs** captent l'invention *instable* (le modèle hésite en écrivant).
- Seule la **source datée** démasque les erreurs *apprises confiantes* et les faits obsolètes (le modèle est sûr mais faux ou périmé).

## Décisions verrouillées
- **Scope** : PoC (preuve de concept), slice fonctionnelle la plus rapide. Pas production.
- **Modèle** : Mistral **local** (pas de cloud). Vrais logprobs. Narratif IA souveraine on-prem.
- **Hardware** : VPS **CPU-only** — AMD Ryzen 9 3900x, 4 vCores @ 4.6GHz, 32 Go RAM DDR4, 300 Go NVMe, 750 Mbps. **Pas de GPU** → mistral-inference et vLLM exclus (tous deux GPU/CUDA obligatoire).
- **Runtime** : **llama.cpp** (moteur CPU). Charge un modèle **Mistral GGUF**, expose les **logprobs** (`n_probs` sur `/completion`, ou `logprobs`/`top_logprobs` sur l'endpoint OpenAI-compat `/v1/chat/completions`). Backend FastAPI parle OpenAI-compat au serveur llama.cpp local.
  - Distinction clé : **modèle** (Mistral) et **runtime/moteur** (llama.cpp) sont orthogonaux. llama.cpp ≠ Llama : c'est un moteur CPU qui charge des poids Mistral. Le modèle reste 100% Mistral.
  - **Modèle retenu : Mistral-7B-Instruct GGUF Q4_K_M** (~4,5 Go RAM, ~5-10 tok/s sur ce CPU) — compromis vitesse/qualité pour la démo. Alternatives qui tiennent en 32 Go : Ministral-8B Q4, ou Mistral-Small-24B Q4 (~14 Go, ~2-3 tok/s, plus lent).
- **Couche 2 (sources)** : **open data officiel Assemblée nationale, chargé en SQLite local.** Source officielle, offline, sous notre contrôle, zéro dépendance tierce en démo. Narratif jury : "on ancre sur VOTRE open data officielle".
  - Datasets (data.assemblee-nationale.fr) pour le scénario vote/député :
    - **Députés en exercice** — `/acteurs/deputes-en-exercice` (CSV/XML)
    - **Votes députés 17e** — `/travaux-parlementaires/votes` (XML/JSON)
    - **Amendements 17e** — `/travaux-parlementaires/amendements/tous-les-amendements` (XML/JSON)
  - Ingestion : télécharger les dumps → parser → **SQLite local** (+ table FTS5 pour la recherche plein texte). Étape one-shot au setup, pas pendant la requête.
  - Couche 2 au runtime : chaque affirmation → requête SQLite locale (clé/valeur sur entités : nom du député, n° de scrutin, position de vote ; FTS5 pour le texte).
  - **Archi générique à connecteurs** : interface `SourceConnector` ; une impl concrète = `AssembleeOpenData` (SQLite officiel). Le **MCP moulineuse** (`https://mcp.code4code.eu/mcp`, testé OK, pas d'auth) reste un **2e connecteur optionnel** pour élargir la couverture, pas requis pour le PoC.
- **Backend** : Python FastAPI. Client modèle local (OpenAI-compat) + client MCP.
- **Frontend** : Vite + React, **DSFR (Système de Design de l'État français)** : Marianne, bleu République `#000091`, composants officiels. Pas de design flompt.

## Architecture / flux

**Décision clé — génération-en-affirmations (single-pass).** On NE génère PAS une prose puis un re-découpage : les affirmations re-générées sont des paraphrases, leurs tokens ne se remappent pas sur les logprobs d'origine (couche 1 cassée). À la place, le modèle local répond **directement sous forme de tableau JSON d'affirmations atomiques**. Chaque affirmation est ainsi composée de **ses propres tokens**, dont les logprobs sont natifs → aucun ré-alignement, le risque le plus dur disparaît. La consigne ("signaler les passages peu fiables") est satisfaite : chaque affirmation est un passage.

```
Question user
   │
   ▼
[1] Génération-en-affirmations — Mistral local répond en JSON: [{claim, tokens, logprobs}, ...]
   │   (un seul appel ; logprobs natifs par affirmation)
   ▼
[2] Couche logprobs — score de confiance interne par affirmation
   │                   (faible proba moyenne / forte entropie = instable → "inféré")
   ▼
[3] Couche source — chaque affirmation interrogée sur SQLite local (open data officiel)
   │                 (lookup entités + FTS5)
   │                 trouvée + datée = vérifié / contredite = faux / rien = incertain
   ▼
[4] Merge + annote — règle de fusion des deux couches → statut final
   │                  vérifié 🟢 / inféré 🟠 / incertain 🔴 + source + score
   ▼
Affichage annoté (jamais de réponse brute non vérifiée)
```

*Repli si la génération-en-JSON dégrade trop la qualité des réponses : prose + découpage déterministe en phrases avec suivi des offsets de tokens (granularité plus grossière, alignement plus simple que le re-découpage abstractif).*

## Composants (unités isolées, interface claire)

| Unité | Rôle | Entrée → Sortie | Dépend de |
|-------|------|-----------------|-----------|
| `llm_client` | Génère en JSON + expose logprobs | prompt → claims[] (texte + logprobs natifs par affirmation) | runtime local OpenAI-compat |
| `confidence_layer` | Couche 1 | claim + ses logprobs → score [0,1] + flag instable | — |
| `ingest` (setup) | DL + parse dumps → SQLite | dumps XML/CSV officiels → base SQLite + FTS5 | open data Assemblée |
| `source_layer` | Couche 2 (interface `SourceConnector`) | claim → {statut: vérifié/faux/aucune, source datée} | `AssembleeOpenData` (SQLite local) |
| `merger` | Fusion des 2 couches | claim + score + verdict source → statut final | — |
| `api` (FastAPI) | Orchestration | question → réponse annotée (JSON) | tout ci-dessus |
| `frontend` (React/DSFR) | Affichage annoté | JSON → UI colorée + sources | api |

## Règle de fusion (merger)
| Couche 1 (logprobs) | Couche 2 (source) | Statut final |
|---------------------|-------------------|--------------|
| stable | source confirme | 🟢 vérifié |
| stable | source contredit | 🔴 faux (priorité source) |
| stable | aucune source | 🟠 inféré (confiant mais non ancré) |
| instable | source confirme | 🟢 vérifié (source l'emporte) |
| instable | aucune source | 🔴 incertain |

Principe : **la source datée prime toujours** sur la confiance interne. Les logprobs ne servent qu'à qualifier le non-sourçable.

## Scénario démo (jury)
Question type : *"Le député X a-t-il voté pour la loi Y ?"* ou *"Qui a déposé l'amendement Z ?"*.
Le modèle local hallucine un **fait à entité précise** (nom de député inventé, mauvais numéro/date de scrutin) → le MCP Assemblée récupère le vrai vote daté → l'affirmation inventée passe 🔴, la correcte 🟢.

**La couche source est la pièce maîtresse visible ; la couche logprobs est le garnish ("attrapé avant même de vérifier").** Raison : les logprobs sont bruités (les valeurs basses tracent souvent un choix de synonyme/formulation, pas un doute factuel ; et — c'est la thèse — une hallucination *confiante* score haut). Donc :
- Choisir une question où la fabrication est une **entité spécifique** (nom/nombre/date) où l'entropie pique vraiment.
- **Pré-tester** que le modèle local quantizé hallucine bien CE fait précis de façon reproductible avant la démo.

## Hors scope (YAGNI pour le PoC)
- Pas d'auth utilisateur, pas de multi-tenant.
- Pas de connecteur générique multi-domaines (un seul connecteur : Assemblée via MCP). L'archive à connecteurs est montrée comme interface, pas implémentée en N sources.
- Pas de cache, pas de persistance. Tout en mémoire le temps de la requête.
- Pas de streaming token-par-token dans l'UI (réponse annotée d'un bloc).

## Risques connus
- **Débit CPU** : Mistral-7B Q4 sur 4 vCores → ~5-10 tok/s. Réponses de démo courtes pour rester fluide. Pré-charger le modèle au boot (pas de cold start pendant la démo).
- **~~Alignement des spans de logprobs~~** : ✅ résolu par la génération-en-affirmations single-pass (logprobs natifs par affirmation).
- **Bruit des logprobs** : couche 1 peu fiable seule (cf. scénario démo). La couche source porte la démo.
- **Source 100% locale** : open data officiel pré-chargé en SQLite → **aucune dépendance réseau pendant la démo jury**. (Le MCP moulineuse, testé OK, reste un connecteur optionnel.)
- **Parsing XML open data** : les dumps Assemblée sont volumineux et imbriqués. Limiter l'ingestion aux datasets du scénario (députés + votes 17e), pas toute la base.
- **Licence DSFR** : réservée à l'usage de l'État. OK pour un hackathon organisé par l'Assemblée ; ne pas publier publiquement comme si c'était state-endorsed.
