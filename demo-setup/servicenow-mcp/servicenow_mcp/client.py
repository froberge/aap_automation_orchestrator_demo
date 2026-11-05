"""ServiceNow Table API client for the incident table."""

from __future__ import annotations

import os
import re
from typing import Any

import httpx

INCIDENT_FIELDS = (
    "number",
    "short_description",
    "description",
    "priority",
    "category",
    "subcategory",
    "state",
    "cmdb_ci",
    "assignment_group",
    "sys_id",
)

STATE_LABELS = {
    "1": "New",
    "2": "In Progress",
    "3": "On Hold",
    "6": "Resolved",
    "7": "Closed",
    "8": "Canceled",
}

_NUMBER = re.compile(r"^[A-Za-z0-9]+$")
_MAX_LIMIT = 50


class ServiceNowError(Exception):
    """A Table API call failed or the incident could not be found."""


class ServiceNowClient:
    def __init__(
        self,
        instance_url: str,
        username: str,
        password: str,
        *,
        verify: bool = True,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base = instance_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self._base,
            auth=(username, password),
            timeout=timeout,
            verify=verify,
            transport=transport,
            headers={"Accept": "application/json"},
        )

    @classmethod
    def from_env(cls) -> ServiceNowClient:
        missing = [
            name
            for name in (
                "SERVICENOW_INSTANCE_URL",
                "SERVICENOW_USERNAME",
                "SERVICENOW_PASSWORD",
            )
            if not os.environ.get(name)
        ]
        if missing:
            raise ServiceNowError(
                "Missing ServiceNow settings: " + ", ".join(missing)
            )
        verify = os.environ.get("SERVICENOW_VERIFY_SSL", "true").lower() not in {
            "0",
            "false",
            "no",
        }
        return cls(
            os.environ["SERVICENOW_INSTANCE_URL"],
            os.environ["SERVICENOW_USERNAME"],
            os.environ["SERVICENOW_PASSWORD"],
            verify=verify,
        )

    def close(self) -> None:
        self._http.close()

    def get_incident(self, number: str) -> dict[str, Any]:
        return self._shape(self._find(number))

    def search_incidents(self, query: str, limit: int = 10) -> dict[str, Any]:
        encoded = query.strip()
        if not encoded:
            raise ServiceNowError("query is required")
        bounded = min(max(int(limit), 1), _MAX_LIMIT)
        payload = self._request(
            "GET",
            "/api/now/table/incident",
            params={
                "sysparm_query": encoded,
                "sysparm_limit": bounded,
                "sysparm_fields": ",".join(INCIDENT_FIELDS),
                "sysparm_display_value": "true",
                "sysparm_exclude_reference_link": "true",
            },
        )
        records = payload.get("result") or []
        if isinstance(records, dict):
            records = [records]
        return {"count": len(records), "incidents": [self._shape(row) for row in records]}

    def create_incident(
        self,
        short_description: str,
        *,
        description: str | None = None,
        urgency: str | None = None,
        impact: str | None = None,
        category: str | None = None,
        caller_id: str | None = None,
    ) -> dict[str, Any]:
        summary = short_description.strip()
        if not summary:
            raise ServiceNowError("short_description is required")
        body = _present(
            {
                "short_description": summary,
                "description": description,
                "urgency": urgency,
                "impact": impact,
                "category": category,
                "caller_id": caller_id,
            }
        )
        payload = self._request("POST", "/api/now/table/incident", json=body)
        return self._shape(payload["result"])

    def update_incident(self, number: str, fields: dict[str, Any]) -> dict[str, Any]:
        body = _present(fields)
        if not body:
            raise ServiceNowError("no fields to update")
        record = self._find(number, display=False)
        payload = self._request(
            "PATCH",
            f"/api/now/table/incident/{record['sys_id']}",
            json=body,
        )
        return self._shape(payload["result"])

    def add_work_note(self, number: str, work_note: str) -> dict[str, Any]:
        note = work_note.strip()
        if not note:
            raise ServiceNowError("work_note is required")
        record = self._find(number, display=False)
        self._request(
            "PATCH",
            f"/api/now/table/incident/{record['sys_id']}",
            json={"work_notes": note},
        )
        return {"number": _number(number), "work_note_added": True}

    def _find(self, number: str, *, display: bool = True) -> dict[str, Any]:
        incident_number = _number(number)
        payload = self._request(
            "GET",
            "/api/now/table/incident",
            params={
                "sysparm_query": f"number={incident_number}",
                "sysparm_limit": 1,
                "sysparm_fields": ",".join(INCIDENT_FIELDS),
                "sysparm_display_value": "true" if display else "false",
                "sysparm_exclude_reference_link": "true",
            },
        )
        records = payload.get("result") or []
        if not records:
            raise ServiceNowError(f"incident {incident_number} was not found")
        return records[0]

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ServiceNowError(f"ServiceNow request failed: {exc}") from exc
        if response.status_code == 401:
            raise ServiceNowError("ServiceNow rejected the username or password")
        if response.status_code == 403:
            raise ServiceNowError("ServiceNow denied access to the incident table")
        if response.status_code >= 400:
            raise ServiceNowError(_error_message(response))
        if not response.content:
            return {"result": {}}
        return response.json()

    def _shape(self, record: dict[str, Any]) -> dict[str, Any]:
        shaped = {field: _display(record.get(field, "")) for field in INCIDENT_FIELDS}
        state = str(shaped["state"])
        shaped["state_label"] = STATE_LABELS.get(state, state)
        return shaped


def _number(number: str) -> str:
    incident_number = number.strip()
    if not _NUMBER.fullmatch(incident_number):
        raise ServiceNowError("incident number must contain only letters and numbers")
    return incident_number


def _display(value: Any) -> str:
    if isinstance(value, dict):
        shown = value.get("display_value")
        if shown:
            return str(shown)
        raw = value.get("value")
        return "" if raw is None else str(raw)
    if value is None:
        return ""
    return str(value)


def _present(fields: dict[str, Any]) -> dict[str, str]:
    body: dict[str, str] = {}
    for key, value in fields.items():
        if value is None:
            continue
        text = str(value).strip()
        if text:
            body[key] = text
    return body


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"ServiceNow returned HTTP {response.status_code}"
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        message = error.get("message") or error.get("detail") or ""
        if message:
            return f"ServiceNow returned HTTP {response.status_code}: {message}"
    return f"ServiceNow returned HTTP {response.status_code}"
