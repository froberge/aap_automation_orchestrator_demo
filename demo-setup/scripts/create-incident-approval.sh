#!/usr/bin/env bash
# Create a priority 1 high-CPU incident for the needs-approval path.
set -euo pipefail

HOST_NAME="${1:-ao-ticket-demo-vm}"
: "${SERVICENOW_INSTANCE_URL:?Set SERVICENOW_INSTANCE_URL}"
: "${SERVICENOW_USERNAME:?Set SERVICENOW_USERNAME}"
: "${SERVICENOW_PASSWORD:?Set SERVICENOW_PASSWORD}"

HOST_NAME="$HOST_NAME" python3 - << 'PY'
import base64
import json
import os
import urllib.error
import urllib.request

host_name = os.environ["HOST_NAME"]
base = os.environ["SERVICENOW_INSTANCE_URL"].rstrip("/")
if not base.startswith("http"):
    base = "https://" + base
token = base64.b64encode(
    f"{os.environ['SERVICENOW_USERNAME']}:{os.environ['SERVICENOW_PASSWORD']}".encode()
).decode()


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise SystemExit(f"{method} {path} failed: HTTP {exc.code} {detail}") from exc


created = call(
    "POST",
    "/api/now/table/incident?sysparm_fields=sys_id,number",
    {
        "short_description": f"High CPU on {host_name}: runaway process needs termination",
        "description": (
            f"Affected system: {host_name}. "
            "A runaway process is holding CPU above 90 percent. "
            "The required fix is process termination of that process. "
            "This may interrupt the workload on the host. "
            "Human review is recommended before the process is killed. "
            "This is not a disk cleanup, log rotation, or service restart."
        ),
        "urgency": "1",
        "impact": "1",
        "category": "software",
    },
)
sys_id = created["result"]["sys_id"]
# This instance does not calculate priority from impact and urgency.
# Priority 5 would take the inform-only path.
updated = call(
    "PATCH",
    f"/api/now/table/incident/{sys_id}?sysparm_display_value=true&sysparm_exclude_reference_link=true&sysparm_fields=number,priority,state,short_description",
    {"priority": "1", "urgency": "1", "impact": "1"},
)
print(json.dumps(updated["result"], indent=2))
PY
