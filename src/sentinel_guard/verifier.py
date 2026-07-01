from __future__ import annotations

import re
from typing import Iterable

from .exceptions import InvalidClaimError, VerificationError
from .normalization import normalize_numeric, normalize_text
from .types import Claim, ClaimStatus, Passage, VerificationResult

# §7, piège B2 : connecteurs de restriction dont l'omission juste après une
# citation signale une troncature possible. Portée explicitement limitée à
# l'adjacence textuelle immédiate (cf. §7) -- une exception plus loin dans
# le texte, un autre article ou un décret échappe à cette heuristique.
_RESTRICTION_CONNECTORS = (
    "sauf si",
    "sauf",
    "toutefois",
    "sous réserve",
    "à l'exception",
    "par dérogation",
)
_LEADING_PUNCTUATION_PATTERN = re.compile(r"^[\s,;:.)\]]+")


def _starts_with_connector(remainder_lower: str, connector: str) -> bool:
    """Le reste commence-t-il par `connector` suivi d'une frontière de mot ?
    Évite qu'un mot plus long partageant le préfixe (ex. "sauferie" pour
    "sauf") déclenche un faux drapeau de troncature (piège B2)."""
    if not remainder_lower.startswith(connector):
        return False
    after = remainder_lower[len(connector):]
    return after == "" or not (after[0].isalnum() or after[0] in "'’-")


def _is_contiguous_subsegment(candidate: str, source: str) -> bool:
    normalized_candidate = normalize_text(candidate)
    normalized_source = normalize_text(source)
    return normalized_candidate in normalized_source


def _detect_ellipsis(text: str) -> bool:
    return "…" in text or "..." in text


def _detect_adjacent_truncation(candidate: str, source: str) -> bool:
    normalized_candidate = normalize_text(candidate)
    normalized_source = normalize_text(source)

    if not normalized_candidate:
        return False

    # Si la citation apparaît plusieurs fois dans le passage, une seule
    # occurrence suffisamment "à risque" (suivie d'une restriction omise)
    # doit déclencher le drapeau -- ne pas se limiter à la première trouvée.
    start = 0
    while True:
        start = normalized_source.find(normalized_candidate, start)
        if start == -1:
            return False

        remainder = normalized_source[start + len(normalized_candidate):]
        remainder = _LEADING_PUNCTUATION_PATTERN.sub("", remainder)
        remainder_lower = remainder.lower()

        if any(_starts_with_connector(remainder_lower, connector) for connector in _RESTRICTION_CONNECTORS):
            return True

        start += 1


# §7 : ancrage d'une reformulation. Une INTERPRÉTATION n'exige pas le
# verbatim exact (par définition c'est une paraphrase), mais elle doit être
# ANCRÉE dans le passage : ses termes significatifs doivent majoritairement
# provenir de la source, sinon c'est une invention pure (NON_AUTHENTIFIÉ).
# Contrôle purement lexical et déterministe (aucun LLM, INV-007) -- il ne
# juge pas la justesse sémantique, seulement l'ancrage des termes.
_INTERPRETATION_ANCHOR_THRESHOLD = 0.6
_TOKEN_PATTERN = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)
_ANCHOR_STOPWORDS = frozenset(
    {
        "le", "la", "les", "un", "une", "des", "de", "du", "et", "ou", "est",
        "que", "qui", "quoi", "ce", "cette", "ces", "à", "au", "aux", "en",
        "dans", "sur", "pour", "par", "avec", "sans", "se", "sa", "son", "ses",
        "il", "elle", "on", "ne", "pas", "plus", "leur", "leurs", "sont", "a",
        "d", "l", "qu", "s", "n", "the",
    }
)


def _anchor_tokens(text: str) -> set[str]:
    tokens = _TOKEN_PATTERN.findall(normalize_text(text).lower())
    return {t for t in tokens if t not in _ANCHOR_STOPWORDS and (t.isdigit() or len(t) > 1)}


