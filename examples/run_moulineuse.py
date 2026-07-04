import sys
from pathlib import Path

workspace_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(workspace_root))

from hallucide._3_retrieval.moulineuse import MoulineuseRetrievalProvider
from hallucide.core_types.types import Intent, RetrievalState
from hallucide._4_verification.verifier import verify_claims
from hallucide.core_types.types import Claim, ClaimStatus


def main() -> None:
    provider = MoulineuseRetrievalProvider()
    intent = Intent(id="1", question="Que dit l'article 1103 du Code civil ?")
    state = RetrievalState(hop_count=0, visited_documents=set(), remaining_budget=5)

    passage = provider.retrieve(
        intent,
        state,
        {"route": "code_article", "article": "1103", "code": "code civil"},
    )
    print(f"source_id={passage.source_id} opposable={passage.opposable}")
    print(f"text={passage.text}")

    claim = Claim(ref=passage.text, status=ClaimStatus.AUTHENTIFIÉ)
    result = verify_claims([claim], passage)
    print(f"verbatim_check={result.verbatim_check} status={result.claims[0].status}")


if __name__ == "__main__":
    main()
