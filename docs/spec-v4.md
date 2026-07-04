# Spécification Technique : Sentinel-Guard (v4 — orchestrateur agnostique, coutures durcies, mode document)

> **Journal des modifications v3 → v4** (ne re-vérifier que ces points) :
> * **§7ter (nouveau)** — **Mode document** : la sortie peut être un document composé
>   de claims (`DocumentDraft`), en trois modes — **analyse**, **synthèse**,
>   **production** — chacun avec son profil de contrôles et son plancher de risque.
>   Un document n'a jamais de statut agrégé : chaque claim garde le sien.
> * **§2** — le plancher de risque force `élevé` pour tout document en mode
>   production, et en mode synthèse d'une source normative.
> * **§10** — piège nouveau nommé : **B5** (synthèse à trou — omission silencieuse),
>   fermé par le contrôle de couverture documentaire (§7ter).
> * **§12** — le taux de sur-refus est mesuré **par mode document** (un seuil unique
>   calibré pour la production bloquerait toute synthèse).
> * **§14** — invariants **INV-015 à INV-017**.
> * **§15** — types `DocumentMode`, `DocumentDraft`, `CoverageMap`.

> **Journal des modifications v2 → v3** (ne re-vérifier que ces points) :
> * **§1bis / §6ter / §7 / §15** — nouvelle dimension **opposabilité** : un verbatim
>   exact sur une source non opposable (débat, exposé des motifs, amendement rejeté)
>   ne reçoit plus `AUTHENTIFIÉ` mais `CITÉ_NON_OPPOSABLE`. Corrige le trou le plus
>   grave de v2 (le label « confirmé » pouvait coiffer un texte sans valeur normative).
> * **§2** — le triage de risque devient `max(triage_LLM, plancher_code)` : un faux
>   négatif de triage ne peut plus désarmer le filet humain.
> * **§4** — restitution (echo-back) des N intentions avant réponse ; contrôle de
>   couverture de la décomposition.
> * **§7** — règle de **contiguïté** (`AUTHENTIFIÉ` = un seul segment contigu),
>   anti-épissage, et **vérificateur de valeur** pour la donnée chiffrée.
> * **§8 / §13.4** — `passage_hashes` ajouté : preuve d'audit **rejouable**.
> * **§10** — deux pièges nouveaux nommés : **A3** (référence inférée mais fausse),
>   **B4** (épissage de fragments vrais).
> * **§12** — mesure du **taux de sur-refus** + métriques par type de piège + calibration
>   inter-annotateur.
> * **§14** — invariants **INV-010 à INV-014**.
> * **§17 (nouveau)** — dépendances externes (modules GitHub) et frontière de fiabilité.

## 1. Vue d'ensemble

**Sentinel-Guard** n'est pas une extension de navigateur : c'est un **orchestrateur de gouvernance** qui s'intercale entre le client et le moteur de génération. Il exécute lui-même, **côté serveur**, un contrôle de fidélité documentaire (cf. glossaire §1bis), indépendamment du modèle utilisé.

