"""Fail-safe Railway lifecycle controller for NG-Dashboard.

Runs from GitHub Actions on a schedule. It never stops Postgres. The dashboard
must first report zero valid sessions, zero authenticated requests and zero
protected jobs before the 20:00 IST stop is requested.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

API = "https://backboard.railway.com/graphql/v2"
TZ = ZoneInfo("Asia/Kolkata")


def request_json(url: str, *, method: str = "GET", headers=None, body=None, timeout=20):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read()
        return json.loads(raw) if raw else {}


def graphql(token: str, query: str, variables: dict):
    result = request_json(
        API,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        body={"query": query, "variables": variables},
        timeout=30,
    )
    if result.get("errors"):
        raise RuntimeError("Railway GraphQL error: " + json.dumps(result["errors"])[:1200])
    return result.get("data") or {}


def health(base_url: str) -> bool:
    try:
        request_json(base_url.rstrip("/") + "/healthz", timeout=12)
        return True
    except Exception:
        return False


def latest_deployment(token: str, project: str, environment: str, service: str) -> dict:
    query = """
    query LatestDeployment($input: DeploymentListInput!, $first: Int) {
      deployments(input: $input, first: $first) {
        edges { node { id status } }
      }
    }
    """
    data = graphql(token, query, {"input": {
        "projectId": project, "environmentId": environment, "serviceId": service
    }, "first": 1})
    edges = (data.get("deployments") or {}).get("edges") or []
    if not edges:
        raise RuntimeError("Railway returned no deployment for NG-Dashboard")
    return edges[0]["node"]


def start_if_needed(base_url: str, token: str, project: str, environment: str, service: str):
    # Give native serverless wake-up/cold-start time before deciding a manual
    # redeploy is required. This avoids unnecessary morning deployments.
    for attempt in range(6):
        if health(base_url):
            print("09:00 IST start check: dashboard healthy; no redeploy needed.")
            return
        if attempt < 5:
            time.sleep(10)
    deployment = latest_deployment(token, project, environment, service)
    mutation = "mutation Redeploy($id: String!) { deploymentRedeploy(id: $id) { id status } }"
    result = graphql(token, mutation, {"id": deployment["id"]})
    started = result.get("deploymentRedeploy")
    if not started:
        raise RuntimeError("Railway did not confirm the dashboard redeploy request")
    print("Start requested:", json.dumps(started))
    deadline = time.time() + 240
    while time.time() < deadline:
        if health(base_url):
            print("Dashboard /healthz is healthy after start.")
            return
        time.sleep(10)
    raise RuntimeError("Dashboard did not become healthy within 4 minutes after redeploy")


def stop_if_safe(base_url: str, lifecycle_token: str, railway_token: str,
                 project: str, environment: str, service: str):
    state_url = base_url.rstrip("/") + "/internal/lifecycle-state"
    try:
        state = request_json(state_url, headers={"X-Lifecycle-Token": lifecycle_token}, timeout=20)
    except Exception as exc:
        print(f"Fail-safe: lifecycle state unavailable; leaving dashboard running ({type(exc).__name__}).")
        return
    jobs = state.get("protected_jobs") or {}
    reasons = []
    if int(state.get("active_sessions") or 0):
        reasons.append(f"{state['active_sessions']} valid session(s)")
    if int(state.get("active_authenticated_requests") or 0):
        reasons.append(f"{state['active_authenticated_requests']} authenticated request(s)")
    if sum(int(v or 0) for v in jobs.values()):
        reasons.append("protected jobs " + json.dumps(jobs))
    if reasons:
        print("20:00+ IST shutdown deferred:", "; ".join(reasons))
        return
    deployment = latest_deployment(railway_token, project, environment, service)
    mutation = "mutation StopDeployment($id: String!) { deploymentStop(id: $id) }"
    result = graphql(railway_token, mutation, {"id": deployment["id"]})
    if result.get("deploymentStop") is not True:
        raise RuntimeError("Railway did not confirm the dashboard stop request")
    print("Safe 20:00+ IST shutdown requested:", json.dumps(result.get("deploymentStop")))


def main():
    required = ("NG_DASHBOARD_URL", "LIFECYCLE_CONTROL_TOKEN", "RAILWAY_API_TOKEN",
                "RAILWAY_PROJECT_ID", "RAILWAY_ENVIRONMENT_ID", "RAILWAY_SERVICE_ID")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise RuntimeError("Missing required GitHub Actions secrets/variables: " + ", ".join(missing))
    now = datetime.now(TZ)
    base = os.environ["NG_DASHBOARD_URL"]
    railway = os.environ["RAILWAY_API_TOKEN"]
    project = os.environ["RAILWAY_PROJECT_ID"]
    environment = os.environ["RAILWAY_ENVIRONMENT_ID"]
    service = os.environ["RAILWAY_SERVICE_ID"]
    if now.hour == 9 and now.minute < 15:
        start_if_needed(base, railway, project, environment, service)
    elif now.hour >= 20 and now.hour <= 23:
        stop_if_safe(base, os.environ["LIFECYCLE_CONTROL_TOKEN"], railway,
                     project, environment, service)
    else:
        print("Outside lifecycle action window; no production action taken.")


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        print(f"Lifecycle controller failed safely: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
