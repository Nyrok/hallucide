from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Set


class ClaimStatus(str, Enum):
    AUTHENTIFIÉ = "AUTHENTIFIÉ"
    CITÉ_NON_OPPOSABLE = "CITÉ_NON_OPPOSABLE"
    INTERPRÉTATION = "INTERPRÉTATION"
    NON_AUTHENTIFIÉ = "NON_AUTHENTIFIÉ"
    DONNÉE_TRACÉE = "DONNÉE_TRACÉE"


class RiskTier(str, Enum):
    FAIBLE = "faible"
    ÉLEVÉ = "élevé"


@dataclass(frozen=True)
class Intent:
    id: str
    question: str


@dataclass(frozen=True)
class Passage:
    source_id: str
    source_type: str
    opposable: bool
    text: str
    metadata: Dict[str, Any]


@dataclass(frozen=True)
class Claim:
    ref: str
    status: ClaimStatus
    truncation_flagged: bool = False


@dataclass(frozen=True)
class VerificationResult:
    verbatim_check: str
    claims: tuple[Claim, ...]


@dataclass(frozen=True)
class IntentExecutionResult:
    intent: Intent
    passage: Passage
    verification: VerificationResult
    risk_tier: RiskTier


@dataclass(frozen=True)
class OrchestrationResult:
    intents: tuple[Intent, ...]
    results: tuple[IntentExecutionResult, ...]
    echo_back: Optional[str] = None
    coverage_passed: Optional[bool] = None
    coverage_ratio: Optional[float] = None
    coverage_missing_tokens: tuple[str, ...] = ()


@dataclass
class RetrievalState:
    hop_count: int = 0
    visited_documents: Set[str] = None
    remaining_budget: int = 1000

    def __post_init__(self) -> None:
        if self.visited_documents is None:
            self.visited_documents = set()
