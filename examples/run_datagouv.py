import sys
from pathlib import Path

workspace_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(workspace_root / "src"))

from sentinel_guard._3_retrieval.datagouv import DataGouvRetrievalProvider
from sentinel_guard.core_types.types import Claim, ClaimStatus, Intent, RetrievalState
from sentinel_guard._4_verification.verifier import verify_claims


def main() -> None:
    provider = DataGouvRetrievalProvider()
    intent = Intent(id="1", question="Combien d'inscrits en Guadeloupe aux législatives 2024 ?")
    state = RetrievalState(hop_count=0, visited_documents=set(), remaining_budget=5)

    passage = provider.retrieve(
        intent,
        state,
        {
            "dataset_id": "6682d0c255dcda5df20b1d90",
            "resource_id": "f69ffab7-fe37-494e-ad6d-a7cfc80ddc1f",
            "filter_column": "Libellé région",
            "filter_value": "Guadeloupe",
            "target_column": "Inscrits",
        },
    )
    print(f"source_id={passage.source_id} source_type={passage.source_type} opposable={passage.opposable}")
    print(f"cellule={passage.text}")
    print(f"dataset_id={passage.metadata['dataset_id']}")

    claim = Claim(ref=passage.text, status=ClaimStatus.DONNÉE_TRACÉE)
    result = verify_claims([claim], passage)
    print(f"verbatim_check={result.verbatim_check} status={result.claims[0].status}")


if __name__ == "__main__":
    main()
