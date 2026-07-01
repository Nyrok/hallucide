from __future__ import annotations

from .measurement import TrapCase, TriageCase
from .triage import RiskTier
from .types import Claim, ClaimStatus, Passage

_CIVIL_CODE_PASSAGE = Passage(
    source_id="LEGIARTI000032040777",
    source_type="normatif",
    opposable=True,
    text="Les contrats légalement formés tiennent lieu de loi à ceux qui les ont faits.",
    metadata={"etat": "VIGUEUR"},
)

_NON_OPPOSABLE_PASSAGE = Passage(
    source_id="debat-2026-001",
    source_type="normatif",
    opposable=False,
    text="Cette disposition vise à clarifier la portée de l'article pour les justiciables.",
    metadata={"classe": "debat"},
)

_RESTRICTION_PASSAGE = Passage(
    source_id="LEGIARTI-preavis",
    source_type="normatif",
    opposable=True,
    text="Le salarié bénéficie d'un délai de préavis de deux mois sauf en cas de faute grave.",
    metadata={"etat": "VIGUEUR"},
)

_ABROGATED_PASSAGE = Passage(
    source_id="LEGIARTI-abroge",
    source_type="normatif",
    opposable=False,
    text="Le présent article est abrogé à compter du 1er janvier 2010.",
    metadata={"etat": "ABROGE"},
)

# Jeu de test piège (§12) : couvre les pièges A1/A2/B1/B2/B3/B4/F1/C2 de la
# matrice §10, chacun avec un cas piège ET un cas répondable correspondant
# (nécessaire pour distinguer le taux de blocage correct du taux de sur-refus).
TRAP_DATASET: list[TrapCase] = [
    # A1 -- référence inventée : citation absente du passage -> refus attendu.
    TrapCase(
        id="a1-invented-reference",
        trap_type="A1",
        is_answerable=False,
        claim=Claim(
            ref="Les contrats sont annulés de plein droit en cas de litige.",
            status=ClaimStatus.AUTHENTIFIÉ,
        ),
        passage=_CIVIL_CODE_PASSAGE,
        expected_status=None,
    ),
    TrapCase(
        id="a1-control-real-citation",
        trap_type="A1",
        is_answerable=True,
        claim=Claim(
            ref="Les contrats légalement formés tiennent lieu de loi à ceux qui les ont faits.",
            status=ClaimStatus.AUTHENTIFIÉ,
        ),
        passage=_CIVIL_CODE_PASSAGE,
        expected_status=ClaimStatus.AUTHENTIFIÉ,
    ),
    # B1 -- citation littérale exacte : doit être authentifiée (cas répondable).
    TrapCase(
        id="b1-exact-citation",
        trap_type="B1",
        is_answerable=True,
        claim=Claim(
            ref="Les contrats légalement formés tiennent lieu de loi à ceux qui les ont faits.",
            status=ClaimStatus.AUTHENTIFIÉ,
        ),
        passage=_CIVIL_CODE_PASSAGE,
        expected_status=ClaimStatus.AUTHENTIFIÉ,
    ),
    # B2 -- citation tronquée (exception omise) : authentifiée mais signalée.
    # Le statut reste AUTHENTIFIÉ (les mots existent), donc ce cas est répondable ;
    # c'est le drapeau truncation_flagged (hors mesure de statut) qui porte le signal.
    TrapCase(
        id="b2-truncated-citation",
        trap_type="B2",
        is_answerable=True,
        claim=Claim(
            ref="Le salarié bénéficie d'un délai de préavis de deux mois",
            status=ClaimStatus.AUTHENTIFIÉ,
        ),
        passage=_RESTRICTION_PASSAGE,
        expected_status=ClaimStatus.AUTHENTIFIÉ,
    ),
    # B3 -- paraphrase distordue : un "..." dans la citation signale une
    # reformulation -> rétrogradée en INTERPRÉTATION, jamais AUTHENTIFIÉ.
    TrapCase(
        id="b3-paraphrase-with-ellipsis",
        trap_type="B3",
        is_answerable=False,
        claim=Claim(
            ref="Les contrats légalement formés ... tiennent lieu de loi à ceux qui les ont faits.",
            status=ClaimStatus.AUTHENTIFIÉ,
        ),
        passage=Passage(
            source_id="LEGIARTI000032040777-spaced",
            source_type="normatif",
            opposable=True,
            text="Les contrats légalement formés ... tiennent lieu de loi à ceux qui les ont faits.",
            metadata={"etat": "VIGUEUR"},
        ),
        expected_status=ClaimStatus.INTERPRÉTATION,
    ),
    # B4 -- épissage de fragments vrais (non contigus) -> NON_AUTHENTIFIÉ -> refus.
    TrapCase(
        id="b4-spliced-fragments",
        trap_type="B4",
        is_answerable=False,
        claim=Claim(
            ref="Le contrat est nul si la loi protège les parties.",
            status=ClaimStatus.AUTHENTIFIÉ,
        ),
        passage=Passage(
            source_id="doc-spliced",
            source_type="normatif",
            opposable=True,
            text="Le contrat est nul si le consentement a été vicié. La loi protège les parties.",
            metadata={},
        ),
        expected_status=None,
    ),
    # F1 -- verbatim exact sur source non opposable -> CITÉ_NON_OPPOSABLE, jamais AUTHENTIFIÉ.
    TrapCase(
        id="f1-verbatim-non-opposable",
        trap_type="F1",
        is_answerable=True,
        claim=Claim(
            ref="Cette disposition vise à clarifier la portée de l'article pour les justiciables.",
            status=ClaimStatus.AUTHENTIFIÉ,
        ),
        passage=_NON_OPPOSABLE_PASSAGE,
        expected_status=ClaimStatus.CITÉ_NON_OPPOSABLE,
    ),
    # C2 -- source périmée/abrogée : verbatim exact mais sur texte non opposable
    # car abrogé -- même mécanisme que F1, mais déclenché par le cycle de vie du texte.
    TrapCase(
        id="c2-abrogated-source",
        trap_type="C2",
        is_answerable=True,
        claim=Claim(
            ref="Le présent article est abrogé à compter du 1er janvier 2010.",
            status=ClaimStatus.AUTHENTIFIÉ,
        ),
        passage=_ABROGATED_PASSAGE,
        expected_status=ClaimStatus.CITÉ_NON_OPPOSABLE,
    ),
    # Cas DONNÉE_TRACÉE de contrôle : égalité numérique stricte après normalisation.
    TrapCase(
        id="donnee-tracee-control",
        trap_type="DONNÉE_TRACÉE",
        is_answerable=True,
        claim=Claim(ref="43 328 508", status=ClaimStatus.DONNÉE_TRACÉE),
        passage=Passage(
            source_id="resource-inscrits-2024",
            source_type="donnee",
            opposable=True,
            text="43 328 508",
            metadata={"dataset_id": "elections-legislatives-2024"},
        ),
        expected_status=ClaimStatus.DONNÉE_TRACÉE,
    ),
    TrapCase(
        id="donnee-tracee-mismatch",
        trap_type="DONNÉE_TRACÉE",
        is_answerable=False,
        claim=Claim(ref="43 000 000", status=ClaimStatus.DONNÉE_TRACÉE),
        passage=Passage(
            source_id="resource-inscrits-2024",
            source_type="donnee",
            opposable=True,
            text="43 328 508",
            metadata={"dataset_id": "elections-legislatives-2024"},
        ),
        expected_status=None,
    ),
]

