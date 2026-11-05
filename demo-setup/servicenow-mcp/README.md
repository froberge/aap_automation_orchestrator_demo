# ServiceNow MCP Server

The ticket-enrichment agents call a ServiceNow MCP server named `servicenow-mcp`. This directory exposes five tools on the incident table: `get_incident`, `search_incidents`, `create_incident`, `update_incident`, and `add_work_note`. The server listens on `/mcp` and answers OpenShift probes at `/healthz`.

Fill in a real ServiceNow instance before applying the manifests. Copy [openshift/secret.example.yaml](openshift/secret.example.yaml) to `openshift/secret.yaml` and set `SERVICENOW_INSTANCE_URL`, `SERVICENOW_USERNAME`, and `SERVICENOW_PASSWORD`. Do not commit `secret.yaml`.

Run the commands below from this directory. They build the image in the `servicenow-mcp` project and expose it with an edge route:

```bash
oc apply -f openshift/namespace.yaml
oc apply -f openshift/secret.yaml \
  -f openshift/imagestream.yaml \
  -f openshift/buildconfig.yaml
oc start-build servicenow-mcp --from-dir=. --follow -n servicenow-mcp
oc apply -f openshift/deployment.yaml \
  -f openshift/service.yaml \
  -f openshift/route.yaml
oc get route servicenow-mcp -n servicenow-mcp -o jsonpath='{.spec.host}{"\n"}'
```

On this cluster the route host looks like `servicenow-mcp-servicenow-mcp.apps.cluster-mshx8.dyn.redhatworkshops.io`. Automation Orchestrator must be allowed to call that host. `oc set env` replaces the whole list, so keep the AAP MCP host in the same value:

```bash
oc set env \
  deployment/automation-orchestrator-backend \
  deployment/automation-orchestrator-worker \
  deployment/automation-orchestrator-background-worker \
  -n automation-orchestrator \
  'APP_INTEGRATION_URL_ALLOWED_HOSTS=["<AAP_MCP_HOST>","<SERVICENOW_MCP_HOST>"]'
```


Re-import [ticket-enrichment/ao/ticket-enrichment.json](../../ticket-enrichment/ao/ticket-enrichment.json) after the integration exists. The triage agent calls `servicenow-mcp::get_incident`. The enrich-and-assign agent calls `search_incidents`, `add_work_note`, and `update_incident` (`comment` for the customer message, `state` `2` for In Progress).
