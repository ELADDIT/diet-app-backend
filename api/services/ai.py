"""AI service integration helpers for generating diet and workout suggestions."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


class AIServiceError(RuntimeError):
    """Represents failures while communicating with the AI provider."""


@dataclass
class AIConfig:
    """Holds configuration for the AI integration."""

    api_key: str
    model: str
    base_url: Optional[str]
    diet_prompt_template: str
    workout_prompt_template: str
    chat_prompt_template: str

    @classmethod
    def from_env(cls) -> "AIConfig":
        """Build a configuration object using environment variables."""

        return cls(
            api_key=os.getenv("AI_API_KEY", ""),
            model=os.getenv("AI_MODEL_NAME", "gpt-4o-mini"),
            base_url=os.getenv("AI_BASE_URL"),
            diet_prompt_template=os.getenv(
                "AI_PROMPT_TEMPLATE_DIET",
                (
                    "Create a concise one-week meal plan for {user_name} who aims to {goal}. "
                    "Reference the following metrics when relevant: {metrics}."
                ),
            ),
            workout_prompt_template=os.getenv(
                "AI_PROMPT_TEMPLATE_WORKOUT",
                (
                    "Draft a four-session workout routine for {user_name} who aims to {goal}. "
                    "Consider these metrics: {metrics}."
                ),
            ),
            chat_prompt_template=os.getenv(
                "AI_PROMPT_TEMPLATE_CHAT",
                (
                    "You are a nutrition and fitness assistant for {user_name}. "
                    "Prior conversation: {history}\nUser: {message}\nAssistant:"
                ),
            ),
        )


class _EchoAIClient:
    """A minimal client placeholder used for deterministic behaviour in tests."""

    def __init__(self, *, base_url: Optional[str], api_key: str) -> None:
        self.base_url = base_url
        self.api_key = api_key

    def generate(self, *, prompt: str, model: str) -> str:
        if not self.api_key:
            raise AIServiceError(
                "AI_API_KEY is not configured. Set the environment variable to enable AI features."
            )
        cleaned_prompt = " ".join(prompt.split())
        return f"[{model}] {cleaned_prompt}"


class AIService:
    """High level helper responsible for AI interactions."""

    def __init__(self, config: Optional[AIConfig] = None, client: Optional[_EchoAIClient] = None) -> None:
        self.config = config or AIConfig.from_env()
        self._client = client or _EchoAIClient(base_url=self.config.base_url, api_key=self.config.api_key)

    @staticmethod
    def _stringify_metrics(metrics: Optional[Dict[str, Any]]) -> str:
        if not metrics:
            return "No additional metrics provided."
        if isinstance(metrics, dict):
            items: Iterable[str] = (f"{key}: {metrics[key]}" for key in sorted(metrics))
            return ", ".join(items)
        return str(metrics)

    @staticmethod
    def _stringify_history(history: Optional[Iterable[Any]]) -> str:
        if not history:
            return "No previous conversation."
        formatted: List[str] = []
        for entry in history:
            if isinstance(entry, dict):
                role = entry.get("role", "user")
                content = entry.get("content", "")
                formatted.append(f"{role}: {content}")
            else:
                formatted.append(str(entry))
        return " | ".join(formatted)

    def generate_diet_plan(self, *, user: Any, metrics: Optional[Dict[str, Any]], goal: str) -> Dict[str, str]:
        prompt = self.config.diet_prompt_template.format(
            user_name=getattr(user, "full_name", None) or getattr(user, "username", "user"),
            goal=goal,
            metrics=self._stringify_metrics(metrics),
        )
        response = self._client.generate(prompt=prompt, model=self.config.model)
        return {"prompt": prompt, "response": response}

    def generate_workout_plan(
        self, *, user: Any, metrics: Optional[Dict[str, Any]], goal: str
    ) -> Dict[str, str]:
        prompt = self.config.workout_prompt_template.format(
            user_name=getattr(user, "full_name", None) or getattr(user, "username", "user"),
            goal=goal,
            metrics=self._stringify_metrics(metrics),
        )
        response = self._client.generate(prompt=prompt, model=self.config.model)
        return {"prompt": prompt, "response": response}

    def chat(
        self,
        *,
        user: Any,
        message: str,
        history: Optional[Iterable[Any]] = None,
    ) -> Dict[str, str]:
        prompt = self.config.chat_prompt_template.format(
            user_name=getattr(user, "full_name", None) or getattr(user, "username", "user"),
            history=self._stringify_history(history),
            message=message,
        )
        response = self._client.generate(prompt=prompt, model=self.config.model)
        return {"prompt": prompt, "response": response}


ai_service = AIService()

__all__ = ["AIConfig", "AIService", "AIServiceError", "ai_service"]
