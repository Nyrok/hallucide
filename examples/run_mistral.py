import os
import sys
from pathlib import Path

workspace_root = Path(__file__).resolve().parents[1]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


load_env_file(workspace_root / ".env")

sys.path.insert(0, str(workspace_root / "src"))

from sentinel_guard import (
    MistralModelProvider,
    Orchestrator,
    PromptBasedDecomposer,
    PromptBasedIntentGenerator,
    RetrievalState,
    RiskTier,
)
from sentinel_guard.retrieval import RetrievalProvider
from sentinel_guard.types import Intent, Passage


class DummyRetrievalProvider(RetrievalProvider):
    """Passage volontairement citable (pas un texte générique) : le LLM doit
    pouvoir y trouver une citation verbatim correspondant à la question pour
    que le contrôle déterministe (§7) la confirme AUTHENTIFIÉ plutôt que de
    refuser, ce qui serait le comportement correct mais peu démonstratif si
    le passage n'avait aucun rapport avec la question.
    """

    def retrieve(self, intent: Intent, state: RetrievalState, query: dict[str, str]) -> Passage:
        return Passage(
            source_id=query["source_id"],
            source_type="normatif",
            opposable=True,
            text="Les contrats légalement formés tiennent lieu de loi à ceux qui les ont faits.",
            metadata={"query": query},
        )


def main() -> None:
    api_key = os.environ["MISTRAL_API_KEY"]
    mistral = MistralModelProvider(api_key=api_key)

    decomposer = PromptBasedDecomposer(mistral)
    intent_generator = PromptBasedIntentGenerator(mistral)

    orchestrator = Orchestrator(
        model_provider=mistral,
        decomposer=decomposer,
        intent_generator=intent_generator,
    )

    result = orchestrator.run(
        message="Quelle est la règle applicable à ce cas ?",
        retrieval_provider=DummyRetrievalProvider(),
        retrieval_state=RetrievalState(hop_count=0, visited_documents=set(), remaining_budget=5),
        floor_conditions=[False],
        llm_risk=RiskTier.FAIBLE,
        query={"source_id": "doc1"},
        max_hops=3,
    )

    print(result)


if __name__ == "__main__":
    main()
