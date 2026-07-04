import sys
from pathlib import Path

workspace_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(workspace_root))

from hallucide._7_audit.audit import build_compliance_log
from hallucide._3_retrieval.moulineuse import MoulineuseRetrievalProvider
from hallucide._1_decomposition.orchestration import Orchestrator
from hallucide._7_audit.sovereign_log import (
    SovereignLogStore,
    build_access_log_entry,
    generate_session_ref,
)
from hallucide._5_triage.triage import RiskTier
from hallucide.core_types.types import Claim, ClaimStatus, Intent, Passage, RetrievalState


class SingleIntentDecomposer:
    def decompose(self, message: str):
        return [Intent(id="1", question=message)]


class VerbatimIntentGenerator:
    def generate_claims(self, intent: Intent, passage: Passage):
        return [Claim(ref=passage.text, status=ClaimStatus.AUTHENTIFIÉ)]


def main() -> None:
    store = SovereignLogStore()

    # §13.4 : le jeton de session est généré indépendamment de l'identité du
    # député -- la table de correspondance (jeton <-> identité) n'existe que
    # côté journal Accès, jamais dans la même structure que le journal Conformité.
    session_ref = generate_session_ref()

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

    compliance_entries = build_compliance_log(
        result,
        provider="local-ollama",
        model="llama3",
        message=message,
        session_ref=session_ref,
        confidential=True,  # §13.4 : mode souverain, query jamais journalisée
    )
    for entry in compliance_entries:
        store.record_compliance(entry)

    access_entry = build_access_log_entry(
        pseudonymized_identity="dep-hash-9f3a21",  # jamais le nom du député
        request_count=1,
        session_ref=session_ref,
    )
    store.record_access(access_entry)

    print("=== Journal Conformité (ouvert, anonymisé) ===")
    for entry in store.compliance_entries:
        print(entry.to_json())

    print()
    print("=== Journal Accès (restreint, pseudonymisé) ===")
    for entry in store.access_entries:
        print(entry.to_json())

    print()
    print("Les deux journaux partagent le même session_ref opaque, mais aucune")
    print("structure ne les joint par identité -- la non-corrélation est réelle,")
    print("pas seulement déclarée.")


if __name__ == "__main__":
    main()
