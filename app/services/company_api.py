import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.config import Settings


class CorporateApiError(Exception):
    """The corporate API returned an unusable result."""


class IntegrationUnavailable(CorporateApiError):
    """A required corporate integration is not configured."""


class CorporateApiClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.corporate_api_base_url and self.settings.corporate_api_key)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        if not self.configured:
            raise IntegrationUnavailable("Не задан ключ корпоративной системы.")
        if not path:
            raise IntegrationUnavailable("Маршрут корпоративной системы ещё не настроен.")

        url = f"{self.settings.corporate_api_base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = {
            "X-API-KEY": self.settings.corporate_api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.corporate_api_timeout_seconds) as client:
                response = await client.request(method, url, headers=headers, params=params, json=json_body)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as error:
            raise CorporateApiError(f"Корпоративная система вернула HTTP {error.response.status_code}.") from error
        except (httpx.HTTPError, ValueError) as error:
            raise CorporateApiError("Не удалось получить корректный ответ корпоративной системы.") from error

    async def find_outages_by_address(self, address: str) -> dict[str, Any]:
        """Resolve address to network assets, then query the documented outage route."""
        if not self.settings.corporate_api_subscriber_lookup_path:
            raise IntegrationUnavailable(
                "Для адресной проверки отключений нужен маршрут поиска абонента. "
                "Он отсутствует в опубликованной документации API."
            )

        subscriber = await self._request(
            "GET", self.settings.corporate_api_subscriber_lookup_path, params={"address": address}
        )
        subscriber_data = subscriber.get("data", subscriber) if isinstance(subscriber, dict) else subscriber
        if not isinstance(subscriber_data, dict):
            raise CorporateApiError("Сервис абонентов вернул данные в неизвестном формате.")

        today = datetime.now(UTC).date()
        filters = {
            "date_from": (today - timedelta(days=1)).isoformat(),
            "date_to": (today + timedelta(days=1)).isoformat(),
        }
        for field in ("substation_name", "line_name"):
            if subscriber_data.get(field):
                filters[field] = str(subscriber_data[field])

        payload = await self._request("GET", self.settings.corporate_api_disconnections_path, params=filters)
        outages = self._as_items(payload)
        active_outages = [outage for outage in outages if self._is_active(outage)]
        return {"subscriber": subscriber_data, "outages": active_outages}

    async def check_capacity(self, address: str, requested_power_kw: float) -> Any:
        if not self.settings.corporate_api_capacity_path:
            raise IntegrationUnavailable(
                "Маршрут проверки свободной мощности не опубликован и не настроен."
            )
        return await self._request(
            "GET",
            self.settings.corporate_api_capacity_path,
            params={"address": address, "requested_power_kw": requested_power_kw},
        )

    async def create_technical_condition(self, payload: dict[str, Any]) -> Any:
        return await self._request("POST", self.settings.corporate_api_technical_condition_path, json_body=payload)

    async def send_complaint(self, payload: dict[str, Any]) -> Any | None:
        if not self.settings.corporate_api_complaint_path:
            return None
        return await self._request("POST", self.settings.corporate_api_complaint_path, json_body=payload)

    @staticmethod
    def _as_items(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("data", "items", "results"):
                if isinstance(payload.get(key), list):
                    return [item for item in payload[key] if isinstance(item, dict)]
        return []

    @staticmethod
    def _is_active(outage: dict[str, Any]) -> bool:
        raw_end = outage.get("connection_time") or outage.get("end_at")
        if raw_end in (None, "", "null"):
            return True
        try:
            end_time = datetime.fromisoformat(str(raw_end).replace("Z", "+00:00"))
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=UTC)
            return end_time >= datetime.now(UTC)
        except ValueError:
            return True

    @staticmethod
    def display_outage(outage: dict[str, Any]) -> str:
        fields = ("reason", "disconnection_time", "connection_time", "end_at", "substation_name", "line_name")
        summary = {key: outage[key] for key in fields if outage.get(key) not in (None, "")}
        return json.dumps(summary, ensure_ascii=False)
