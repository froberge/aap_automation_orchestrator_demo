#!/usr/bin/env python3
"""Create or update the ao-ticket-demo-vm host in Ansible Product Demos Inventory."""

from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if not value:
        sys.exit(f"Set {name}")
    return value


AWS_PROFILE = os.environ.get("AWS_PROFILE", "redhat-demo")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
INSTANCE_NAME = os.environ.get("INSTANCE_NAME", "ao-ticket-demo-vm")
INVENTORY_NAME = os.environ.get("INVENTORY_NAME", "Ansible Product Demos Inventory")
HOST_NAME = os.environ.get("HOST_NAME", "ao-ticket-demo-vm")
ANSIBLE_USER = os.environ.get("ANSIBLE_USER", "ec2-user")
GROUPS = ("aws_rhel", "aws_linux", "os_linux")
CONTROLLER_HOST = env("CONTROLLER_HOST").rstrip("/")
CONTROLLER_TOKEN = env("CONTROLLER_TOKEN")

CONTEXT = ssl._create_unverified_context() if os.environ.get("CONTROLLER_INSECURE") == "1" else None


def api(method: str, path: str, body: dict | None = None, ok: set[int] | None = None) -> tuple[int, dict | None]:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        CONTROLLER_HOST + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {CONTROLLER_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, context=CONTEXT) as response:
            raw = response.read()
            payload = json.loads(raw) if raw else None
            return response.status, payload
    except urllib.error.HTTPError as exc:
        if ok and exc.code in ok:
            return exc.code, None
        detail = exc.read().decode(errors="replace")
        sys.exit(f"{method} {path} failed: HTTP {exc.code} {detail}")


def first_id(path: str, label: str) -> int:
    _status, payload = api("GET", path)
    results = (payload or {}).get("results") or []
    if not results:
        sys.exit(f"{label} was not found")
    return int(results[0]["id"])


def instance() -> tuple[str, str]:
    query = [
        "aws", "ec2", "describe-instances",
        "--profile", AWS_PROFILE,
        "--region", AWS_REGION,
        "--filters",
        f"Name=tag:Name,Values={INSTANCE_NAME}",
        "Name=instance-state-name,Values=running",
        "--query", "Reservations[0].Instances[0].[InstanceId,PublicIpAddress]",
        "--output", "text",
    ]
    result = subprocess.run(query, check=True, capture_output=True, text=True)
    instance_id, public_ip = result.stdout.split()
    if instance_id in {"", "None"} or public_ip in {"", "None"}:
        sys.exit(f"No running instance tagged {INSTANCE_NAME} in {AWS_REGION}.")
    return instance_id, public_ip


def main() -> None:
    instance_id, public_ip = instance()
    inventory_id = first_id(
        "/api/controller/v2/inventories/?name=" + urllib.parse.quote(INVENTORY_NAME),
        f"inventory {INVENTORY_NAME}",
    )
    host_body = {
        "name": HOST_NAME,
        "description": "RHEL 9 ticket enrichment demo VM in us-east-1",
        "inventory": inventory_id,
        "enabled": True,
        "instance_id": instance_id,
        "variables": f"ansible_host: {public_ip}\nansible_user: {ANSIBLE_USER}\n",
    }
    _status, existing = api(
        "GET",
        f"/api/controller/v2/hosts/?name={urllib.parse.quote(HOST_NAME)}&inventory={inventory_id}",
    )
    found = (existing or {}).get("results") or []
    if found:
        host_id = int(found[0]["id"])
        api("PATCH", f"/api/controller/v2/hosts/{host_id}/", host_body)
        print(f"Updated host {HOST_NAME} ({host_id}) -> {public_ip}")
    else:
        _status, created = api("POST", "/api/controller/v2/hosts/", host_body)
        host_id = int((created or {})["id"])
        print(f"Created host {HOST_NAME} ({host_id}) -> {public_ip}")

    for group in GROUPS:
        group_id = first_id(
            f"/api/controller/v2/groups/?name={urllib.parse.quote(group)}&inventory={inventory_id}",
            f"group {group}",
        )
        status, _payload = api(
            "POST",
            f"/api/controller/v2/groups/{group_id}/hosts/",
            {"id": host_id},
            ok={204, 400},
        )
        print(f"Group {group} ({status})")


if __name__ == "__main__":
    main()