# Banc de triage (§12) : items à risque connu élevé où le triage LLM se
# trompe (classe faible), pour vérifier que le plancher déterministe (§2)
# rattrape chaque faux négatif -- INV-011 rendu mesurable plutôt que présumé.
TRIAGE_DATASET: list[TriageCase] = [
    TriageCase(
        id="triage-llm-correct-eleve",
        llm_risk=RiskTier.ÉLEVÉ,
        floor_conditions=(False,),
        expected_risk=RiskTier.ÉLEVÉ,
    ),
    TriageCase(
        id="triage-llm-faux-negatif-citation-non-opposable",
        # Le LLM sous-estime le risque (CITÉ_NON_OPPOSABLE équivaut à
        # INTERPRÉTATION côté opposabilité, §6ter) -- le plancher doit rattraper.
        llm_risk=RiskTier.FAIBLE,
        floor_conditions=(True,),
        expected_risk=RiskTier.ÉLEVÉ,
    ),
    TriageCase(
        id="triage-llm-faux-negatif-texte-libre",
        llm_risk=RiskTier.FAIBLE,
        floor_conditions=(True,),  # route texte libre (§4bis)
        expected_risk=RiskTier.ÉLEVÉ,
    ),
    TriageCase(
        id="triage-llm-faux-negatif-troncature",
        llm_risk=RiskTier.FAIBLE,
        floor_conditions=(True,),  # drapeau anti-troncature (§7, B2)
        expected_risk=RiskTier.ÉLEVÉ,
    ),
    TriageCase(
        id="triage-llm-faux-negatif-multiple-conditions",
        llm_risk=RiskTier.FAIBLE,
        floor_conditions=(False, False, True),  # une seule condition suffit
        expected_risk=RiskTier.ÉLEVÉ,
    ),
    TriageCase(
        id="triage-control-faible-legitime",
        llm_risk=RiskTier.FAIBLE,
        floor_conditions=(False, False),
        expected_risk=RiskTier.FAIBLE,
    ),
]
