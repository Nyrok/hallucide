from __future__ import annotations

import json
import re
from typing import Any, Protocol

from .exceptions import SentinelGuardError, VerificationError
from .types import Claim, ClaimStatus, Intent, Passage


class ModelProvider(Protocol):
    supports_forced_tool_calling: bool

    def generate(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, str]] | None = None,
        tool_choice: str | None = None,
    ) -> dict[str, Any]:
        ...


class MockModelProvider:
    def __init__(
        self,
        responses: dict[str, str] | None = None,
        supports_forced_tool_calling: bool = False,
    ) -> None:
        self.supports_forced_tool_calling = supports_forced_tool_calling
        self._responses = responses or {}

    def generate(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, str]] | None = None,
        tool_choice: str | None = None,
    ) -> dict[str, Any]:
        if tool_choice == "required" and not self.supports_forced_tool_calling:
            raise SentinelGuardError("Provider does not support forced tool calling.")

        prompt = next((m for m in messages if m.get("role") == "system"), None)
        if not prompt or not isinstance(prompt.get("content"), str):
            raise SentinelGuardError("Unable to infer prompt type from model messages.")

        content = prompt["content"]
        if "Découpe le message" in content:
            key = "decompose"
        elif "CITATION vs REFORMULATION" in content:
            key = "claims"
        else:
            key = "default"

        return {"text": self._responses.get(key, "")}


class PromptBuilder:
    @staticmethod
    def build_decomposition_prompt(message: str) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "Découpe le message suivant en intentions atomiques. "
                    "Réponds uniquement avec un tableau JSON de la forme "
                    "[{\"id\": \"1\", \"question\": \"...\"}, ...]."
                ),
            },
            {"role": "user", "content": message},
        ]

    @staticmethod
    def build_claim_generation_prompt(intent: Intent, passage: Passage) -> list[dict[str, str]]:
        # Prompt B (§5) : distinction explicite citation vs paraphrase. Le
        # modèle doit copier le VERBATIM exact pour AUTHENTIFIÉ, et marquer
        # toute reformulation comme INTERPRÉTATION (non opposable, §7). Le
        # vérificateur déterministe reste l'autorité finale (§2) : ce prompt
        # améliore la coopération, il ne remplace pas le contrôle verbatim.
        return [
            {
                "role": "system",
                "content": (
                    "À partir du passage officiel fourni, produis les affirmations qui RÉPONDENT "
                    "à la question, en t'appuyant uniquement sur ce passage.\n"
                    "Règle CITATION vs REFORMULATION :\n"
                    "  - Extrait repris MOT POUR MOT du passage -> statut \"AUTHENTIFIÉ\".\n"
                    "  - Reformulation avec tes propres mots (résumé fidèle) -> statut \"INTERPRÉTATION\".\n"
                    "N'ajoute aucun fait absent du passage. Si le passage contient de quoi répondre, "
                    "produis au moins une affirmation ; s'il ne contient vraiment rien de pertinent, "
                    "renvoie un tableau vide [].\n"
                    "Réponds UNIQUEMENT par un tableau JSON de la forme "
                    "[{\"ref\": \"...\", \"status\": \"AUTHENTIFIÉ|INTERPRÉTATION\"}, ...]."
                ),
            },
            {"role": "user", "content": f"Question: {intent.question}\nPassage: {passage.text}"},
        ]


_MARKDOWN_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


def _strip_markdown_fence(text: str) -> str:
    """Certains LLM (Gemini observé en direct) enveloppent une réponse JSON
    dans une balise de code markdown malgré la consigne "réponds uniquement
    par...". Le contrôle verbatim (§7) ne dépend jamais de cette tolérance --
    elle ne fait qu'aider le parsing JSON en amont, purement cosmétique.
    """
    match = _MARKDOWN_FENCE_PATTERN.match(text.strip())
    return match.group(1).strip() if match else text


def _parse_json_response(text: str) -> Any:
    try:
        return json.loads(_strip_markdown_fence(text))
    except json.JSONDecodeError as exc:
        raise VerificationError("LLM response is not valid JSON.") from exc


def _extract_text_response(response: dict[str, Any]) -> str:
    if not isinstance(response, dict):
        raise SentinelGuardError("LLM response must be a JSON object.")

    text = response.get("text")
    if not isinstance(text, str):
        raise SentinelGuardError("LLM response missing text output.")

    text = text.strip()
    if not text:
        raise SentinelGuardError("LLM returned empty text response.")

    return text


class PromptBasedDecomposer:
    """§6 : la décomposition ne récupère jamais de passage elle-même --
    l'orchestrateur appelle toujours MCP directement (§4 étape 4), jamais le
    LLM. Cette classe n'a donc aucun outil à forcer ; le forçage natif
    (`tool_choice: required`) décrit par §6 ne s'applique qu'à un backend qui
    laisserait le modèle appeler `search_tricoteuses` lui-même -- ce que
    l'architecture actuelle n'a jamais fait, en choisissant la voie
    équivalente explicitement autorisée par §6 ("backend local sans
    forçage") pour tous les backends, pas seulement les modèles locaux.
    """

    def __init__(self, model_provider: ModelProvider) -> None:
        self.model_provider = model_provider

    def decompose(self, message: str) -> list[Intent]:
        response = self.model_provider.generate(
            messages=PromptBuilder.build_decomposition_prompt(message),
            tools=[],
            tool_choice=None,
        )
        text = _extract_text_response(response)
        payload = _parse_json_response(text)
        if not isinstance(payload, list):
            raise SentinelGuardError("Expected a JSON array of intents.")

        intents: list[Intent] = []
        for item in payload:
            if not isinstance(item, dict) or "id" not in item or "question" not in item:
                raise SentinelGuardError("Invalid intent payload from LLM.")
            intents.append(Intent(id=str(item["id"]), question=str(item["question"])))
        return intents


class PromptBasedIntentGenerator:
    """§6 : la génération contrainte (étape 6) reçoit le passage déjà
    récupéré par l'orchestrateur -- elle n'appelle jamais elle-même
    `search_tricoteuses`, donc aucun outil à forcer ici non plus.
    """

    def __init__(self, model_provider: ModelProvider) -> None:
        self.model_provider = model_provider

    def generate_claims(self, intent: Intent, passage: Passage) -> list[Claim]:
        response = self.model_provider.generate(
            messages=PromptBuilder.build_claim_generation_prompt(intent, passage),
            tools=[],
            tool_choice=None,
        )
        text = _extract_text_response(response)
        payload = _parse_json_response(text)
        if not isinstance(payload, list):
            raise SentinelGuardError("Expected a JSON array of claims.")

        claims: list[Claim] = []
        for item in payload:
            if not isinstance(item, dict) or "ref" not in item or "status" not in item:
                raise SentinelGuardError("Invalid claim payload from LLM.")
            status_value = str(item["status"])
            try:
                status = ClaimStatus(status_value)
            except ValueError as exc:
                raise SentinelGuardError(f"Unsupported claim status: {status_value}") from exc
            claims.append(Claim(ref=str(item["ref"]), status=status))
        return claims
