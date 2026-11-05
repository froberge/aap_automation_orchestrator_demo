"""Table API calls made by the five incident tools."""

import json
import unittest

import httpx

from servicenow_mcp.client import ServiceNowClient, ServiceNowError


def _client(handler) -> ServiceNowClient:
    return ServiceNowClient(
        "https://example.service-now.com",
        "user",
        "secret",
        transport=httpx.MockTransport(handler),
    )


def _record(**extra):
    base = {
        "number": "INC0010001",
        "short_description": "Disk full",
        "description": "Root filesystem",
        "priority": "2",
        "category": "software",
        "subcategory": "os",
        "state": "1",
        "cmdb_ci": "app-01",
        "assignment_group": "Ops",
        "sys_id": "abc123",
    }
    base.update(extra)
    return base


class IncidentClientTest(unittest.TestCase):
    def test_get_incident_queries_by_number(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["query"] = request.url.params["sysparm_query"]
            seen["fields"] = request.url.params["sysparm_fields"]
            return httpx.Response(200, json={"result": [_record()]})

        incident = _client(handler).get_incident(" INC0010001 ")

        self.assertEqual(seen["query"], "number=INC0010001")
        self.assertIn("cmdb_ci", seen["fields"])
        self.assertEqual(incident["state_label"], "New")
        self.assertEqual(incident["sys_id"], "abc123")

    def test_search_incidents_caps_the_limit(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["limit"] = request.url.params["sysparm_limit"]
            seen["query"] = request.url.params["sysparm_query"]
            return httpx.Response(200, json={"result": [_record()]})

        found = _client(handler).search_incidents("short_descriptionLIKEdisk", limit=500)

        self.assertEqual(seen["query"], "short_descriptionLIKEdisk")
        self.assertEqual(seen["limit"], "50")
        self.assertEqual(found["count"], 1)

    def test_create_incident_posts_only_provided_fields(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["body"] = request.read().decode()
            return httpx.Response(201, json={"result": _record(state="1")})

        created = _client(handler).create_incident(
            " Disk full ",
            description="  ",
            urgency="1",
        )

        body = json.loads(seen["body"])
        self.assertEqual(seen["method"], "POST")
        self.assertEqual(body, {"short_description": "Disk full", "urgency": "1"})
        self.assertEqual(created["number"], "INC0010001")

    def test_update_incident_patches_sys_id_and_maps_comment(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.method, request.url.path, request.read().decode()))
            if request.method == "GET":
                return httpx.Response(200, json={"result": [_record()]})
            return httpx.Response(200, json={"result": _record(state="2")})

        updated = _client(handler).update_incident(
            "INC0010001",
            {"state": "2", "comments": "We are looking at this", "description": None},
        )

        self.assertEqual(calls[0][0], "GET")
        self.assertEqual(calls[1][0], "PATCH")
        self.assertTrue(calls[1][1].endswith("/api/now/table/incident/abc123"))
        self.assertEqual(
            json.loads(calls[1][2]),
            {"state": "2", "comments": "We are looking at this"},
        )
        self.assertEqual(updated["state_label"], "In Progress")

    def test_add_work_note_uses_the_journal_field(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.method, request.read().decode()))
            if request.method == "GET":
                return httpx.Response(200, json={"result": [_record()]})
            return httpx.Response(200, json={"result": _record()})

        result = _client(handler).add_work_note("INC0010001", " Checked disk usage ")

        self.assertEqual(json.loads(calls[1][1]), {"work_notes": "Checked disk usage"})
        self.assertEqual(result, {"number": "INC0010001", "work_note_added": True})

    def test_missing_incident_is_an_error(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"result": []})

        with self.assertRaises(ServiceNowError) as caught:
            _client(handler).get_incident("INC0099999")
        self.assertIn("INC0099999", str(caught.exception))

    def test_rejected_number(self):
        def handler(_request: httpx.Request) -> httpx.Response:
            raise AssertionError("request should not be sent")

        with self.assertRaises(ServiceNowError) as caught:
            _client(handler).get_incident("INC001^state=1")
        self.assertIn("letters and numbers", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
