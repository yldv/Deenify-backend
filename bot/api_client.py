from dataclasses import dataclass
import json
import logging
from typing import Any

import aiohttp

from core.constants import DEFAULT_LANGUAGE
from core.languages import normalize_language_code

logger = logging.getLogger(__name__)


class ApiClientError(Exception):
    def __init__(
        self,
        message: str,
        status: int | None = None,
        payload: Any = None,
        method: str | None = None,
        url: str | None = None,
        response_text: str = "",
    ):
        super().__init__(message)
        self.status = status
        self.payload = payload
        self.method = method
        self.url = url
        self.response_text = response_text


class PaymentRequiredError(ApiClientError):
    pass


class BlockedUserError(ApiClientError):
    pass


class NotFoundError(ApiClientError):
    pass


@dataclass
class BackendApiClient:
    base_url: str

    def __post_init__(self):
        self.base_url = self.base_url.rstrip("/")

    async def _request(self, method: str, path: str, **kwargs):
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        headers.setdefault("Accept", "application/json")
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.request(method, url, **kwargs) as response:
                    response_text = await response.text()
                    payload = self._parse_payload(response_text)
                    if response.status in (200, 201):
                        return payload
                    self._log_failure(method, url, response.status, response_text)
                    self._raise_for_status(
                        response.status,
                        payload,
                        method=method,
                        url=url,
                        response_text=response_text,
                    )
        except aiohttp.ClientError as exc:
            logger.exception(
                "Backend request connection error: method=%s url=%s error=%s",
                method,
                url,
                exc,
            )
            raise ApiClientError(
                "Backend connection error.",
                method=method,
                url=url,
            ) from exc

    def _parse_payload(self, response_text):
        if not response_text:
            return {}
        try:
            return json.loads(response_text)
        except ValueError:
            return {"detail": response_text}

    def _log_failure(self, method, url, status, response_text):
        logger.error(
            "Backend request failed: method=%s url=%s status=%s response=%s",
            method,
            url,
            status,
            response_text,
        )

    def _raise_for_status(self, status: int, payload, *, method, url, response_text):
        message = payload.get("detail") if isinstance(payload, dict) else None
        message = message or "Backend request failed."
        kwargs = {
            "status": status,
            "payload": payload,
            "method": method,
            "url": url,
            "response_text": response_text,
        }
        if status == 402:
            raise PaymentRequiredError(message, **kwargs)
        if status == 403:
            raise BlockedUserError(message, **kwargs)
        if status == 404:
            raise NotFoundError(message, **kwargs)
        raise ApiClientError(message, **kwargs)

    @staticmethod
    def _api_language(language: str) -> str:
        return normalize_language_code(language) or DEFAULT_LANGUAGE

    async def get_user(self, *, telegram_id):
        return await self._request("GET", f"/bot/users/{telegram_id}/")

    async def get_or_create_user(
        self,
        *,
        telegram_id,
        full_name="",
        username="",
        language="uz",
        phone_number="",
    ):
        return await self._request(
            "POST",
            "/bot/users/",
            json={
                "telegram_id": telegram_id,
                "full_name": full_name,
                "username": username or "",
                "language": language,
                "phone_number": phone_number,
            },
        )

    async def change_language(self, *, telegram_id, language):
        return await self._request(
            "PATCH",
            f"/bot/users/{telegram_id}/language/",
            json={"language": language},
        )

    async def get_quiz_next(self, *, telegram_id, language="uz"):
        return await self._request(
            "GET",
            "/quiz/next/",
            params={"telegram_id": telegram_id},
            headers={"Accept-Language": self._api_language(language)},
        )

    async def submit_quiz_answer(self, *, telegram_id, test_id, answer_id, language="uz"):
        return await self._request(
            "POST",
            "/quiz/answer/",
            json={
                "telegram_id": telegram_id,
                "test_id": test_id,
                "answer_id": answer_id,
            },
            headers={"Accept-Language": self._api_language(language)},
        )

    async def restart_quiz_round(self, *, telegram_id):
        return await self._request(
            "POST",
            "/quiz/restart/",
            json={"telegram_id": telegram_id},
        )

    async def reset_quiz_progress(self, *, telegram_id):
        return await self._request(
            "POST",
            "/quiz/reset/",
            json={"telegram_id": telegram_id},
        )

