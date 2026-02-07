from __future__ import annotations

import json
import logging
from typing import Any


logger = logging.getLogger(__name__)


class OpenAIHelper:
    def __init__(self, api_key: str | None, chat_model: str, embedding_model: str):
        self.api_key = api_key
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self._client = None

        if not api_key:
            return

        try:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAI client unavailable, falling back to local logic: %s", exc.__class__.__name__)
            self._client = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def embed_texts(self, texts: list[str]) -> list[list[float]] | None:
        if not self._client:
            return None
        try:
            response = self._client.embeddings.create(model=self.embedding_model, input=texts)
            return [item.embedding for item in response.data]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Embedding request failed, using TF-IDF fallback: %s", exc.__class__.__name__)
            return None

    def generate_card(self, context: dict[str, Any]) -> dict[str, Any] | None:
        if not self._client:
            return None

        prompt = (
            "You are generating a concise candidate card JSON. "
            "Return only JSON with keys: headline, summary, top_skills, strengths, risks. "
            "top_skills/strengths/risks must be arrays of strings."
        )

        try:
            response = self._client.chat.completions.create(
                model=self.chat_model,
                response_format={"type": "json_object"},
                temperature=0.2,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(context)},
                ],
            )
            content = response.choices[0].message.content or "{}"
            payload = json.loads(content)
            return payload if isinstance(payload, dict) else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Card generation failed, keeping deterministic card: %s", exc.__class__.__name__)
            return None

    def generate_rationale(self, role_text: str, student_text: str) -> str | None:
        if not self._client:
            return None

        prompt = (
            "Write one sentence (<=25 words) explaining candidate-role fit. "
            "Be concrete and avoid hype."
        )

        try:
            response = self._client.chat.completions.create(
                model=self.chat_model,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Role: {role_text}\nCandidate: {student_text}"},
                ],
            )
            content = response.choices[0].message.content
            return content.strip() if content else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Rationale generation failed, using template rationale: %s", exc.__class__.__name__)
            return None
