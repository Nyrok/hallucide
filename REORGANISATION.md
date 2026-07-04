# 📂 Réorganisation par étapes du pipeline

**Date**: 4 juillet 2026  
**Objectif**: Ranger les 27 modules du moteur par bloc du pipeline pour meilleure lisibilité et maintenabilité.

---

## Structure avant / après

### Avant (plat)
```
src/sentinel_guard/
├── orchestration.py, llm.py, coverage.py, ...
└── 27 fichiers .py dans le même dossier
```

### Après (par étape)
```
src/sentinel_guard/
├── core.py                          # Façade principale (SentinelGuard.ask)
├── core_types/
│   ├── types.py                    # Intent, Passage, Claim, ClaimStatus, RiskTier, etc.
│   └── exceptions.py               # SentinelGuardException, VerificationError, etc.
│
├── _1_decomposition/
│   ├── orchestration.py            # Boucle principale d'orchestration
│   └── llm.py                       # Abstraction LLM, prompts, parsing
│
├── _2_coverage/
│   └── coverage.py                 # Vérification de couverture des intentions
│
├── _3_retrieval/
│   ├── multi_source.py             # Router vers la bonne source
│   ├── moulineuse.py               # Source: Moulineuse (code, parlement)
│   ├── datagouv.py                 # Source: data.gouv.fr (données chiffrées)
│   ├── file_retrieval.py           # Source: fichiers CSV/ZIP
│   ├── retrieval.py                # Interface générique
│   ├── multi_hop.py                # Suivi des renvois (voir article X)
│   └── mcp_client.py               # Protocole MCP (bas niveau)
│
├── _4_verification/
│   ├── verifier.py                 # Vérification mot-pour-mot (cœur dur)
│   ├── normalization.py            # Nettoyage: casse, ponctuation, chiffres
│   └── slot_provenance.py          # Distinction référence copiée vs inférée
│
├── _5_triage/
│   └── triage.py                   # Plancher de risque (FAIBLE → ÉLEVÉ, jamais inversé)
│
├── _6_validation/
│   ├── human_validation.py         # Registre des décisions humaines
│   └── document.py                 # Mode document v4 (analyse/synthèse/production)
│
├── _7_audit/
│   ├── audit.py                    # Journal de conformité rejouable
│   └── sovereign_log.py            # Cloisonnement conformité/accès (§13.4)
│
├── llm_providers/
│   ├── mistral.py                  # Implémentation Mistral
│   ├── gemini.py                   # Implémentation Gemini
│   └── litellm_provider.py         # Variante via LiteLLM
│
└── analysis/
    ├── measurement.py              # Banc de mesure (taux de blocage, etc.)
    ├── trap_dataset.py             # Jeu de données pièges
    ├── calibration.py              # Kappa de Cohen inter-annotateurs
    └── trust.py                    # Analyse de confiance
```

---

## Flux du pipeline

```
Question
  │
  ├─ [1] DÉCOMPOSITION (_1_decomposition/)
  │  │   llm.py: LLM décompose en intentions
  │  │   orchestration.py: boucle principale
  │  └─ → intentions
  │
  ├─ [2] COUVERTURE (_2_coverage/)
  │  │   check_coverage(): vérifier qu'aucune intention n'est oubliée
  │  └─ → coverage_ratio, couverture OK ou ÉLEVÉ
  │
  ├─ [3] RÉCUPÉRATION (_3_retrieval/)
  │  │   multi_source.py: router à la bonne source
  │  │   moulineuse.py / datagouv.py / file_retrieval.py: récupérer passage
  │  │   multi_hop.py: suivre les renvois
  │  └─ → passages officiels (opposable ou non)
  │
  ├─ [4] VÉRIFICATION (_4_verification/)
  │  │   verifier.py: vérifier MOT POUR MOT (cœur dur)
  │  │   normalization.py: nettoyer avant comparaison
  │  │   slot_provenance.py: référence copiée vs inférée
  │  └─ → claims avec statuts (AUTHENTIFIÉ, NON_AUTHENTIFIÉ, etc.)
  │
  ├─ [5] TRIAGE (_5_triage/)
  │  │   apply_risk_floor(): au moindre signal danger → ÉLEVÉ
  │  └─ → risk_tier (FAIBLE ou ÉLEVÉ)
  │
  ├─ [6] VALIDATION (_6_validation/)
  │  │   human_validation.py: chercher décision humaine enregistrée
  │  │   document.py: mode document (si applicable)
  │  └─ → published = True/False
  │
  └─ [7] JOURNALISATION (_7_audit/)
     │   audit.py: une entrée de conformité par intention
     │   sovereign_log.py: cloisonner conformité/accès
     └─ → ComplianceLogEntry (rejoué, sans question ni identité)
```

---

## Imports

Tous les imports internes utilisent **chemins absolus depuis `sentinel_guard`** :

❌ Avant:
```python
from .types import Claim
from .verifier import verify_claims
```

✅ Après:
```python
from sentinel_guard.core_types.types import Claim
from sentinel_guard._4_verification.verifier import verify_claims
```

**Avantage**: pas de confusion sur les chemins relatifs quand les modules sont dispersés.

---

## Makefile

Nouveau `Makefile` simplifie la vie :

```bash
make install    # venv + pip install -e .[test]
make test       # pytest -q (175 tests attendus)
make frontend   # http://localhost:8770 (chat futuriste)
make ui         # http://localhost:8765 (démo historique)
make demo       # install + test + rapport
make clean      # nettoyer caches
make help       # affiche ce guide
```

---

## Ce qui n'a PAS changé

- **Logique du moteur** : aucune ligne de code du pipeline modifiée
- **Tests** : toujours à la racine (`tests/`), imports corrigés
- **Démonstrateurs** : `ui/` et `demarche/etape_2_front/` intact, imports corrigés
- **Spec** : `sentinel-guard-spec-v4.md` inchangée (la structure suit la spec)
- **Comportement** : 175 tests doivent toujours passer

---

## Migration pour l'équipe

Si vous étiez déjà familiarisé avec le code, cette réorg:

✅ **Améliore**:
- Clarté: chaque étape du pipeline est dans son dossier
- Navigation: `Cmd+P 1_decomposition` dans l'éditeur pour trouver décomposition
- Maintenance: plus facile d'ajouter une nouvelle étape sans polluer le top-level
- Documentation: la structure EST la documentation du pipeline

⚠️ **Impacte**:
- Les imports changent (corrigés automatiquement)
- Besoin de `make install` plutôt que `pip install -e .` directement
- Si des scripts personnalisés importent du moteur, faut les updater (peu probable)

---

## Commandes de vérification

```bash
# Tous les fichiers parsent (syntax OK)
python3 << 'EOF'
import ast, os
for root, dirs, files in os.walk('src/sentinel_guard'):
    for f in files:
        if f.endswith('.py'):
            ast.parse(open(os.path.join(root, f)).read())
print("✅ All files parse")
EOF

# Imports résolvent (si pip était dispo)
# make install && make test

# Structure vérifiée
find src/sentinel_guard -type d | sort
```

---

## Références

- Spec moteur: `sentinel-guard-spec-v4.md`
- Documentation équipe: `demarche/etape_1_comprendre/COMPRENDRE.md`
- Interface de chat: `demarche/etape_2_front/README.md`
- Blocages connus: `demarche/suivi/BLOCAGES.md`
