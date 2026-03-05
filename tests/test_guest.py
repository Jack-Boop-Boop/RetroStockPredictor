"""Tests for guest login, upgrade, and related features."""

import pytest


class TestGuestLogin:
    def test_guest_creates_account(self, client):
        resp = client.post("/api/auth/guest")
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["is_guest"] is True

    def test_guest_gets_portfolio(self, client):
        resp = client.post("/api/auth/guest")
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/portfolio", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert float(data["cash"]) == 100000.0

    def test_guest_gets_watchlist(self, client):
        resp = client.post("/api/auth/guest")
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/watchlist", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "AAPL" in data["symbols"]

    def test_guest_gets_agents(self, client):
        resp = client.post("/api/auth/guest")
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/agents", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["agents"]) == 7  # CEO, Risk, Quant, Tech, Fund, Sent, ML

    def test_guest_me_shows_guest_flag(self, client):
        resp = client.post("/api/auth/guest")
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/auth/me", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_guest"] is True
        assert "@local" in data["email"]

    def test_multiple_guests_get_unique_ids(self, client):
        resp1 = client.post("/api/auth/guest")
        resp2 = client.post("/api/auth/guest")
        token1 = resp1.json()["access_token"]
        token2 = resp2.json()["access_token"]
        assert token1 != token2


class TestGuestUpgrade:
    def test_upgrade_guest_to_full(self, client):
        # Create guest
        resp = client.post("/api/auth/guest")
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upgrade
        resp = client.post("/api/auth/upgrade", json={
            "email": "upgraded@example.com",
            "password": "newpass123",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_guest"] is False

        # Verify can login with new creds
        resp = client.post("/api/auth/login", json={
            "email": "upgraded@example.com",
            "password": "newpass123",
        })
        assert resp.status_code == 200

    def test_upgrade_fails_for_non_guest(self, client, demo_user, auth_headers):
        resp = client.post("/api/auth/upgrade", json={
            "email": "new@example.com",
            "password": "newpass123",
        }, headers=auth_headers)
        assert resp.status_code == 400

    def test_upgrade_fails_duplicate_email(self, client, demo_user):
        # Create guest
        resp = client.post("/api/auth/guest")
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try to upgrade with existing email
        resp = client.post("/api/auth/upgrade", json={
            "email": "test@example.com",  # demo_user's email
            "password": "newpass123",
        }, headers=headers)
        assert resp.status_code == 409
