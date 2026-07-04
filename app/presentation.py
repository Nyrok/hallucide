"""Couche de PRÉSENTATION — score 0-100, bandes et couleurs.

┌───────────────────────────────────────────────────────────────────────────┐
│  CE FICHIER N'EST PAS DE LA VÉRIFICATION.                                   │
│  C'est un HABILLAGE du statut déterministe déjà produit par le moteur       │
│  (src/sentinel_guard/verifier.py). Le score 0-100 ne fait que TRADUIRE en   │
│  chiffre et en couleur un statut que le code a déjà établi mot pour mot.    │
│  À dire tel quel au pitch, sinon un juré demandera « d'où sort ce chiffre » │
│  → réponse : « d'un mapping fixe et déterministe du statut du moteur, pas   │
│  d'une nouvelle logique de confiance ni d'une probabilité du modèle ».      │
└───────────────────────────────────────────────────────────────────────────┘

Deux niveaux d'information viennent du moteur (voir COMPRENDRE.md §5) :

  1. le STATUT d'un claim  (ClaimStatus, types.py) :
     AUTHENTIFIÉ / CITÉ_NON_OPPOSABLE / INTERPRÉTATION / DONNÉE_TRACÉE / NON_AUTHENTIFIÉ
  2. le COMPLIANCE_STATUS d'une intention  (audit.py) :
     VALIDATED / BLOCKED / NO_ANSWER   ← NO_ANSWER = « aucune affirmation produite »

Le score se calcule donc à DEUX niveaux :
  - `score_for_claim(...)`  : pour une affirmation individuelle (badge coloré + chiffre).
  - `score_for_intent(...)` : pour l'intention entière (gère le cas NO_ANSWER, où il
                              n'y a aucun claim, et applique le plafond « non publié »).

Choix assumé : les scores sont des VALEURS FIXES par statut, pas des tirages
aléatoires dans une fourchette. Un outil anti-hallucination doit être
reproductible : la même réponse doit toujours donner le même score. Les
fourchettes du cahier (§4.2) servent de garde-fous (bandes de couleur), la
valeur exacte est déterministe.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

# --- Bandes de couleur (le front mappe ces noms vers des dégradés CSS) --------
BAND_VERIFIED = "verifie"    # vert  — preuve forte, publiable
BAND_TRACED = "trace"        # bleu  — donnée tracée à la cellule exacte
BAND_CAUTION = "prudence"    # orange — vrai mais faible / non opposable / à valider
BAND_RISK = "risque"         # rouge — non authentifié / aucune réponse fiable

# Badge « intervention humaine requise » (§4 étape 9). Apposé dès que le moteur
# refuse la publication automatique (published == False), quel que soit le statut.
HUMAN_BADGE = "🧑‍⚖️"

# Plafond appliqué à un résultat NON publié : même une citation AUTHENTIFIÉE, si
# elle est bloquée par le plancher de risque (ex. query partagée E1, sélection
# ambiguë), ne doit pas s'afficher en vert rassurant. On la ramène en zone
# orange/rouge (cahier §4.2, dernière puce).
NOT_PUBLISHED_CAP = 45


@dataclass(frozen=True)
class ScoreView:
    """Ce que le front reçoit pour dessiner un badge : un chiffre, une bande de
    couleur, un libellé humain, et un éventuel badge d'intervention humaine."""

    score: int          # 0-100
    band: str           # une des constantes BAND_*
    label: str          # libellé court affichable
    reason: str         # phrase d'explication (survol)
    human_review: bool  # True → afficher HUMAN_BADGE + « NON PUBLIABLE en l'état »

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["human_badge"] = HUMAN_BADGE if self.human_review else None
        return d


# Table maîtresse statut → (score de base, bande, libellé, explication).
# Ordre et valeurs pensés pour que couleur ↔ statut réel du moteur soient cohérents.
_STATUS_TABLE: Dict[str, tuple[int, str, str, str]] = {
    "AUTHENTIFIÉ": (
        96, BAND_VERIFIED, "Authentifié",
        "Citation présente mot pour mot dans une source officielle opposable en vigueur.",
    ),
    "DONNÉE_TRACÉE": (
        88, BAND_TRACED, "Donnée tracée",
        "Valeur chiffrée retrouvée à la cellule exacte d'une source publique (data.gouv/INSEE).",
    ),
    "CITÉ_NON_OPPOSABLE": (
        55, BAND_CAUTION, "Cité (non opposable)",
        "Citation exacte, mais la source n'est pas opposable (ou texte abrogé) : vrai, non invocable.",
    ),
    "INTERPRÉTATION": (
        50, BAND_CAUTION, "Interprétation",
        "Reformulation ancrée dans la source (négations et chiffres présents), mais pas un verbatim : à valider.",
    ),
    "NON_AUTHENTIFIÉ": (
        20, BAND_RISK, "Non authentifié",
        "Affirmation non retrouvée mot pour mot dans la source : potentielle hallucination, bloquée.",
    ),
}

