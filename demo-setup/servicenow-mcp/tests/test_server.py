"""The MCP server exposes the five incident tools and a health check."""

import asyncio
import unittest

from starlette.testclient import TestClient

from servicenow_mcp.client import ServiceNowClient
from servicenow_mcp.server import build_server


class ServerTest(unittest.TestCase):
    def test_tools_and_healthz(self):
        server = build_server(
            ServiceNowClient("https://example.service-now.com", "user", "secret")
        )
        names = sorted(tool.name for tool in asyncio.run(server.list_tools()))
        self.assertEqual(
            names,
            [
                "add_work_note",
                "create_incident",
                "get_incident",
                "search_incidents",
                "update_incident",
            ],
        )

        app = server.streamable_http_app()
        with TestClient(app) as client:
            response = client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "ok")


if __name__ == "__main__":
    unittest.main()
