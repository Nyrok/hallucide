from __future__ import annotations

from typing import Iterable, Protocol

from .coverage import DEFAULT_COVERAGE_THRESHOLD, build_echo_back, check_coverage
from .exceptions import RetrievalError, VerificationError
from .retrieval import RetrievalProvider, advance_retrieval
from .triage import RiskTier, apply_risk_floor
from .types import Claim, Intent, IntentExecutionResult, OrchestrationResult, Passage, RetrievalState
from .verifier import verify_claims


class Decomposer(Protocol):
    def decompose(self, message: str) -> list[Intent]:
        ...


class IntentGenerator(Protocol):
    def generate_claims(self, intent: Intent, passage: Passage) -> list[Claim]:
        ...


class Orchestrator:
    def __init__(self, model_provider: object, decomposer: Decomposer, intent_generator: IntentGenerator) -> None:
        self.model_provider = model_provider
        self.decomposer = decomposer
        self.intent_generator = intent_generator

    def run(
        self,
        message: str,
        retrieval_provider: RetrievalProvider,
        retrieval_state: RetrievalState,
        floor_conditions: Iterable[bool],
        llm_risk: RiskTier,
        query: dict[str, str],
        max_hops: int,
        coverage_threshold: float = DEFAULT_COVERAGE_THRESHOLD,
    ) -> OrchestrationResult:
        intents = tuple(self.decomposer.decompose(message))
        if not intents:
            raise ValueError("No intents produced from message.")

        # §4 étape 1bis : contrôle de couverture + echo-back si N>1.
        # Garde-fou borné (§10, E4), pas un verrou : un échec de couverture
        # ne bloque pas la publication, mais il fait partie du plancher de
        # risque déterministe (§2) au même titre que le drapeau anti-troncature
        # -- il ne peut pas être oublié par l'appelant via floor_conditions.
        coverage = check_coverage(message, list(intents), threshold=coverage_threshold)
        echo_back = build_echo_back(list(intents)) if len(intents) > 1 else None

        base_floor_conditions = list(floor_conditions) + [not coverage.passed]
        results: list[IntentExecutionResult] = []

        for intent in intents:
            # §4ter : hop_count et visited_documents bornent le multi-saut AU
            # SEIN d'une intention (INV-006), ils ne doivent pas fuiter d'une
            # intention à l'autre -- deux questions distinctes peuvent
            # légitimement s'appuyer sur le même article. On réinitialise donc
            # la chaîne de récupération par intention, tout en conservant le
            # budget global (ressource partagée, épuisable sur l'ensemble).
            intent_state = RetrievalState(remaining_budget=retrieval_state.remaining_budget)
            passage, intent_state = advance_retrieval(intent, retrieval_provider, query, intent_state, max_hops)
            retrieval_state.remaining_budget = intent_state.remaining_budget
            claims = self.intent_generator.generate_claims(intent, passage)

            # §4 étape 8 : un échec du contrôle verbatim est un REFUS pour
            # CETTE intention (§7bis), pas un crash de tout le pipeline -- les
            # autres intentions continuent, et le refus reste journalisable
            # (§8, compliance_status BLOCKED). Un refus force le risque élevé.
            try:
                verification = verify_claims(claims, passage)
            except VerificationError as exc:
                verification = exc.result
                results.append(
                    IntentExecutionResult(
                        intent=intent, passage=passage, verification=verification, risk_tier=RiskTier.ÉLEVÉ
                    )
                )
                continue

            # §4bis, piège A3 : une référence inférée (pas copiée depuis la
            # question) élève le risque pour cette intention spécifiquement,
            # au même titre que la couverture l'élève globalement.
            slot_inferred = bool(passage.metadata.get("slot_inferred", False))
            # §7, piège B2 : une citation possiblement tronquée (connecteur de
            # restriction omis juste après) élève le risque pour cette intention.
            truncation_flagged = any(c.truncation_flagged for c in verification.claims)
            # §2/§4bis : la route texte libre (recherche par proximité, jamais
            # par identité exacte) fait partie de la liste explicite du
            # plancher de risque -- piège C1, "pertinence non garantie".
            pertinence_non_garantie = bool(passage.metadata.get("pertinence_non_garantie", False))
            risk_tier = apply_risk_floor(
                llm_risk,
                base_floor_conditions + [slot_inferred, truncation_flagged, pertinence_non_garantie],
            )

            results.append(IntentExecutionResult(intent=intent, passage=passage, verification=verification, risk_tier=risk_tier))

        return OrchestrationResult(
            intents=intents,
            results=tuple(results),
            echo_back=echo_back,
            coverage_passed=coverage.passed,
            coverage_ratio=coverage.ratio,
            coverage_missing_tokens=coverage.missing_tokens,
        )