# Cas particulier : aucune affirmation produite (compliance_status == NO_ANSWER).
# C'est un BON signe (le système se tait plutôt que d'inventer) mais côté score
# c'est le plancher : rien n'a pu être prouvé.
_NO_ANSWER_VIEW = (
    5, BAND_RISK, "Aucune réponse fiable",
    "Le système n'a produit aucune affirmation vérifiable pour cette intention (il préfère se taire plutôt qu'inventer).",
)

# Statut inconnu (défense en profondeur : si le moteur ajoute un jour un statut,
# on ne l'affiche jamais en vert par erreur).
_UNKNOWN_VIEW = (
    10, BAND_RISK, "Statut inconnu",
    "Statut non reconnu par la couche d'affichage : traité comme non fiable par précaution.",
)


def _apply_not_published(score: int, band: str, reason: str, published: bool) -> tuple[int, str, str, bool]:
    """Applique le plafond « intervention humaine » si le moteur refuse la
    publication. Renvoie (score, band, reason, human_review)."""
    if published:
        return score, band, reason, False
    capped = min(score, NOT_PUBLISHED_CAP)
    # On ne descend jamais EN DESSOUS de la bande réelle : un NON_AUTHENTIFIÉ
    # reste rouge, un AUTHENTIFIÉ bloqué passe en orange (prudence).
    new_band = BAND_RISK if band == BAND_RISK else BAND_CAUTION
    note = " — intervention humaine requise, NON PUBLIABLE en l'état (§4 étape 9)."
    return capped, new_band, reason + note, True


def score_for_claim(status: str, risk_tier: str, published: bool) -> ScoreView:
    """Score d'UNE affirmation, à partir de son statut réel + risque + publication.

    `status`     : valeur de ClaimStatus (ex. "AUTHENTIFIÉ").
    `risk_tier`  : "faible" ou "élevé" (informe l'explication, pas le score de base).
    `published`  : booléen du moteur (AskResult.published pour cette intention).
    """
    base, band, label, reason = _STATUS_TABLE.get(status, _UNKNOWN_VIEW)
    score, band, reason, human = _apply_not_published(base, band, reason, published)
    return ScoreView(score=score, band=band, label=label, reason=reason, human_review=human)


def score_for_intent(
    claims: list[Dict[str, Any]],
    compliance_status: str,
    risk_tier: str,
    published: bool,
    control_claim: Optional[Dict[str, Any]] = None,
) -> ScoreView:
    """Score AGRÉGÉ d'une intention, pour la vignette de tête d'un message.

    Règle d'agrégation : on prend le claim le PLUS FAIBLE (le maillon faible
    gouverne la fiabilité de l'ensemble — cohérent avec l'esprit du moteur, qui
    bloque au moindre signal). Si aucun claim (NO_ANSWER), on affiche le plancher.

    `control_claim` : claim de contrôle de secours produit par ui/server.py quand
    le LLM n'a rien affirmé (verbatim réel du passage) — pris en compte s'il existe.
    """
    # Rassemble tous les statuts de claims disponibles (LLM + contrôle éventuel).
    statuses = [c.get("status") for c in claims if c.get("status")]
    if control_claim and control_claim.get("status"):
        statuses.append(control_claim["status"])

    if not statuses:
        # Aucune affirmation : NO_ANSWER (ou équivalent). Plancher.
        base, band, label, reason = _NO_ANSWER_VIEW
        score, band, reason, human = _apply_not_published(base, band, reason, published)
        return ScoreView(score=score, band=band, label=label, reason=reason, human_review=human)

    # Le maillon faible = le statut au plus petit score de base.
    def _base_score(s: str) -> int:
        return _STATUS_TABLE.get(s, _UNKNOWN_VIEW)[0]

    weakest = min(statuses, key=_base_score)
    return score_for_claim(weakest, risk_tier, published)


# --- Auto-test rapide (exécuter : python -m app.presentation) --------------
if __name__ == "__main__":
    checks = [
        # (statut, risk, published) -> (score attendu, bande attendue)
        (("AUTHENTIFIÉ", "faible", True), (96, BAND_VERIFIED, False)),
        (("AUTHENTIFIÉ", "élevé", False), (45, BAND_CAUTION, True)),   # bloqué → plafonné
        (("DONNÉE_TRACÉE", "faible", True), (88, BAND_TRACED, False)),
        (("INTERPRÉTATION", "élevé", False), (45, BAND_CAUTION, True)),
        (("NON_AUTHENTIFIÉ", "élevé", False), (20, BAND_RISK, True)),
        (("NON_AUTHENTIFIÉ", "faible", True), (20, BAND_RISK, False)),
    ]
    ok = True
    for (args, (exp_score, exp_band, exp_human)) in checks:
        v = score_for_claim(*args)
        good = (v.score == exp_score and v.band == exp_band and v.human_review == exp_human)
        ok = ok and good
        print(f"{'OK ' if good else 'FAIL'} {args} -> score={v.score} band={v.band} human={v.human_review}")
    # NO_ANSWER agrégé
    v = score_for_intent([], "NO_ANSWER", "élevé", False)
    no_ans_ok = v.band == BAND_RISK and v.human_review
    print(f"{'OK ' if no_ans_ok else 'FAIL'} intent NO_ANSWER -> score={v.score} band={v.band}")
    print("=== TOUT OK ===" if ok and no_ans_ok else "=== ÉCHEC ===")
