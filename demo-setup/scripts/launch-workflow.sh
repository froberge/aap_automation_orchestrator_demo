#!/usr/bin/env bash
# Request a service-account token and start the Ticket Enrichment webhook.
set -euo pipefail

INCIDENT_NUMBER="${1:?Usage: ./scripts/launch-workflow.sh INC0010001}"
AO_HOST="${AO_HOST:-https://automation-orchestrator-automation-orchestrator.apps.cluster-mshx8.dyn.redhatworkshops.io}"
AO_HOST="${AO_HOST%/}"

: "${AO_CLIENT_ID:?Set AO_CLIENT_ID to the service account client id}"
: "${AO_CLIENT_SECRET:?Set AO_CLIENT_SECRET to the service account client secret}"

TOKEN="$(
  curl -sS -X POST \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode 'grant_type=client_credentials' \
    --data-urlencode "client_id=${AO_CLIENT_ID}" \
    --data-urlencode "client_secret=${AO_CLIENT_SECRET}" \
    "${AO_HOST}/api/v1/auth/token" \
    | python3 -c 'import json,sys
data=json.load(sys.stdin)
token=data.get("access_token")
if not token:
    raise SystemExit(data)
print(token)'
)"

BODY="$(INCIDENT_NUMBER="$INCIDENT_NUMBER" python3 -c 'import json,os; print(json.dumps({"incident_number": os.environ["INCIDENT_NUMBER"]}))')"

curl -sS -X POST \
  "${AO_HOST}/api/v1/webhooks/servicenow-incident" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  --data-binary "$BODY"
echo
