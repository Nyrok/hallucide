import sys
from pathlib import Path

workspace_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(workspace_root / "src"))

from sentinel_guard._1_decomposition.orchestration import Orchestrator
from sentinel_guard._5_triage.triage import RiskTier
from sentinel_guard.core_types.types import Claim, ClaimStatus, Intent, Passage, RetrievalState


class TwoQuestionDecomposer:
    """Simule une décomposition réussie : N=2 questions, N=2 intentions."""

    def decompose(self, message: str):
        return [
            Intent(id="1", question="Quel est le délai de rétractation ?"),
            Intent(id="2", question="Quelle est la sanction en cas de non-respect du délai ?"),
        ]


class ForgetfulDecomposer:
    """Simule le piège E4 (§10) : la décomposition oublie la seconde question."""

    def decompose(self, message: str):
        return [Intent(id="1", question="Quel est le délai de rétractation ?")]


class DummyIntentGenerator:
    def generate_claims(self, intent: Intent, passage: Passage):
        return [Claim(ref=passage.text, status=ClaimStatus.AUTHENTIFIÉ)]


class DummyRetrievalProvider:
    def retrieve(self, intent: Intent, state: RetrievalState, query: dict[str, str]):
        return Passage(
            source_id=f"doc-{intent.id}",
            source_type="normatif",
            opposable=True,
            text="Passage authentique.",
            metadata={},
        )


def run(decomposer, label: str) -> None:
    message = "Quel est le délai de rétractation et quelle est la sanction en cas de non-respect du délai ?"
    orchestrator = Orchestrator(model_provider=object(), decomposer=decomposer, intent_generator=DummyIntentGenerator())
    result = orchestrator.run(
        message=message,
        retrieval_provider=DummyRetrievalProvider(),
        retrieval_state=RetrievalState(),
        floor_conditions=[False],
        llm_risk=RiskTier.FAIBLE,
        query={},
        max_hops=2,
    )

    print(f"--- {label} ---")
    print(f"echo_back:\n{result.echo_back}")
    print(f"coverage_passed={result.coverage_passed} ratio={result.coverage_ratio:.2f} missing={result.coverage_missing_tokens}")
    print(f"risk_tier={result.results[0].risk_tier.value}")
    print()


def main() -> None:
    run(TwoQuestionDecomposer(), "décomposition complète (N=2)")
    run(ForgetfulDecomposer(), "piège E4 : intention oubliée (N=1 au lieu de 2)")


if __name__ == "__main__":
    main()
