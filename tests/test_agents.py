"""Tests for custom agent CRUD and hierarchy."""

import pytest


def _create_guest_with_agents(client):
    """Helper: create a guest user (gets default agents) and return headers."""
    resp = client.post("/api/auth/guest")
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestAgentList:
    def test_list_agents_default_hierarchy(self, client):
        headers = _create_guest_with_agents(client)
        resp = client.get("/api/agents", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["agents"]) == 7

        types = [a["agent_type"] for a in data["agents"]]
        assert "ceo" in types
        assert "risk" in types
        assert "quant" in types
        assert "technical" in types
        assert "fundamental" in types
        assert "sentiment" in types
        assert "ml" in types

    def test_list_agents_requires_auth(self, client):
        resp = client.get("/api/agents")
        assert resp.status_code == 401


class TestAgentCreate:
    def test_create_agent(self, client):
        headers = _create_guest_with_agents(client)

        resp = client.post("/api/agents", json={
            "name": "My Custom Agent",
            "agent_type": "custom",
            "prompt": "Do something special",
            "weight": 1.5,
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My Custom Agent"
        assert data["weight"] == 1.5

    def test_create_agent_with_parent(self, client):
        headers = _create_guest_with_agents(client)

        # Get existing agents to find a parent
        agents = client.get("/api/agents", headers=headers).json()["agents"]
        quant = next(a for a in agents if a["agent_type"] == "quant")

        resp = client.post("/api/agents", json={
            "name": "Extra Analyst",
            "agent_type": "technical",
            "parent_id": quant["id"],
        }, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["parent_id"] == quant["id"]


class TestAgentUpdate:
    def test_update_agent_name_and_weight(self, client):
        headers = _create_guest_with_agents(client)

        agents = client.get("/api/agents", headers=headers).json()["agents"]
        tech = next(a for a in agents if a["agent_type"] == "technical")

        resp = client.put(f"/api/agents/{tech['id']}", json={
            "name": "Super Technical",
            "weight": 2.0,
            "prompt": "Focus heavily on RSI signals",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Super Technical"
        assert data["weight"] == 2.0
        assert "RSI" in data["prompt"]

    def test_update_agent_disable(self, client):
        headers = _create_guest_with_agents(client)

        agents = client.get("/api/agents", headers=headers).json()["agents"]
        sent = next(a for a in agents if a["agent_type"] == "sentiment")

        resp = client.put(f"/api/agents/{sent['id']}", json={
            "enabled": False,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_update_nonexistent_agent(self, client):
        headers = _create_guest_with_agents(client)
        resp = client.put("/api/agents/nonexistent", json={
            "name": "Ghost",
        }, headers=headers)
        assert resp.status_code == 404


class TestAgentDelete:
    def test_delete_agent(self, client):
        headers = _create_guest_with_agents(client)

        agents = client.get("/api/agents", headers=headers).json()["agents"]
        ml = next(a for a in agents if a["agent_type"] == "ml")

        resp = client.delete(f"/api/agents/{ml['id']}", headers=headers)
        assert resp.status_code == 204

        # Verify deleted
        agents_after = client.get("/api/agents", headers=headers).json()["agents"]
        assert len(agents_after) == 6

    def test_delete_reparents_children(self, client):
        headers = _create_guest_with_agents(client)

        agents = client.get("/api/agents", headers=headers).json()["agents"]
        quant = next(a for a in agents if a["agent_type"] == "quant")
        ceo = next(a for a in agents if a["agent_type"] == "ceo")

        # Quant has children (tech, fund, sent, ml) — deleting quant should re-parent them to CEO
        resp = client.delete(f"/api/agents/{quant['id']}", headers=headers)
        assert resp.status_code == 204

        agents_after = client.get("/api/agents", headers=headers).json()["agents"]
        tech = next(a for a in agents_after if a["agent_type"] == "technical")
        assert tech["parent_id"] == ceo["id"]


class TestAgentReset:
    def test_reset_agents(self, client):
        headers = _create_guest_with_agents(client)

        # Delete some agents
        agents = client.get("/api/agents", headers=headers).json()["agents"]
        client.delete(f"/api/agents/{agents[0]['id']}", headers=headers)

        # Reset
        resp = client.post("/api/agents/reset", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["agents"]) == 7
