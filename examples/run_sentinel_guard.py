import sys
from pathlib import Path

workspace_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(workspace_root / "src"))

from hallucide import MockModelProvider, MultiSourceRetrievalProvider, Hallucide
from hallucide._3_retrieval.moulineuse import MoulineuseRetrievalProvider


def main() -> None:
    # MockModelProvider remplace ici un vrai LLM (Gemini/Mistral) pour ne pas
    # exiger de clé API dans cette démonstration -- voir examples/run_gemini.py
    # et run_mistral.py pour le câblage avec un vrai modèle. La récupération,
    # elle, est réelle (Moulineuse en direct), pas mockée.
    model_provider = MockModelProvider(
        responses={
            "decompose": '[{"id": "1", "question": "Que dit l\'article 1103 du Code civil ?"}]',
            "claims": (
                '[{"ref": "Les contrats légalement formés tiennent lieu de loi '
                'à ceux qui les ont faits.", "status": "AUTHENTIFIÉ"}]'
            ),
        }
    )

    guard = Hallucide(
        model_provider=model_provider,
        retrieval_provider=MultiSourceRetrievalProvider(moulineuse=MoulineuseRetrievalProvider()),
    )

    result = guard.ask(
        message="Que dit l'article 1103 du Code civil ?",
        query={"route": "code_article", "article": "1103", "code": "code civil"},
    )

    intent_result = result.orchestration.results[0]
    print(f"session_ref={result.session_ref}")
    print(f"source_id={intent_result.passage.source_id}")
    print(f"statut={intent_result.verification.claims[0].status.value}")
    print(f"risk_tier={intent_result.risk_tier.value}")
    print()
    print("Journal Conformité (jamais la question, §13.4) :")
    for entry in result.compliance_entries:
        print(entry.to_json())


if __name__ == "__main__":
    main()
