import sys
from pathlib import Path

workspace_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(workspace_root / "src"))

from hallucide import MockModelProvider, MultiSourceRetrievalProvider, Hallucide
from hallucide._6_validation.human_validation import ValidationDecision, ValidationKey
from hallucide._3_retrieval.moulineuse import MoulineuseRetrievalProvider


def main() -> None:
    # Route texte libre (§4bis) : pertinence non garantie -> risque élevé
    # automatique (§2), donc validation humaine requise avant publication
    # (§4 étape 9), sans avoir à forcer artificiellement les conditions plancher.
    model_provider = MockModelProvider(
        responses={
            "decompose": '[{"id": "1", "question": "congé menstruel"}]',
            "claims": '[{"ref": "Ordonnance n°62-91 du 26 janvier 1962 RELATIVE AU CONGE SPECIAL DE CERTAINS FONCTIONNAIRES", "status": "AUTHENTIFIÉ"}]',
        }
    )

    guard = Hallucide(
        model_provider=model_provider,
        retrieval_provider=MultiSourceRetrievalProvider(moulineuse=MoulineuseRetrievalProvider()),
    )

    result = guard.ask(message="congé menstruel", query={"route": "texte_libre", "query": "congé menstruel"})
    intent_result = result.orchestration.results[0]

    print("=== Premier appel (aucune décision humaine encore) ===")
    print(f"risk_tier={intent_result.risk_tier.value}")
    print(f"published={result.published}")
    print(f"human_validation={result.compliance_entries[0].human_validation}")
    print()

    print("=== Décision humaine : approbation par un agent (réf. pseudonymisée) ===")
    key = ValidationKey.from_result(intent_result)
    guard.validation_registry.record_decision(
        key, ValidationDecision.APPROVED, validator_ref="dep-hash-9f3a21",
        comment="Source réelle mais hors-sujet (piège C1) -- vérifié manuellement, on l'affiche avec avertissement.",
    )

    result2 = guard.ask(message="congé menstruel", query={"route": "texte_libre", "query": "congé menstruel"})
    print(f"published={result2.published}")
    print(f"human_validation={result2.compliance_entries[0].human_validation}")


if __name__ == "__main__":
    main()
