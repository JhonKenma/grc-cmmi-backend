"""Servicios auxiliares del modulo de evaluaciones."""

from __future__ import annotations

from typing import Any

import requests


class CopilotQuestionSelectorClient:
    """Cliente HTTP para solicitar sugerencias de preguntas al microservicio IA."""

    def __init__(self, base_url: str, timeout_seconds: int = 45):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def suggest_questions(
        self,
        *,
        authorization_header: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Invoca el endpoint de seleccion de preguntas y retorna JSON validado."""
        headers = {"Content-Type": "application/json"}
        if authorization_header:
            headers["Authorization"] = authorization_header

        try:
            response = requests.post(
                f"{self.base_url}/copilot/evaluations/question-selection",
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
        except requests.Timeout as exc:
            raise RuntimeError("Timeout al conectar con el microservicio de IA.") from exc
        except requests.ConnectionError as exc:
            raise RuntimeError(
                "No se pudo conectar con el microservicio de IA."
            ) from exc

        if response.status_code >= 400:
            detail = None
            try:
                error_data = response.json()
            except requests.JSONDecodeError:
                error_data = None

            if isinstance(error_data, dict):
                detail = error_data.get("detail") or error_data.get("error")

            if not isinstance(detail, str) or not detail.strip():
                fallback_text = (response.text or "").strip()
                if fallback_text:
                    detail = fallback_text[:500]

            if isinstance(detail, str) and detail.strip():
                raise ValueError(detail)

            raise ValueError("No fue posible obtener sugerencias desde la IA.")

        try:
            data = response.json()
        except requests.JSONDecodeError as exc:
            raise RuntimeError(
                "El microservicio de IA retorno una respuesta no JSON."
            ) from exc

        if not isinstance(data, dict):
            raise RuntimeError("Respuesta inesperada del microservicio de IA.")

        return data
