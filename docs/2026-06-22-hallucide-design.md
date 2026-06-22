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
- **Couche 2 (sources)** : serveur **MCP moulineuse** (`https://www.tricoteuses.fr/services/mcp-moulineuse`), accès unifié Parlement + Légifrance + Service Public, temps réel, 14e législature+. Fallback : MCP LegiWatch (`/services/mcp-parlement`) ou REST api-parlement. On n'écrit aucun parseur XML/CSV : le backend est client MCP.
- **Backend** : Python FastAPI. Client modèle local (OpenAI-compat) + client MCP.
- **Frontend** : Vite + React, **DSFR (Système de Design de l'État français)** : Marianne, bleu République `#000091`, composants officiels. Pas de design flompt.

## Architecture / flux
```
Question user
   │
   ▼
[1] Génération — Mistral local répond, on récupère les logprobs par token
   │
   ▼
[2] Decompose — réponse découpée en affirmations atomiques (JSON)
   │             1 appel structured-output au modèle local
   │             chaque affirmation garde ses spans de tokens d'origine
   ▼
[3] Couche logprobs — score de confiance interne par affirmation
   │                   (faible proba moyenne / forte entropie = instable → "inféré")
   ▼
[4] Couche source — chaque affirmation interrogée via MCP moulineuse
   │                 trouvée + datée = vérifié / contredite = faux / rien = incertain
   ▼
[5] Merge + annote — règle de fusion des deux couches → statut final
   │                  vérifié 🟢 / inféré 🟠 / incertain 🔴 + source + score
   ▼
Affichage annoté (jamais de réponse brute non vérifiée)
```

## Composants (unités isolées, interface claire)

| Unité | Rôle | Entrée → Sortie | Dépend de |
|-------|------|-----------------|-----------|
| `llm_client` | Génère + expose logprobs | prompt → texte + logprobs[] | runtime local OpenAI-compat |
| `decomposer` | Découpe en affirmations | texte + logprobs → claims[] (JSON, chacune avec span) | llm_client |
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
Le modèle local hallucine un vote/auteur plausible → la couche logprobs flague l'instable → le MCP Assemblée récupère le vrai vote daté → l'affirmation inventée passe 🔴, la correcte 🟢. Démontre que seule la source démasque une hallucination *confiante*.

## Hors scope (YAGNI pour le PoC)
- Pas d'auth utilisateur, pas de multi-tenant.
- Pas de connecteur générique multi-domaines (un seul connecteur : Assemblée via MCP). L'archive à connecteurs est montrée comme interface, pas implémentée en N sources.
- Pas de cache, pas de persistance. Tout en mémoire le temps de la requête.
- Pas de streaming token-par-token dans l'UI (réponse annotée d'un bloc).

## Risques connus
- **llama.cpp/vLLM sur Mac** : vLLM tourne mal sur Apple Silicon → llama.cpp retenu. À confirmer au runtime.
- **MCP moulineuse derrière Anubis (anti-bot)** : le fetcher web est bloqué ; un vrai client MCP devrait passer. À tester en priorité jour 1.
- **Découpe en affirmations + alignement des spans de logprobs** : non trivial. Le decomposer doit re-mapper chaque affirmation sur les tokens d'origine pour scorer la couche 1.
