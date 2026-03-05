"""Tests for auth endpoints: register, login, me."""

import pytest


class TestRegister:
    def test_register_success(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "new@example.com",
            "password": "securepass123",
            "display_name": "New User",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_email(self, client, demo_user):
        resp = client.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "anotherpass123",
        })
        assert resp.status_code == 409

    def test_register_weak_password(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "weak@example.com",
            "password": "short",
        })
        assert resp.status_code == 422  # Pydantic validation

    def test_register_invalid_email(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "notanemail",
            "password": "securepass123",
        })
        assert resp.status_code == 422


class TestLogin:
    def test_login_success(self, client, demo_user):
        resp = client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password(self, client, demo_user):
        resp = client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpass",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/auth/login", json={
            "email": "ghost@example.com",
            "password": "whatever123",
        })
        assert resp.status_code == 401


class TestMe:
    def test_me_authenticated(self, client, auth_headers):
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert data["display_name"] == "Test User"

    def test_me_no_token(self, client):
        """In public/demo mode, /me returns the shared public user when no token is provided."""
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_guest"] is True
        assert "@local" in data["email"]

    def test_me_invalid_token(self, client):
        resp = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
        assert resp.status_code == 401
