"""6-step E2E pipeline test using mongomock + mock Docker."""

import time

from fastapi.testclient import TestClient


def test_e2e_6step_pipeline(gateway_client: TestClient, worker_client: TestClient):
    """完整 E2E 链路: workspace -> agent -> register -> chat -> task -> status."""

    # Step 1: POST /api/v1/workspaces -> 201
    resp = gateway_client.post("/api/v1/workspaces", json={"name": "test-workspace"})
    assert resp.status_code == 201
    ws = resp.json()
    assert ws["workspace_id"]
    assert ws["volume_name"]
    workspace_id = ws["workspace_id"]

    # Step 2: POST /api/v1/agents -> 201, status == pending
    resp = gateway_client.post(
        "/api/v1/agents",
        json={"name": "test-agent", "role": "coordinator", "workspace_id": workspace_id},
    )
    assert resp.status_code == 201
    agent = resp.json()
    assert agent["node_id"]
    assert agent["status"] == "pending"
    node_id = agent["node_id"]

    # Step 3: POST register -> status becomes running
    resp = gateway_client.post(
        f"/api/v1/agents/{node_id}/register",
        json={
            "container_id": "test-container",
            "container_ip": "127.0.0.1",
            "container_hostname": "worker-test",
            "container_port": 3000,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"

    # Step 4: POST /api/v1/gateway/chat/completions -> 200 (mock Hermes)
    resp = gateway_client.post(
        "/api/v1/gateway/chat/completions",
        json={
            "agent_node_id": node_id,
            "workspace_id": workspace_id,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert resp.status_code == 200
    chat = resp.json()
    assert chat["request_id"]
    assert chat["usage"]["total_tokens"] > 0

    # Step 5: GET /api/v1/agents/{id} -> running, hostname recorded
    resp = gateway_client.get(f"/api/v1/agents/{node_id}")
    assert resp.status_code == 200
    agent_data = resp.json()
    assert agent_data["status"] == "running"
    assert agent_data["container_hostname"] == "worker-test"

    # Step 6: Worker task -> accepted, then completed
    resp = worker_client.post(
        "/task",
        json={
            "task_id": "task-001",
            "task_type": "write",
            "instructions": "test output content",
            "output_path": "output.txt",
            "input_files": [],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
    assert resp.json()["task_id"] == "task-001"

    time.sleep(0.3)

    resp = worker_client.get("/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
