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
- **Runtime local** : **llama.cpp** (serveur OpenAI-compatible, `logprobs` natif, modèle Mistral GGUF, Metal sur Apple Silicon). Alternative si box GPU Linux : vLLM. Le backend parle OpenAI-compat → runtime interchangeable.
- **Couche 2 (sources)** : serveur **MCP moulineuse** — endpoint réel **`https://mcp.code4code.eu/mcp`** (Streamable HTTP, **pas d'auth**, `mcp-session-id` retourné au handshake). ✅ Testé et fonctionnel le 2026-06-22 (la page `tricoteuses.fr/services/mcp-moulineuse` n'est que la doc ; Anubis ne bloque que les fetchers web, pas un vrai client MCP). On n'écrit aucun parseur XML/CSV : le backend est client MCP.
  - Outils exposés : `search_recipes`/`list_recipes`/`get_recipe` (recettes métier, **commencer par là**), `search_legal_texts` (FTS Typesense `textes_juridiques`), `query_typesense`, `query_sql` (SQL sur la base `canutes`, schémas `assemblee`/`senat`/`annuaire`/`droits_*`), `list_tables`/`describe_table`/`get_json_schemas` (introspection), `list_parlement_items`/`get_parlement_item` (HTTP read-only vers `parlement.tricoteuses.fr`, + résumés IA pour questions/débats), `run_script`/`list_package_schemas`/`get_package_symbol_json_schema`/`get_typescript_types` (scripts TS).
  - Stratégie couche 2 : `search_recipes` → `search_legal_texts` pour le sourçage rapide ; `query_sql` pour les faits structurés (votes, auteurs d'amendement, mandats).
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
[3] Couche source — chaque affirmation interrogée via MCP moulineuse
   │                 (search_legal_texts / query_sql)
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
| `source_layer` | Couche 2 | claim → {statut: vérifié/faux/aucune, source datée} | client MCP moulineuse |
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
- **llama.cpp/vLLM sur Mac** : vLLM tourne mal sur Apple Silicon → llama.cpp retenu. À confirmer au runtime.
- **~~MCP moulineuse derrière Anubis~~** : ✅ résolu — endpoint `https://mcp.code4code.eu/mcp` testé OK, pas d'auth, handshake + tools/list fonctionnels.
- **~~Alignement des spans de logprobs~~** : ✅ résolu par la génération-en-affirmations single-pass (logprobs natifs par affirmation).
- **Bruit des logprobs** : couche 1 peu fiable seule (cf. scénario démo). La couche source porte la démo.
- **Filet offline pour la démo** : pré-charger le dataset du scénario (dump CSV/XML `data.assemblee-nationale.fr`, hors Anubis) en SQLite local, pour ne pas dépendre du réseau MCP pendant le passage jury. Le connecteur MCP reste l'implémentation par défaut ; le dump est le secours.
- **Licence DSFR** : réservée à l'usage de l'État. OK pour un hackathon organisé par l'Assemblée ; ne pas publier publiquement comme si c'était state-endorsed.
