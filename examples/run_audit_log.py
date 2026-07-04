import sys
from pathlib import Path

workspace_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(workspace_root))

from hallucide._7_audit.audit import build_compliance_log
from hallucide._3_retrieval.moulineuse import MoulineuseRetrievalProvider
from hallucide._1_decomposition.orchestration import Orchestrator
from hallucide._5_triage.triage import RiskTier
from hallucide.core_types.types import Claim, ClaimStatus, Intent, Passage, RetrievalState


class SingleIntentDecomposer:
    def decompose(self, message: str):
        return [Intent(id="1", question=message)]


class VerbatimIntentGenerator:
    """Génère un seul claim qui reprend le passage mot pour mot (étape 6 de la spec)."""

    def generate_claims(self, intent: Intent, passage: Passage):
        return [Claim(ref=passage.text, status=ClaimStatus.AUTHENTIFIÉ)]


def main() -> None:
    orchestrator = Orchestrator(
        model_provider=object(),
        decomposer=SingleIntentDecomposer(),
        intent_generator=VerbatimIntentGenerator(),
    )

    message = "Que dit l'article 1103 du Code civil ?"
    result = orchestrator.run(
        message=message,
        retrieval_provider=MoulineuseRetrievalProvider(),
        retrieval_state=RetrievalState(),
        floor_conditions=[False],
        llm_risk=RiskTier.FAIBLE,
        query={"route": "code_article", "article": "1103", "code": "code civil"},
        max_hops=3,
    )

    print(f"echo_back={result.echo_back!r} coverage_passed={result.coverage_passed} ratio={result.coverage_ratio:.2f}")

    entries = build_compliance_log(
        result,
        provider="local-ollama",
        model="llama3",
        message=message,
    )
    for entry in entries:
        print(entry.to_json())


if __name__ == "__main__":
    main()
