"""Streamable HTTP MCP server for ServiceNow incidents."""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from servicenow_mcp.client import ServiceNowClient, ServiceNowError

_STATE_HELP = (
    "ServiceNow incident state: 1 New, 2 In Progress, 3 On Hold, "
    "6 Resolved, 7 Closed, 8 Canceled."
)


def build_server(client: ServiceNowClient) -> FastMCP:
    """Register the five incident tools on a stateless streamable HTTP server."""
    mcp = FastMCP(
        "servicenow-mcp",
        instructions=(
            "Read and update ServiceNow incidents. "
            "Pass the incident number, such as INC0010001. " + _STATE_HELP
        ),
        host=os.environ.get("MCP_HOST", "0.0.0.0"),
        port=int(os.environ.get("MCP_PORT", "8080")),
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )

    @mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def healthz(_request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    @mcp.tool()
    def get_incident(number: str) -> dict:
        """Fetch one ServiceNow incident by its number, such as INC0010001.

        Returns number, short_description, description, priority, category,
        subcategory, state, state_label, cmdb_ci, assignment_group, and sys_id.
        """
        return _call(client.get_incident, number)

    @mcp.tool()
    def search_incidents(query: str, limit: int = 10) -> dict:
        """Search incidents with a ServiceNow encoded query.

        query is passed to sysparm_query. Example:
        short_descriptionLIKEdisk^sys_created_on>=javascript:gs.daysAgo(30)
        limit defaults to 10 and cannot exceed 50.
        """
        return _call(client.search_incidents, query, limit)

    @mcp.tool()
    def create_incident(
        short_description: str,
        description: str | None = None,
        urgency: str | None = None,
        impact: str | None = None,
        category: str | None = None,
        caller_id: str | None = None,
    ) -> dict:
        """Create a ServiceNow incident. short_description is required.

        urgency and impact use 1 (high) through 3 (low).
        """
        return _call(
            client.create_incident,
            short_description,
            description=description,
            urgency=urgency,
            impact=impact,
            category=category,
            caller_id=caller_id,
        )

    @mcp.tool()
    def update_incident(
        number: str,
        state: str | None = None,
        short_description: str | None = None,
        description: str | None = None,
        assignment_group: str | None = None,
        category: str | None = None,
        urgency: str | None = None,
        impact: str | None = None,
        close_code: str | None = None,
        close_notes: str | None = None,
        comment: str | None = None,
    ) -> dict:
        """Update fields on an incident identified by number.

        Only fields you pass are changed. comment is the customer-visible
        ServiceNow comments field. State values: 1 New, 2 In Progress,
        3 On Hold, 6 Resolved, 7 Closed, 8 Canceled.
        """
        fields = {
            "state": state,
            "short_description": short_description,
            "description": description,
            "assignment_group": assignment_group,
            "category": category,
            "urgency": urgency,
            "impact": impact,
            "close_code": close_code,
            "close_notes": close_notes,
            "comments": comment,
        }
        return _call(client.update_incident, number, fields)

    @mcp.tool()
    def add_work_note(number: str, work_note: str) -> dict:
        """Add an internal work note to an incident. Customers do not see work notes."""
        return _call(client.add_work_note, number, work_note)

    return mcp


def main() -> None:
    client = ServiceNowClient.from_env()
    try:
        build_server(client).run(transport="streamable-http")
    finally:
        client.close()


def _call(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except ServiceNowError as exc:
        return {"error": str(exc)}


if __name__ == "__main__":
    main()
