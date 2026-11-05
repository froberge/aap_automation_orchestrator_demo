#!/usr/bin/env bash
# Create a priority 5 inquiry for the inform-only path.
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
        "short_description": f"Request a copy of the backup report for {host_name}",
        "description": (
            f"Affected system: {host_name}. "
            "The caller wants a copy of last week's backup report sent by email. "
            "No disk cleanup, log rotation, service restart, process termination, "
            "package upgrade, firewall change, or network change is requested. "
            "No automated remediation applies. Leave the ticket for a person to answer."
        ),
        "urgency": "3",
        "impact": "3",
        "category": "inquiry",
    },
)
sys_id = created["result"]["sys_id"]
# Priority 4 or 5 skips remediation template matching and takes inform_only.
updated = call(
    "PATCH",
    f"/api/now/table/incident/{sys_id}?sysparm_display_value=true&sysparm_exclude_reference_link=true&sysparm_fields=number,priority,state,short_description",
    {"priority": "5", "urgency": "3", "impact": "3"},
)
print(json.dumps(updated["result"], indent=2))
PY
