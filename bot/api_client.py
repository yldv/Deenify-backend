from dataclasses import dataclass
import json
import logging
from typing import Any

import aiohttp

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

    async def get_or_create_user(self, *, telegram_id, full_name, username, language):
        return await self._request(
            "POST",
            "/bot/users/",
            json={
                "telegram_id": telegram_id,
                "full_name": full_name,
                "username": username or "",
                "language": language,
            },
        )

    async def change_language(self, *, telegram_id, language):
        return await self._request(
            "PATCH",
            f"/bot/users/{telegram_id}/language/",
            json={"language": language},
        )

    async def get_statistics(self, *, telegram_id):
        return await self._request("GET", f"/bot/users/{telegram_id}/statistics/")

    async def get_categories(self, *, language="uz"):
        return await self._request(
            "GET",
            "/tests/categories/",
            headers={"Accept-Language": language},
        )

    async def start_test_session(self, *, telegram_id, test_type, language="uz"):
        return await self._request(
            "POST",
            "/tests/sessions/start/",
            json={"telegram_id": telegram_id, "test_type": test_type},
            headers={"Accept-Language": language},
        )

    async def submit_answer(self, *, session_id, telegram_id, test_id, answer_id, language="uz"):
        data = await self._request(
            "POST",
            f"/tests/sessions/{session_id}/answer/",
            json={
                "telegram_id": telegram_id,
                "test_id": test_id,
                "answer_id": answer_id,
            },
            headers={"Accept-Language": language},
        )
        if "session_stats" not in data and "session" in data:
            data["session_stats"] = data["session"]
        return data

    async def finish_session(self, *, session_id, telegram_id):
        return await self._request(
            "POST",
            f"/tests/sessions/{session_id}/finish/",
            json={"telegram_id": telegram_id},
        )

    async def get_subscription_plans(self, *, language="uz"):
        return await self._request(
            "GET",
            "/subscriptions/plans/",
            headers={"Accept-Language": language},
        )

    async def create_atmos_order(self, *, telegram_id, plan_id):
        return await self._request(
            "POST",
            "/payments/atmos/orders/",
            json={"telegram_id": telegram_id, "plan_id": plan_id},
        )

    async def get_orders(self, *, telegram_id, language="uz"):
        return await self._request(
            "GET",
            f"/bot/users/{telegram_id}/orders/",
            headers={"Accept-Language": language},
        )