Le moteur de génération (API d'un fournisseur ou LLM local) est un **composant interchangeable**. La garantie de fidélité repose sur le code de l'orchestrateur, jamais sur la discipline du modèle.

```text
Client  ──►  Sentinel-Guard (orchestrateur)  ──►  Moteur de génération (pluggable)
                    │                                      ▲
                    ├──► Client MCP → Tricoteuses/Moulineuse│
                    └──► Vérificateur déterministe ────────┘
```

---

## 1bis. Glossaire — ce que chaque mot promet (à lire en premier)

Le vocabulaire est défini **une seule fois ici**, et tout le reste du document s'y conforme. Trois niveaux distincts, à ne jamais confondre. Un seul est garanti par du code.

| Niveau | Ce qui est affirmé | Qui le prouve | Terme réservé |
| --- | --- | --- | --- |
| **Fidélité** | la citation existe **à l'identique** dans la source récupérée | **code déterministe** | `AUTHENTIFIÉ` |
| **Pertinence** | c'est la **bonne** source pour cette question | récupération + humain | *non garanti* |
| **Interprétation** | la conclusion juridique tirée est correcte | **humain expert** | *non opposable* |

Règles d'emploi strictes dans tout le document :

* Les mots **« garanti », « authentifié », « vérifié »** ne s'appliquent **qu'à la ligne Fidélité**. Jamais à la pertinence, jamais à l'interprétation.
* La promesse centrale du système se formule donc précisément : **« la garantie de fidélité documentaire est indépendante du modèle utilisé »** — et rien de plus large.
* « Anti-hallucination » est un objectif, pas une garantie : le système *réduit fortement* le risque, il ne l'annule pas (voir la matrice §10).
* La ligne **Fidélité** a deux déclinaisons selon le type de source (§6ter) : `AUTHENTIFIÉ` pour un texte (citation = passage, mot pour mot) et `DONNÉE_TRACÉE` pour une donnée chiffrée (valeur = cellule d'un dataset, à telle version). Les deux sont prouvés par du code ; aucune ne touche la pertinence ni l'interprétation.
* **(v3) Opposabilité.** La fidélité prouve que les mots existent dans la source ; elle ne dit rien de l'**autorité** de cette source. Un verbatim exact tiré d'un débat, d'un exposé des motifs ou d'un amendement rejeté est *fidèle* mais *non opposable*. Le label `AUTHENTIFIÉ` est donc réservé aux sources **opposables** (texte en vigueur / consolidé) ; un verbatim sur source non opposable reçoit `CITÉ_NON_OPPOSABLE` (§7).
* **Pour implémenter :** les contraintes machine-actionnables (invariants, types, priorité des règles) sont en **Partie normative §14–§16**. En cas de doute, elles font foi sur les sections narratives.

---

## 2. Principe architectural fondateur

> **La garantie de fidélité documentaire vient du vérificateur déterministe de l'orchestrateur, pas du jugement du modèle.**

Conséquence directe (formulée selon le glossaire §1bis) : la taille du modèle n'affecte **pas la fidélité** — qu'une citation existe à l'identique dans la source est prouvé par le code, pas par le modèle. Un petit modèle local et une grande API produisent donc la **même garantie de fidélité** ; ils ne diffèrent que sur la *fluidité*, l'*utilité* et la *pertinence* des réponses. Ce qui est indépendant du modèle, c'est la fidélité — pas la pertinence ni l'interprétation, qui restent du ressort de la récupération et de l'humain.

**(v3) Triage de risque à plancher déterministe.** Le triage faible/élevé (§4, étape 2) ne peut pas dépendre du seul jugement d'un LLM : un faux négatif (élevé classé faible) désarmerait silencieusement la validation humaine. La règle est donc `risk_tier = max(triage_LLM, plancher_code)`, où le plancher force `élevé` dès qu'un des éléments suivants est présent : un claim `INTERPRÉTATION` ou `CITÉ_NON_OPPOSABLE`, une route texte libre (§4bis), un drapeau anti-troncature (§7), une donnée chiffrée insérée dans un énoncé à tonalité normative (§6ter), un cas D2/D3 (§10), **(v4)** un document en mode **production**, ou un document en mode **synthèse** dont la source est normative (§7ter). Le triage ne peut jamais descendre sous le plancher (INV-011).

---

## 3. Abstraction du moteur (le point d'agnosticité)

L'orchestrateur ne parle qu'à une **interface**, jamais à un fournisseur précis. Tout backend qui l'implémente est utilisable sans changer une ligne de la logique de gouvernance.

```text
interface ModelProvider {
  generate(messages, tools, tool_choice) -> { text, tool_calls }
  supportsForcedToolCalling: bool   // capacité réelle, pas supposée
}
```

| Backend                         | `supportsForcedToolCalling` | Stratégie de forçage                          |
| ------------------------------- | --------------------------- | --------------------------------------------- |
| API compatible OpenAI/Anthropic | `true`                      | `tool_choice: "required"` natif               |
| LLM local (Ollama/llama.cpp…)   | souvent `false`             | **Forçage par l'orchestrateur** (voir §6)     |

L'orchestrateur **n'assume jamais** qu'un backend force les outils : il lit `supportsForcedToolCalling` et applique le forçage natif si disponible, sinon son propre forçage logiciel. Le contrat de gouvernance reste identique dans les deux cas. *L'implémentation concrète recommandée de cette interface est LiteLLM (§17).*

---

## 4. Schéma de flux (identique quel que soit le backend)

Le principe directeur est **1 question → 1 intention → 1 requête → 1 vérification**. Jamais N→1 : fusionner plusieurs questions en une seule recherche détruit la traçabilité « cette citation répond à cette question » *avant même* la génération (cf. §4bis).

```text
0. Message reçu (peut contenir PLUSIEURS questions)
        ↓
1. DÉCOMPOSITION en intentions atomiques (LLM)
   N questions → N intentions séparées, jamais fusionnées
        ↓
1bis. (v3) ECHO-BACK : restitution des N intentions à l'utilisateur
   + contrôle de couverture (la concaténation des intentions couvre le message)
        ↓
   ┌──────────  POUR CHAQUE intention, isolément :  ──────────┐
   │                                                          │
   │ 2. Triage du risque = max(LLM, plancher_code) (§2)       │
   │        ↓                                                  │
   │ 3. Formulation de la requête (LLM) — structurée si        │
   │    possible (slots typés), texte libre en repli (§4bis)  │
   │        ↓                                                  │
   │ 4. Récupération MCP, éventuellement EN BOUCLE             │
   │    (multi-saut : article → décret d'application…)        │
   │    bornes déterministes — voir §4ter                     │
   │        ↓                                                  │
   │ 5. Passages officiels extraits ──┐ conservés en mémoire   │
   │        ↓                         │ (requis pour l'étape 8)│
   │ 6. Génération CONTRAINTE         │                        │
   │    (passages injectés)           │                        │
   │        ↓                         │                        │
   │ 7. Sortie du modèle              │                        │
   │        ↓                         │                        │
   │ 8. CONTRÔLE VERBATIM (code) ◄────┘                        │
   │    chaque citation ↔ passage extrait + opposabilité       │
   │        ↓                                                  │
   │   ┌── échec ──► REFUS sécurisé (§7bis) pour CETTE intention│
   │   │                                                       │
   │ 9. [risque élevé] Validation humaine                     │
   └──────────────────────────────────────────────────────────┘
        ↓
10. Recomposition : une réponse par intention, chacune avec
    son propre statut (AUTHENTIFIÉ / CITÉ_NON_OPPOSABLE / REFUS /
    ESCALADE) + journalisation (§8)
```

Trois points critiques :

* **Étape 1 (décomposition).** Sans elle, six questions posées d'un coup produisent une seule requête fourre-tout, et le rédacteur pioche des passages récupérés pour la question A à l'appui de la question B — la condition idéale du piège « citation réelle mais hors-sujet ». La décomposition garantit qu'une intention ne peut être servie que par les passages récupérés *pour elle*.
* **(v3) Étape 1bis (echo-back + couverture).** La décomposition est faite par un LLM et n'a aucun équivalent du verbatim pour la rattraper : une intention oubliée = une question silencieusement non répondue que l'utilisateur croit traitée. On ferme ce trou par deux garde-fous : un contrôle de couverture (la concaténation des intentions couvre le message source) et, si N>1, la restitution des intentions à l'utilisateur avant de répondre.
* **Étape 4 (récupération).** C'est **l'orchestrateur** qui appelle MCP, jamais le modèle directement. Le modèle ne reçoit que des passages déjà récupérés ; il ne peut donc pas halluciner l'existence d'une source. Le LLM intervient *avant* (formuler la requête) mais ne décide jamais *ce qui est affirmé* — seulement *où chercher*.

---

## 4bis. Formulation de requête : structurée par défaut, texte libre en repli assumé

C'est le maillon faible identifié en test. Une requête en **texte libre** récupère par proximité sémantique : elle peut remonter un passage *réel mais hors-sujet* (ex. le délai de rétractation de 14 j du Code de la consommation pour une question d'achat immobilier, qui relève en réalité des 10 j du CCH). Le verbatim valide alors une citation **fidèle mais non pertinente**.

Politique :

| Mode                   | Quand                                                 | Propriété                                       |
| ---------------------- | ----------------------------------------------------- | ----------------------------------------------- |
| **Structuré** (défaut) | champs sûrs identifiables (code, n° d'article, date)  | numéro inexistant → **lookup échoue → refus**   |
| **Texte libre** (repli)| aucun champ sûr (question en langage naturel)         | couverture +, **assurance −**, marqué comme tel |

Règle : le texte libre n'est jamais interdit (il assure la couverture), mais une réponse qui en découle est **explicitement marquée « pertinence non garantie »** et exposée avec ses passages d'ancrage, pour inspection humaine. La **fidélité** (la citation existe dans la source) et la **pertinence** (c'est la bonne source) sont deux propriétés distinctes : le code garantit la première, jamais la seconde.

**(v3) Slot inféré vs slot copié.** Le danger propre de la route structurée n'est pas le numéro *inexistant* (déjà géré : lookup échoue → refus), mais le numéro *existant mais faux* choisi par le LLM, qui récupère un mauvais article réel, le matche verbatim, et l'expose comme `AUTHENTIFIÉ`. Discriminateur déterministe : la valeur du slot figure-t-elle dans la question de l'utilisateur ? **Copiée** → confiance ; **inférée** (absente de la question) → marquage « référence inférée, pertinence non garantie » + escalade. Ceci ne *prouve* pas la bonne référence ; il isole le sous-ensemble dangereux (piège A3, §10).

---

## 4ter. Récupération multi-saut : bornes déterministes

Le multi-saut (article → décret d'application → …) est nécessaire mais dangereux : laissé flou (« budget de tentatives »), il varie selon le backend et peut produire boucles, chaînes infinies, ou récupérations opportunistes « pour trouver quelque chose qui colle ». La boucle est donc **bornée par du code, pas par le modèle** :

```text
max_hops            = 3        # profondeur maximale de la chaîne de renvois
visited_documents   = set()    # aucun document re-récupéré deux fois
budget_tokens       = <plafond fixe>
stop_conditions:
  - hop_count >= max_hops
  - aucune NOUVELLE référence extraite au dernier saut
  - budget_tokens dépassé
on_stop_sans_réponse → REFUS (§7bis), jamais "rapprochement opportuniste"
```

Propriété clé : à corpus et requête identiques, la chaîne de récupération est **reproductible** quel que soit le backend. Le LLM peut *proposer* le prochain saut (c'est de l'intelligence, §5), mais c'est l'orchestrateur qui *décide* d'arrêter — et l'arrêt sans référence nouvelle conduit au refus, pas à un passage « à peu près pertinent ».

---

## 5. Rôle du LLM : intelligence partout, autorité nulle part

Principe directeur :

> **Des LLM interviennent partout dans le pipeline — décomposer, formuler, rédiger.** Ce qui est interdit au LLM, ce n'est pas de *réfléchir*, c'est d'avoir le *dernier mot sur la vérité*. Aucune affirmation n'est publiée sans passer un contrôle déterministe (§7) qui, lui, ne contient aucun LLM. Le LLM a l'intelligence ; le code a l'autorité.

Le LLM joue donc deux rôles distincts, avec deux prompts.

**Prompt A — Décomposition (étape 1).** Le LLM a le droit d'analyser et de séparer les intentions ; il n'affirme rien sur le fond.

```text
Le message peut contenir PLUSIEURS questions. Découpe-le en intentions
atomiques. Ne fusionne JAMAIS deux intentions. Ne réponds rien sur le fond.
Réponds UNIQUEMENT par un tableau JSON :
[ {"id":1,"question":"<une seule question>"}, ... ]
```

**Prompt B — Rédaction contrainte (étape 6), en rôle `system`.** Appliqué à *une* intention, avec ses passages déjà récupérés.

```text
Tu rédiges la réponse à UNE question, à partir EXCLUSIVEMENT des passages
officiels fournis ci-dessous.
1. INTERDICTION DE CITER HORS CONTEXTE : toute référence absente des passages
   fournis est interdite.
2. REFUS : si les passages ne permettent pas de répondre, réponds exactement :
   [REFUS_VÉRIFICATION] : Impossible d'établir une réponse à partir des sources officielles disponibles pour cette question.
3. TRAÇABILITÉ : chaque affirmation cite l'identifiant officiel du passage qui la fonde.
4. CITATION vs PARAPHRASE : mets entre guillemets uniquement le texte repris mot
   pour mot ; tout reformulé est présenté comme synthèse (non opposable).
```

**Note essentielle :** ces prompts améliorent la *coopération* du modèle, ils ne **sont pas** la garantie. La garantie est le contrôle verbatim (§7). Même un modèle qui ignore ces consignes — ou un petit modèle local qui les suit mal — est rattrapé par le vérificateur déterministe. C'est ce qui permet d'assumer un LLM aux étapes 1, 3 et 6 sans céder sur l'intégrité.

> Le message de refus est volontairement **agnostique à la source** (« pour cette question »), et non rattaché à un registre nommé : l'orchestrateur peut être branché sur l'open data de l'Assemblée, data.gouv ou un autre corpus officiel sans changer le prompt.

---

## 6. Forçage de la récupération (agnostique)

* **Backend avec forçage natif :** `tool_choice: "required"` sur l'outil `search_tricoteuses` dès qu'une intention juridique est détectée.
* **Backend local sans forçage :** l'orchestrateur **exécute lui-même** la requête MCP *avant* d'appeler le modèle, et injecte les passages dans le contexte. Le modèle n'a alors physiquement pas d'autre matière que les passages officiels.

Dans les deux cas, le résultat est le même : **aucune génération ne commence sans passages officiels en main.** `tool_choice: required` force *l'appel* mais pas sa *pertinence* — c'est pourquoi la logique de refus (§7) reste obligatoire même quand le forçage natif est disponible.

---

## 6bis. Source de référence : Tricoteuses / Moulineuse

Première source branchée, **recommandée par l'Assemblée nationale pour le hackathon** (fournisseur « Assemblée nationale & communauté »). C'est une **couche d'unification** au-dessus des sources officielles : open data AN + Sénat + **DILA/Légifrance** (LEGI codes consolidés, JORF, DOLE). Mise à jour « plusieurs fois par jour, temps réel sur certaines données ». L'autorité ultime reste donc Légifrance/JORF ; Moulineuse la réexpose unifiée en MCP. *Note de portée : étant une ressource « retravaillée », elle convient à la ligne Fidélité tant qu'elle restitue le texte officiel à l'identique — propriété à recontrôler par échantillon, pas à présumer (recoupement Légifrance possible via §17).*

### Mapping outils → rôles (vérifié sur schémas réels)

| Outil MCP | Rôle | Glossaire §1bis |
| --- | --- | --- |
| `get_pastilled_article` (`article`, `chambre`, `alinea?`, `date?`, `documentUid`/`sourceUrl`) | récupération **structurée** jusqu'à l'alinéa pastillé | **Fidélité → AUTHENTIFIÉ** |
| `get_parlement_item` (`id`, `resource`) | détail exact d'un objet (amendement, question, débat) | Fidélité + statut (selon opposabilité) |
| `search_legal_texts` (`query`) | recherche plein-texte Typesense (proximité) | **Pertinence → *non garanti*** |
| `query_sql` / `describe_table` / `list_tables` | contrôles **déterministes non-IA** (existence, statut, version) | Contrôle §7 |
| `add_links` (`text`, `date`) | résolution de renvois → **multi-saut** (§4ter) | récupération |
| `run_script` (Deno) | puissant — **jamais l'autorité**, seulement l'intelligence | — |
| `search_recipes` | orientation du choix d'outil | méta (étape formulation §5) |

### Deux routes de récupération distinctes (à ne pas confondre)

* **Article parlementaire** (projet/proposition de loi, amendement, *pastillé*) → `get_pastilled_article`. Exige un `documentUid`/`sourceUrl` précis : il **refuse** sans identifiant de document — comportement sûr, mais qui impose une étape de résolution du document en amont.
* **Article de code consolidé** (« Article 1103 du Code civil ») → **route SQL, prouvée live.** Pas via `search_legal_texts` (la FTS n'indexe que les textes JORF). Les articles consolidés vivent dans `legifrance.article` (`num`, `@cid` du texte parent, `ETAT`, `DATE_DEBUT`/`DATE_FIN`, `BLOC_TEXTUEL.CONTENU`), interrogeable par **`query_sql`** ; méthode documentée par la recette `legifrance_retrouver_article_code_en_vigueur`. **Test réel :** l'art. 1103 du Code civil renvoie `LEGIARTI000032040777`, `ETAT = VIGUEUR`, version `2016-10-01`, et le texte exact « Les contrats légalement formés tiennent lieu de loi… » — soit tout ce qu'exige `AUTHENTIFIÉ` (identifiant + verbatim + état). C'est **multi-étapes (normaliser le n°, résoudre le bon code, filtrer la version), pas un appel unique** : à intégrer comme tel, mais la faisabilité est acquise.

Le paramètre **`date` (`YYYY-MM-DD`)** des outils permet une résolution *à une date donnée* : c'est le levier propre pour la logique de version/consolidation (§3) et le piège C2 (donnée périmée), plutôt que l'âge de la source.

### Validation empirique (test live, à montrer au jury)

* `search_legal_texts("congé menstruel")` → renvoie des **ordonnances de 1943-1962 sur le congé militaire**, réelles et citables, mais **totalement hors-sujet** : le moteur a matché le seul mot « congé ». **C1 reproduit en conditions réelles** — fidélité parfaite, pertinence nulle. D'où l'obligation de marquer la voie texte libre « pertinence non garantie ».
* `get_pastilled_article("1er", "assemblee")` sans document → **refus** : « requiert `documentUid` ou `sourceUrl` ». La route structurée ne devine jamais ; elle exige l'identité exacte.
* `search_legal_texts("article 1103 Code civil")` → **2 résultats hors-sujet** (un décret de 1991 sur le code de l'aviation civile). **Mais la route SQL fonctionne** : `query_sql` sur `legifrance.article` a renvoyé l'art. 1103 (`LEGIARTI000032040777`, `ETAT = VIGUEUR`, version 2016-10-01, texte verbatim exact). La route `AUTHENTIFIÉ` pour les codes est donc **prouvée**, simplement multi-étapes.
* **Bonne nouvelle (piège C2).** Chaque article porte `ETAT` (`VIGUEUR` / abrogé), des dates `DATE_DEBUT`/`DATE_FIN` et un `Echeancier` : l'état et la version à une date sont des métadonnées récupérables → détection « texte abrogé / périmé » **déterministe**. *Distinction fine : « en vigueur » ≠ « effectivement applicable » — un article peut être en vigueur mais attendre son décret d'application ; à signaler, pas à trancher par le modèle.*
* **Corroboration externe.** Les recettes officielles de Tricoteuses implémentent **exactement la même discipline que cette spec** : vérifier qu'une expression figure réellement dans le texte avant de l'affirmer (`position(expression IN texte) = 0 → ne pas appliquer`), citer la version par date, distinguer publié/consolidé, afficher un niveau de confiance et une rubrique « Limites ».

---

## 6ter. Multi-administration : deux types de source, une garantie

Le produit vise plusieurs administrations et plusieurs commissions. L'orchestrateur étant agnostique à la source, c'est une **extension de configuration**, pas d'architecture. Mais une distinction structurante s'impose : **texte normatif ≠ donnée chiffrée**, car la « fidélité » n'y veut pas dire la même chose.

| Type de source | Exemple | MCP | Fidélité = | Autorité | Statut produit |
| --- | --- | --- | --- | --- | --- |
| **Texte normatif / parlementaire** | lois, codes, amendements, débats | **Moulineuse** | citation = passage, mot pour mot | **normative** | `AUTHENTIFIÉ` (si opposable) / `CITÉ_NON_OPPOSABLE` |
| **Donnée chiffrée** | élections, INSEE, DGFiP, santé… | **Open Data (data.gouv)** | valeur = cellule d'un dataset, à telle version | **de mesure** | `DONNÉE_TRACÉE` (≠ authentifié) |

Règle pour le glossaire (§1bis) : un parlementaire ne doit **jamais** confondre « la loi dispose que X » (autorité normative) et « l'INSEE mesure Y » (autorité de mesure). Chaque affirmation porte donc le **type de source** en plus de son statut. La fidélité d'une donnée ne se prouve pas par comparaison de chaîne mais par **traçabilité** : `dataset_id` + `resource_id` + **version** + cellule, et par **égalité numérique stricte** entre la valeur publiée et la cellule (§7, INV-013).

**(v3) Opposabilité à l'intérieur du normatif.** Tout texte normatif n'a pas la même autorité. On dérive *déterministement* des métadonnées de classe documentaire un booléen :

```text
opposable = true   si  classe ∈ {en_vigueur, consolidé}
opposable = false  si  classe ∈ {débat, exposé_des_motifs, amendement_rejeté,
                                  question_écrite, projet_non_promulgué}
```

Seul `opposable == true` peut recevoir `AUTHENTIFIÉ`. Un verbatim exact sur source non opposable reçoit `CITÉ_NON_OPPOSABLE` (publié, mais traité comme `INTERPRÉTATION` côté opposabilité, donc plancher de risque `élevé`). L'opposabilité vient de *quel type de document*, jamais du modèle.

### Deux MCP suffisent à couvrir largement

On s'en tient à **Moulineuse** (normatif/parlementaire) + **Open Data data.gouv** (données). data.gouv est la **porte d'entrée** de nombreuses administrations (Intérieur, Justice, DGFiP, Santé publique France, ADEME…), donc un seul adaptateur MCP en dessert plusieurs.

### Multi-commission

Géré par des **profils de sources** filtrant le registre selon la commission (Finances → DGFiP/INSEE ; Affaires sociales → CNAM/Santé publique France ; Lois → Légifrance/parlementaire), et par l'extension du cloisonnement des logs (§13.4) **entre commissions**.

### Validation empirique (tests live)

* **Moulineuse — route fidélité.** `list_parlement_items("questions")` → deux questions écrites réelles du Sénat **déposées le 25/06/2026**, avec `uid`, texte intégral et `dateMaj`. *Note v3 : ces objets sont `opposable=false` — ils illustrent précisément pourquoi `CITÉ_NON_OPPOSABLE` est nécessaire.*
* **Open Data — chaîne « donnée tracée ».** `search_datasets("élections législatives 2024")` → dataset officiel **Ministère de l'Intérieur** ; `list_dataset_resources` → 14 ressources avec `resource_id` et **URL horodatée** ; `query_resource_data` → valeurs exactes (Inscrits **43 328 508**, etc.). La fidélité-donnée = `resource_id` + version + cellule, *sans* verbatim de texte.

---

## 7. Le vérificateur déterministe

C'est ici que se joue la différence entre *paraît vérifié* et *est vérifié*. Le contrôle est exécuté **exclusivement** par l'orchestrateur, qui détient à la fois la sortie du modèle et les passages officiellement récupérés. Il ne contient **aucun appel LLM** (INV-007).

### Politique de normalisation (sinon un `===` naïf rejette des citations légitimes)

Avant comparaison, citation et passage source subissent la **même** normalisation :

* espaces multiples → espace simple ; espaces insécables normalisés
* casse préservée pour les sigles, sinon insensible à la casse
* guillemets typographiques unifiés
* ponctuation de bord ignorée

### Statuts attribués à chaque affirmation

| Statut                  | Condition                                                       | Action            |
| ----------------------- | -------------------------------------------------------------- | ----------------- |
| `AUTHENTIFIÉ`           | citation = un **segment contigu** du passage opposable après normalisation | Publiée |
| `CITÉ_NON_OPPOSABLE`    | verbatim exact, mais sur source **non opposable** (§6ter)      | Publiée, *non opposable* → risque élevé |
| `INTERPRÉTATION`        | reformulation dont la **référence** existe dans les passages   | Publiée, *non opposable* |
| `DONNÉE_TRACÉE`         | valeur = cellule (`resource_id`+version), **égalité numérique stricte** | Publiée |
| `NON_AUTHENTIFIÉ`       | aucune correspondance de référence dans les passages           | **Bloquée → §7bis**|

Règles clés :

* **Le mot « authentifié » ne touche jamais une paraphrase** ni une source non opposable. Seule une citation littérale, confirmée mot pour mot, *sur source opposable*, reçoit `AUTHENTIFIÉ`.
* **(v3) Contiguïté (anti-épissage, piège B4).** Une citation `AUTHENTIFIÉ` doit correspondre à **un seul segment contigu** du passage normalisé. Une citation reconstituée par concaténation de fragments non contigus (chacun exact, mais formant une proposition fausse) → `NON_AUTHENTIFIÉ`. Un « … » à l'intérieur d'une citation est un marqueur d'épissage explicite → rétrogradation en `INTERPRÉTATION`. Ceci fixe la granularité du comparateur et durcit INV-008.
* **(v3) Vérificateur de valeur (donnée).** Pour `DONNÉE_TRACÉE`, la valeur publiée doit être **strictement égale** à la cellule après normalisation de format (séparateurs de milliers, séparateur décimal, unité, politique d'arrondi explicite). Corollaire (analogue d'INV-008) : **aucune valeur calculée par le modèle n'est `DONNÉE_TRACÉE`** — le modèle transcrit des cellules ; toute arithmétique est faite par le code, sinon c'est `INTERPRÉTATION`.

> **Jetons techniques vs libellés affichés.** Les noms ci-dessus sont les **jetons internes**, stables et contraignants (invariants §14, interfaces §15). L'interface utilisateur les présente avec des **libellés adoucis** : `NON_AUTHENTIFIÉ` / `REFUS_VÉRIFICATION` → « Source non confirmée » ; `INTERPRÉTATION` → « Reformulation (à valider) » ; `CITÉ_NON_OPPOSABLE` → « Cité (sans valeur normative) » ; `AUTHENTIFIÉ` → « Confirmé par la source » ; `DONNÉE_TRACÉE` → « Donnée officielle (version datée) ». Le mapping est cosmétique : il ne modifie ni la sémantique ni les invariants.

### Contrôles déterministes complémentaires (non-IA)

* l'identifiant cité existe-t-il dans l'index ? (lookup, pas génération)
* la date citée figure-t-elle dans le passage ?
* le texte est-il marqué abrogé dans les métadonnées du passage ?
* la source est-elle opposable ? (dérivé de la classe documentaire, §6ter)
* **détection locale des restrictions adjacentes (anti-troncature, piège B2) :** si le passage source enchaîne, *immédiatement après* la portion citée, sur un connecteur de restriction (« sauf », « toutefois », « sous réserve », « à l'exception », « sauf si », « par dérogation ») que la citation a omis → **drapeau « citation possiblement tronquée »** → escalade. **Portée explicitement limitée :** cette heuristique ne voit que les restrictions *textuellement adjacentes*. Une exception située deux alinéas plus loin, dans un autre article, dans un décret ou dans une jurisprudence **lui échappe** — elle relève de l'humain.

---

## 7bis. Politique de refus (mécanisme actif)

Déclenchée si : aucun passage retourné par MCP ; ou au moins une affirmation `NON_AUTHENTIFIÉ` ; ou incohérence détectée entre une citation et la source.

```text
[REFUS_VÉRIFICATION] : Impossible d'établir une réponse
à partir des sources officielles disponibles pour cette question.
```

Le refus est un état terminal sûr : en cas de doute, le système bloque la publication plutôt que d'émettre une affirmation non adossée à une source.

---

## 7ter. Mode document (v4)

Le flux §4 produit une réponse à une intention. Or l'usage parlementaire dominant n'est pas l'interrogation mais la **production de documents** : notes, discours, amendements, synthèses de rapports. Le mode document étend le pipeline **sans en changer le cœur** : un document est une **liste ordonnée de claims**, chacun vérifié individuellement par le vérificateur déterministe (§7). Il n'existe **aucun statut agrégé** « document vérifié » (INV-015) : le document expose la mosaïque des statuts de ses claims — c'est précisément ce qui permet à l'élu de distinguer, dans un même texte, ce qui est adossé au droit en vigueur de ce qui relève de son choix politique.

### Trois modes, trois profils de vérification

Le point commun est « sortie = document composé de claims » ; ce que le code peut garantir varie selon le mode.

| Mode | Exemple | Nature de la sortie | Contrôles spécifiques | Plancher de risque |
| --- | --- | --- | --- | --- |
| **analyse** | « explique-moi ce texte » | majoritairement `INTERPRÉTATION`, appuyée sur des extraits `AUTHENTIFIÉ` / `CITÉ_NON_OPPOSABLE` | anti-troncature (§7, B2) **renforcé** : expliquer une règle en omettant son « sauf… » est le piège dominant du mode | selon l'opposabilité de la source analysée |
| **synthèse** | « résume ce rapport de 300 pages » | presque aucun verbatim (comportement attendu, pas suspect) | lookup d'existence de chaque référence mentionnée ; **égalité stricte** de chaque chiffre repris (vérificateur de valeur §7) ; **contrôle de couverture documentaire** (ci-dessous) | `élevé` si la source est normative |
| **production** | « rédige un amendement » | mélange `AUTHENTIFIÉ` (droit en vigueur cité) + `INTERPRÉTATION` (dispositif nouveau) | existence de l'article et de l'alinéa visés (lookup) ; validité formelle du document (structure d'amendement, visas) | **toujours `élevé`** (INV-016) |

### Règles transverses

* **Mode analyse — la source est le passage.** La récupération est triviale : le texte fourni (ou résolu via §6bis) devient le passage de référence, avec son booléen `opposable` dérivé de sa classe documentaire (§6ter). Garantie : on ne peut pas « expliquer » un texte en citant des phrases qui n'y figurent pas.
* **Mode synthèse — contrôle de couverture documentaire (ferme B5).** Analogue documentaire de l'echo-back de l'étape 1bis (§4) : le **code** segmente la source en unités structurelles (articles, sections, chapitres — selon les métadonnées du document), et exige un mapping `unité → claim(s)` fourni par le LLM mais **vérifié par lookup**. Toute unité absente du mapping doit figurer dans une liste d'**omissions explicites** ; une synthèse sans mapping de couverture n'est pas publiable (INV-017). Un résumé qui saute silencieusement le chapitre gênant est ainsi détecté par construction. *Portée explicitement limitée : le contrôle voit l'omission d'une unité entière, pas l'omission d'un point à l'intérieur d'une unité couverte — ce résidu relève de l'humain (matrice §10, B5 🟡).*
* **Mode production — le dispositif nouveau est `INTERPRÉTATION` par nature.** Le système ne « vérifie » pas un choix politique (remplacer « dix » par « quatorze ») : il le marque comme tel. Ce qu'il garantit, c'est que le texte *existant* cité à l'appui (l'article modifié, son alinéa, son état `VIGUEUR`) est exact — le piège C1 (confusion Code de la consommation / CCH, reproduit en test live §6bis) est bloqué au verbatim.
* **Calibration par mode (§12).** L'absence de verbatim est suspecte en production, attendue en synthèse : le taux de sur-refus se mesure et se calibre **par mode**, sinon un seuil unique bloque tout résumé ou laisse passer toute production.

---

## 8. Registre et conformité

Le log capture le **résultat du contrôle verbatim** — c'est ce qu'un audit veut réellement voir.

```json
{
  "timestamp": "ISO-8601",
  "provider": "openai-api | anthropic-api | local-ollama",
  "model": "nom et version du modèle",
  "query": "texte de la question",
  "risk_tier": "faible | élevé",
  "mcp_calls": ["id_outil", "ids_passages_récupérés"],
  "passage_hashes": ["sha256(passage_normalisé)"],
  "claims": [
    { "ref": "id officiel", "status": "AUTHENTIFIÉ | CITÉ_NON_OPPOSABLE | INTERPRÉTATION | NON_AUTHENTIFIÉ | DONNÉE_TRACÉE" }
  ],
  "verbatim_check": "PASS | FAIL",
  "compliance_status": "VALIDATED | BLOCKED",
  "human_validation": "n/a | pending | approved",
  "governance_version": "v4"
}
```

`provider` et `model` sont journalisés précisément *parce que* l'architecture est agnostique. **(v3) `passage_hashes`** rend un PASS **rejouable** hors-ligne même si le corpus a changé depuis : on prouve la conformité contre une version reconstituable.

---

## 9. Variante API vs local — côte à côte

| Critère                         | API fournisseur                  | LLM local                                    |
| ------------------------------- | -------------------------------- | -------------------------------------------- |
| Confidentialité des questions   | sort de l'infrastructure         | **ne sort jamais** (atout parlementaire)     |
| Fidélité aux consignes          | élevée                           | plus faible (rattrapée par le vérificateur)  |
| Fiabilité du tool-calling natif | élevée                           | variable → forçage par l'orchestrateur (§6)  |
| Garantie de **fidélité documentaire** | **identique**                | **identique**                                |
| Coût marginal                   | par requête                      | infrastructure fixe                          |

La ligne décisive est l'avant-dernière : la garantie est **identique** parce qu'elle ne dépend pas du moteur. Le choix API/local devient une décision de **confidentialité et de coût**, pas de sécurité juridique.

---

## 10. Couverture et limites — matrice des pièges

Pièges regroupés par **endroit où ils vivent dans la réponse**. ✅ verrouillé · 🟡 borné puis délégué · ❌ trou résiduel.

**A. La référence citée (l'identifiant)**

| Piège | État | Traitement |
| --- | --- | --- |
| A1 — Référence inventée | ✅ | verbatim (§7) + lookup d'existence |
| A2 — Prémisse fausse (réf inexistante fournie) | 🟡 | structuré → refus ; texte libre → risque de voisin plausible |
| **A3 — Référence valide mais erronée, inférée (v3)** | 🟡 | slot inféré ≠ copié → « référence inférée, pertinence non garantie » + escalade (§4bis) |

**B. La fidélité de la citation (texte vs source)**

| Piège | État | Traitement |
| --- | --- | --- |
| B1 — Citation littérale exacte | ✅ | verbatim (§7) |
| B2 — Citation tronquée (exception omise) | 🟡 | heuristique anti-troncature (§7) → drapeau ; résidu → humain |
| B3 — Paraphrase distordue | 🟡 | `INTERPRÉTATION` / non-opposable (§7) |
| **B4 — Épissage de fragments vrais (v3)** | ✅ | règle de contiguïté (§7) → `NON_AUTHENTIFIÉ` |
| **B5 — Synthèse à trou : omission silencieuse (v4)** | 🟡 | contrôle de couverture documentaire (§7ter) → omissions nommées ; résidu (omission *interne* à une unité couverte) → humain |

**C. La pertinence (est-ce la *bonne* source)**

| Piège | État | Traitement |
| --- | --- | --- |
| C1 — Source réelle hors-sujet | 🟡 | requête structurée + « pertinence non garantie » (§4bis) + humain |
| C2 — Source périmée / caduque | 🟡 | contrôle date/statut (§7) + version (§3) |
| C3 — Mauvaise juridiction / territoire | 🟡 | contrôle métadonnées du passage (§7) |

**D. Le raisonnement (ce que la LLM déduit)**

| Piège | État | Traitement |
| --- | --- | --- |
| D1 — Interprétation déguisée en fait | 🟡 | statut non-opposable (§5) + escalade humaine (§9) |
| D2 — Synthèse multi-sources fallacieuse | ❌ | citations vraies, conclusion fausse — **humain seul** |
| D3 — Fausse attribution (« selon X… ») | ❌ | attrapé si entre guillemets ; sinon **humain** |

**E. La structure de la requête**

| Piège | État | Traitement |
| --- | --- | --- |
| E1 — N questions → 1 requête fourre-tout | ✅ | décomposition (§4) |
| E2 — Multi-saut non suivi | ✅ | récupération en boucle (§4) |
| E3 — Référent manquant (« ce texte ») | 🟡 | demande de précision (prompt B) |
| **E4 — Intention oubliée à la décomposition (v3)** | 🟡 | contrôle de couverture + echo-back (§4, étape 1bis) |

**F. L'autorité de la source (v3)**

| Piège | État | Traitement |
| --- | --- | --- |
| **F1 — Verbatim exact sur source non opposable** | ✅ | dérivation `opposable` (§6ter) → `CITÉ_NON_OPPOSABLE`, jamais `AUTHENTIFIÉ` |

### Lecture de la matrice

* **Verrouillé (A1, B1, B4, E1, E2, F1)** : invention pure + structure + épissage + faux label d'autorité. Le risque grave et massif, bien fermé.
* **Borné puis délégué (A2, A3, B2, B3, B5, C1, C2, C3, D1, E3, E4)** : routé vers marquage « non garanti » + humain. Délégué, pas masqué.
* **Trous résiduels (D2, D3)** : même racine — *le verbatim prouve que les mots existent, jamais que la source soutient l'affirmation*. Limite **mathématique** du contrôle déterministe. Relève de l'humain en risque élevé, par construction.

> La valeur de cette matrice n'est pas qu'elle soit toute verte — elle ne peut pas l'être. C'est qu'elle **nomme** ses cases non-vertes au lieu de les cacher.

---

## 11. Ce que Sentinel-Guard garantit / ne garantit pas

**Garantit :** qu'aucune citation littérale publiée comme `AUTHENTIFIÉ` n'est absente de la source officielle opposable récupérée ; qu'une référence inexistante est bloquée ; qu'un verbatim sur source non opposable n'obtient jamais le label d'autorité ; qu'en l'absence de source, le système refuse.

**Ne garantit pas :** la justesse de l'*interprétation* d'un texte pourtant correctement cité, ni la *pertinence* d'une source réelle mais hors-sujet. C'est une limite honnête, à assumer devant le jury plutôt qu'à masquer.

---

## 12. Mesure (sans quoi « excellent » reste une impression)

Constituer un **jeu de test piège** : questions à réponse connue, dont certaines conçues pour induire l'hallucination (article inexistant, texte abrogé, faux numéro d'arrêt, source non opposable, donnée corrompue), **et** des questions répondables à source connue. Protocole :

* **Taux de blocage correct** (sur pièges) — le chiffre qui prouve l'efficacité, et qui doit être **identique** quel que soit le backend.
* **(v3) Taux de sur-refus** = répondables bloqués / répondables. Un vérificateur trop prudent est abandonné par les utilisateurs, qui reviennent au LLM brut — ici la disponibilité est une propriété de **sécurité**, pas un confort.
* **(v4) Taux de sur-refus par mode document** (analyse / synthèse / production, §7ter) : un seuil calibré pour la production (verbatim exigé) bloquerait toute synthèse (zéro verbatim = comportement attendu). La calibration et le reporting se font par mode ; le jeu de test inclut des documents pièges par mode (rapport avec chapitre à omettre silencieusement pour B5, amendement visant un alinéa inexistant, etc.).
* **(v3) Métriques par type de piège** (réutilise la taxonomie §10) plutôt qu'un seul taux agrégé.
* **(v3) Taux de faux négatifs de triage** (items à risque connu classés faible) — mesure si le plancher §2 tient.
* **(v3) Calibration inter-annotateur** du gold standard : 2 annotateurs sur un sous-ensemble + Cohen's kappa / ICC, **pour valider le jeu de test, pas l'opération**.

Outillage de mesure : voir §17 (hors pipeline runtime, juge local en mode souverain).

---

## 13. Déploiement souverain on-premise (cible institutionnelle)

L'orchestrateur étant déjà un composant serveur, le passage à un hébergement souverain multi-utilisateurs est un changement d'**exploitation**, pas d'architecture. La garantie de fidélité documentaire (§1bis, §2, §7) est inchangée.

### 13.1 Principe de souveraineté

En mode **tout-local** — LLM local, client MCP local, vérificateur local — aucune donnée ne quitte l'infrastructure de l'institution. Aucun appel à un fournisseur externe.

> Comme la garantie ne dépend pas de la taille du modèle (§2), un modèle open-source modeste sur GPU on-premise délivre **la même garantie** qu'une grande API. La contrainte « local » dégrade la *fluidité*, jamais la *sécurité juridique*.

### 13.2 Topologie cible

```text
Députés / collaborateurs (postes distants)
        │  (réseau interne / VPN institutionnel uniquement)
        ▼
Passerelle d'accès + Authentification (identité institutionnelle)
        ▼
Sentinel-Guard (orchestrateur, multi-tenant)
   ├── LLM local (GPU on-premise, éventuellement répliqué)
   ├── Client MCP local → corpus officiel indexé
   └── Vérificateur déterministe (verbatim)
        ▼
Journalisation cloisonnée (§13.4)
```

### 13.3 Accès distant — la condition de la promesse « local »

« Local » n'est confidentiel que si **tout le chemin** l'est. À cadrer (DSI, §13.5) : accès restreint au réseau interne / VPN, aucune exposition publique ; authentification forte adossée à l'identité institutionnelle ; chiffrement en transit de bout en bout. Sans cela, l'accès distant réintroduit la surface d'attaque que le « local » devait éliminer.

### 13.4 Cloisonnement des logs — confidentialité du travail parlementaire

**Tension centrale :** *savoir quel député recherche quelle loi* est politiquement sensible. Principe : **séparer la preuve de conformité de l'identité de l'auteur.** Deux journaux distincts, non corrélables par défaut :

| Journal                  | Contenu                                                             | Finalité           | Identité           |
| ------------------------ | ------------------------------------------------------------------ | ------------------ | ------------------ |
| **Conformité** (ouvert)  | statut verbatim, refus, ids+hashes de passages, provider/model, horodatage | audit anti-hallu.  | **anonymisé**      |
| **Accès** (restreint)    | authentification, volumétrie par session                            | sécurité réseau    | pseudonymisé       |

Le journal de conformité **ne contient ni le texte de la question ni l'identité**. Log de conformité :

```json
{
  "timestamp": "ISO-8601",
  "session_ref": "jeton opaque, non rattaché à une identité",
  "provider": "local-ollama | ...",
  "model": "nom et version",
  "risk_tier": "faible | élevé",
  "mcp_calls": ["ids_passages_récupérés"],
  "passage_hashes": ["sha256(passage_normalisé)"],
  "claims": [{ "ref": "id officiel", "status": "AUTHENTIFIÉ | CITÉ_NON_OPPOSABLE | INTERPRÉTATION | NON_AUTHENTIFIÉ | DONNÉE_TRACÉE" }],
  "verbatim_check": "PASS | FAIL",
  "compliance_status": "VALIDATED | BLOCKED",
  "governance_version": "v4"
}
```

> Le champ `query` disparaît du journal de conformité : on prouve la conformité **sans** archiver l'objet de la recherche du député. Le hash porte sur la *source*, pas sur la question — la confidentialité est préservée et la preuve devient rejouable.

### 13.5 Frontière de responsabilité (à assumer devant le jury)

Ce qui relève du **projet** (démontrable au hackathon) : l'orchestrateur, le vérificateur, le mode tout-local, le cloisonnement des logs.

Ce qui relève de la **DSI de l'Assemblée** (hors périmètre hackathon) : hébergement physique, revue de sécurité, conformité RGPD, exigences type ANSSI/SecNumCloud, disponibilité, montée en charge pour ~577 députés + collaborateurs. *Le contrôle de valeur numérique (§7) et l'accès PISTE/Légifrance (§17) relèvent de ce périmètre s'ils ne sont pas démontrés au hackathon.*

**Cadrage honnête :** au hackathon, on démontre la méthode en mode souverain sur **un serveur local unique** ; le déploiement multi-députés est présenté comme **chemin cible**, frontière nommée explicitement. On livre une **brique souveraine conçue pour l'être**.

---

# Partie normative (pour l'implémentation)

> Contraignante pour le code. Là où une section narrative et un invariant divergeraient, l'invariant prime (§16). Une IA de codage doit traiter §14–§16 comme la source de vérité d'implémentation, et §1–§13 comme la justification.

## 14. Invariants d'implémentation (non négociables)

* **INV-001** — Aucune génération ne commence sans passages récupérés.
* **INV-002** — Une intention n'accède jamais aux passages d'une autre intention.
* **INV-003** — Toute affirmation publiée possède exactement un statut : `AUTHENTIFIÉ`, `CITÉ_NON_OPPOSABLE`, `INTERPRÉTATION`, `NON_AUTHENTIFIÉ` ou `DONNÉE_TRACÉE`.
* **INV-004** — `NON_AUTHENTIFIÉ` entraîne toujours `REFUS_VÉRIFICATION`.
* **INV-005** — `REFUS_VÉRIFICATION` est un état terminal.
* **INV-006** — Un document déjà présent dans `visitedDocuments` ne peut jamais être re-récupéré.
* **INV-007** — Le vérificateur déterministe ne contient aucun appel LLM.
* **INV-008** — Aucune paraphrase ne peut recevoir le statut `AUTHENTIFIÉ`.
* **INV-009** — Les exemples et validations empiriques ne modifient jamais les invariants.
* **(v3) INV-010** — `AUTHENTIFIÉ` exige `passage.opposable == true`. Un verbatim sur source non opposable reçoit `CITÉ_NON_OPPOSABLE`.
* **(v3) INV-011** — `risk_tier = max(triage_LLM, plancher_code)` ; il ne peut jamais descendre sous le plancher déterministe (§2).
* **(v3) INV-012** — Une citation `AUTHENTIFIÉ` correspond à **un seul segment contigu** du passage normalisé (anti-épissage).
* **(v3) INV-013** — `DONNÉE_TRACÉE` exige l'égalité numérique stricte (après normalisation de format) entre valeur publiée et cellule ; aucune valeur calculée par le modèle n'est `DONNÉE_TRACÉE`.
* **(v3) INV-014** — Aucune dépendance à juge-LLM (`deepeval`, `ragas`) n'intervient dans le chemin de décision runtime ; elles sont confinées au banc de mesure §12.
* **(v4) INV-015** — Un document publié n'a **aucun statut agrégé** : chaque claim conserve son statut individuel (§7), visible dans la sortie. Aucun libellé de type « document vérifié » ne peut exister dans l'interface.
* **(v4) INV-016** — En mode **production**, `risk_tier = élevé` inconditionnellement ; en mode **synthèse** d'une source normative, également (extension du plancher §2).
* **(v4) INV-017** — En mode **synthèse**, toute unité structurelle de la source absente du mapping de couverture figure dans la liste d'omissions explicites ; une synthèse **sans** mapping de couverture n'est pas publiable.

Chaque invariant est **vérifiable par un test automatique** (ex. INV-002 → injecter deux intentions et vérifier le cloisonnement ; INV-008/012 → soumettre une paraphrase puis un épissage et vérifier qu'aucun n'obtient `AUTHENTIFIÉ` ; INV-010 → injecter un passage de débat et vérifier le `CITÉ_NON_OPPOSABLE` ; INV-014 → vérifier qu'aucun import de ces paquets n'apparaît dans le chemin runtime ; INV-017 → soumettre un rapport de 10 sections et une synthèse n'en mappant que 9 sans omission déclarée : blocage).

## 15. Interfaces canoniques (pseudo-types)

Types **normatifs** : une implémentation peut les enrichir, jamais en modifier la sémantique.

```typescript
interface Intent {
  id: string
  question: string
}

interface Passage {
  sourceId: string
  sourceType: "normatif" | "donnee"
  opposable: boolean              // (v3) dérivé de la classe documentaire (§6ter)
  text: string
  metadata: Record<string, unknown>
}

type ClaimStatus =
  | "AUTHENTIFIÉ"
  | "CITÉ_NON_OPPOSABLE"           // (v3)
  | "INTERPRÉTATION"
  | "NON_AUTHENTIFIÉ"
  | "DONNÉE_TRACÉE"

interface Claim {
  ref: string
  status: ClaimStatus
}

interface VerificationResult {
  verbatimCheck: "PASS" | "FAIL"
  claims: Claim[]
}

interface RetrievalState {
  hopCount: number
  visitedDocuments: Set<string>
  remainingBudget: number
}

type DocumentMode = "analyse" | "synthèse" | "production"   // (v4)

interface CoverageMap {                                      // (v4) — mode synthèse
  sourceUnits: string[]              // unités structurelles, segmentées par le CODE
  covered: Record<string, string[]>  // unité → ids de claims (existence vérifiée par lookup)
  omitted: string[]                  // omissions EXPLICITES (INV-017)
}

interface DocumentDraft {                                    // (v4)
  mode: DocumentMode
  claims: Claim[]                    // ordonnés ; aucun statut agrégé (INV-015)
  coverage?: CoverageMap             // requis si mode == "synthèse" (INV-017)
}
```

Correspondances : `Passage.sourceType` ↔ §6ter ; `Passage.opposable` ↔ §6ter (v3) ; `ClaimStatus` ↔ glossaire §1bis + §7 ; `RetrievalState` ↔ bornes §4ter ; `DocumentMode` / `DocumentDraft` / `CoverageMap` ↔ §7ter (v4).

## 16. Priorité des règles

En cas de conflit, ordre strict et déterministe :

1. Les **invariants d'implémentation** (§14) priment sur tout.
2. Les **sections architecturales** (§2, §4, §7) priment sur les exemples.
3. Les **validations empiriques** (§6bis, §6ter) ne sont **pas** normatives.
4. Les **annexes** servent uniquement d'illustration.
5. Les **exemples de code** ne peuvent jamais contredire les invariants.

---

## 17. Dépendances externes et frontière de fiabilité

> Section de **référence** (non normative au sens du §16), à une exception : la règle de frontière runtime (§17.2 / INV-014). Toutes les dépendances retenues sont sous licence **permissive (MIT / Apache-2.0)** — aucune obligation copyleft, compatibles déploiement souverain (§13.5).

### 17.1 Modules retenus

| Couche (flux §4) | Module (repo GitHub) | Licence | Rôle | Rattachement |
| --- | --- | --- | --- | --- |
| Moteur | `BerriAI/litellm` | MIT | Implémentation concrète de `ModelProvider` (§3) ; bascule API ↔ local | §3, §6, §9, §13 |
| Récupération | `modelcontextprotocol/python-sdk` (`mcp`) | MIT | Client MCP appelé **par l'orchestrateur** (étape 4) | §1, §4, §6bis |
| Source d'autorité (repli) | `pylegifrance/pylegifrance` + `mcp-server-legifrance` | à confirmer sur le dépôt | Recoupement / repli Légifrance-JORF | §6bis |
| Vérificateur (cœur) | stdlib `unicodedata` / `re` | PSF | Normalisation + verbatim (§7), **aucun LLM** | §7 |
| Vérificateur (drapeau) | `rapidfuzz` | MIT | **Uniquement** drapeau quasi-correspondance ; jamais autorité | §7 (B2) |
| Audit | stdlib `hashlib` | PSF | `sha256` → preuve rejouable | §8, §13.4 |
| Mesure (hors runtime) | `confident-ai/deepeval` | Apache-2.0 | Métriques + tests pytest/CI | §12, §14 |
| Mesure (hors runtime) | `vibrantlabsai/ragas` | Apache-2.0 | Métriques RAG complémentaires | §12 |
| Calibration (hors runtime) | `doccano` + `krippendorff` / `scikit-learn` | MIT / BSD-3 | Gold standard + ICC / kappa | §12 |

### 17.2 Règle de frontière runtime (INV-014)

Un seul composant tiers intervient dans le **chemin de décision** menant à la publication : le **vérificateur** (sans LLM, INV-007). Le client MCP intervient *avant* la génération. Tout le reste est plomberie (LiteLLM) ou **hors-ligne** (deepeval, ragas, doccano). Justification : ces outils notent par **juge-LLM** — le mode de jugement que la spec refuse de croire (§2, §5). Les utiliser en runtime réintroduirait la dépendance au modèle que tout le système élimine.

### 17.3 Réglages souverains obligatoires des dépendances

```text
mcp        : épingler  mcp>=1.27,<2   (v1.x stable ; v2 en alpha)
litellm    : backend Ollama local ; AUCUNE clé API externe chargée
ragas      : RAGAS_DO_NOT_TRACK=true   (coupe la télémétrie)
deepeval   : aucun compte externe ; juge = modèle LOCAL (via litellm/Ollama)
pylegifrance : hors-ligne sur corpus indexé, OU via PISTE si la DSI l'autorise (§13.5)
```

### 17.4 Placement dans le flux

```text
        ┌─ litellm (ModelProvider) ─────────────────┐
        │  décompose · formule · rédige             │  ← LLM : intelligence
Client ─┤  mcp (client) ──► Moulineuse / data.gouv  │  ← étape 4 : récupération
        │       (+ pylegifrance en recoupement)     │
        └─ VÉRIFICATEUR : unicodedata/re (+rapidfuzz drapeau, +hashlib audit)
                          │  ← code : AUTORITÉ (INV-007)
                          ▼
              AUTHENTIFIÉ / CITÉ_NON_OPPOSABLE / DONNÉE_TRACÉE / REFUS / ESCALADE

   [hors ligne, jamais runtime]  deepeval · ragas · doccano  ──► rapport §12
```

### 17.5 Ce que ces dépendances n'apportent pas

Aucune n'ajoute de fiabilité au **cœur** de la garantie : celle-ci vient de l'architecture (§2, §7) et des invariants (§14). Ce qu'elles apportent est plus modeste : éviter de re-coder la plomberie (moins de bugs) et **préserver l'invariance au modèle** (LiteLLM : même garantie en local comme en API). Écarter les frameworks « guardrails » à juge-LLM est le pendant de ce choix — ils déplaceraient l'autorité vers un modèle.