def _interpretation_is_anchored(candidate: str, source: str) -> bool:
    candidate_tokens = _anchor_tokens(candidate)
    if not candidate_tokens:
        return False
    source_tokens = _anchor_tokens(source)
    overlap = len(candidate_tokens & source_tokens) / len(candidate_tokens)
    return overlap >= _INTERPRETATION_ANCHOR_THRESHOLD


def _verify_text_claim(claim: Claim, passage: Passage) -> ClaimStatus:
    if claim.status == ClaimStatus.NON_AUTHENTIFIÉ:
        raise InvalidClaimError("Claim status cannot be NON_AUTHENTIFIÉ for initial verification.")
    if claim.status == ClaimStatus.DONNÉE_TRACÉE:
        raise InvalidClaimError("Text verification path cannot process DONNÉE_TRACÉE claims.")

    is_exact = _is_contiguous_subsegment(claim.ref, passage.text)

    if not is_exact:
        # §7 : le modèle a marqué ce claim comme une reformulation
        # (INTERPRÉTATION). On l'accepte si et seulement si ses termes sont
        # ancrés dans le passage -- sinon c'est une invention pure.
        if claim.status == ClaimStatus.INTERPRÉTATION and _interpretation_is_anchored(claim.ref, passage.text):
            return ClaimStatus.INTERPRÉTATION
        return ClaimStatus.NON_AUTHENTIFIÉ

    # Verbatim exact trouvé dans le passage.
    if _detect_ellipsis(claim.ref):
        return ClaimStatus.INTERPRÉTATION  # anti-épissage (§7)

    if not passage.opposable:
        return ClaimStatus.CITÉ_NON_OPPOSABLE

    return ClaimStatus.AUTHENTIFIÉ


def _verify_traced_data_claim(claim: Claim, passage: Passage) -> ClaimStatus:
    normalized_ref = normalize_numeric(claim.ref)
    normalized_text = normalize_numeric(passage.text)
    if normalized_ref != normalized_text:
        return ClaimStatus.NON_AUTHENTIFIÉ
    return ClaimStatus.DONNÉE_TRACÉE


_FLAGGABLE_STATUSES = (ClaimStatus.AUTHENTIFIÉ, ClaimStatus.CITÉ_NON_OPPOSABLE)


def verify_claims(claims: Iterable[Claim], passage: Passage) -> VerificationResult:
    verified_claims: list[Claim] = []
    for claim in claims:
        if claim.status not in ClaimStatus:
            raise InvalidClaimError(f"Unsupported claim status: {claim.status}")

        if claim.status == ClaimStatus.DONNÉE_TRACÉE:
            verified_status = _verify_traced_data_claim(claim, passage)
            truncation_flagged = False
        else:
            verified_status = _verify_text_claim(claim, passage)
            # §7, B2 : seules les citations littérales valides peuvent être
            # tronquées de façon pertinente (NON_AUTHENTIFIÉ/INTERPRÉTATION
            # sont déjà non opposables pour d'autres raisons).
            truncation_flagged = (
                verified_status in _FLAGGABLE_STATUSES
                and _detect_adjacent_truncation(claim.ref, passage.text)
            )

        verified_claims.append(
            Claim(ref=claim.ref, status=verified_status, truncation_flagged=truncation_flagged)
        )

    verbatim_check = "PASS" if all(c.status != ClaimStatus.NON_AUTHENTIFIÉ for c in verified_claims) else "FAIL"
    result = VerificationResult(verbatim_check=verbatim_check, claims=tuple(verified_claims))
    if verbatim_check == "FAIL":
        # §7bis : refus. On attache le résultat complet à l'exception pour
        # qu'un appelant (l'orchestrateur) puisse le journaliser comme un
        # état BLOCKED (§8) plutôt que de perdre le détail dans le crash.
        raise VerificationError(
            "One or more claims failed deterministic verification.", result=result
        )

    return result
