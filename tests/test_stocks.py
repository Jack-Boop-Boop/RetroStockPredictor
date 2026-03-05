"""Tests for stock search, popular stocks, and portfolio import."""

import pytest


class TestStockSearch:
    def test_search_by_symbol(self, client):
        resp = client.get("/api/stocks/search?q=AAPL")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        symbols = [r["symbol"] for r in data["results"]]
        assert "AAPL" in symbols

    def test_search_by_name(self, client):
        resp = client.get("/api/stocks/search?q=apple")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any("Apple" in r["name"] for r in data["results"])

    def test_search_unknown_symbol_returns_lookup(self, client):
        resp = client.get("/api/stocks/search?q=ZZZZ")
        assert resp.status_code == 200
        data = resp.json()
        # Should return a bare lookup entry for direct symbol
        assert data["total"] >= 1
        assert data["results"][0]["symbol"] == "ZZZZ"

    def test_search_limit(self, client):
        resp = client.get("/api/stocks/search?q=a&limit=3")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) <= 3

    def test_search_empty_query_fails(self, client):
        resp = client.get("/api/stocks/search?q=")
        assert resp.status_code == 422  # validation error


class TestPopularStocks:
    def test_popular_stocks(self, client):
        resp = client.get("/api/stocks/popular")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        symbols = [r["symbol"] for r in data["results"]]
        assert "AAPL" in symbols

    def test_popular_with_limit(self, client):
        resp = client.get("/api/stocks/popular?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 5

    def test_popular_by_sector(self, client):
        resp = client.get("/api/stocks/popular?sector=Technology")
        assert resp.status_code == 200
        data = resp.json()
        for result in data["results"]:
            assert result["sector"] == "Technology"


class TestSectors:
    def test_list_sectors(self, client):
        resp = client.get("/api/stocks/sectors")
        assert resp.status_code == 200
        data = resp.json()
        assert "Technology" in data
        assert "Healthcare" in data


class TestPortfolioImport:
    def test_import_positions(self, client, auth_headers):
        resp = client.post("/api/portfolio/import", json={
            "positions": [
                {"symbol": "AAPL", "shares": 10, "avg_cost": 150.00},
                {"symbol": "MSFT", "shares": 5, "avg_cost": 380.00},
            ]
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["imported"] == 2

        # Check portfolio reflects import
        resp = client.get("/api/portfolio", headers=auth_headers)
        portfolio = resp.json()
        symbols = [p["symbol"] for p in portfolio["positions"]]
        assert "AAPL" in symbols
        assert "MSFT" in symbols

    def test_import_merges_existing(self, client, auth_headers):
        # Import once
        client.post("/api/portfolio/import", json={
            "positions": [{"symbol": "AAPL", "shares": 10, "avg_cost": 150.00}]
        }, headers=auth_headers)

        # Import again for same symbol
        resp = client.post("/api/portfolio/import", json={
            "positions": [{"symbol": "AAPL", "shares": 5, "avg_cost": 200.00}]
        }, headers=auth_headers)
        assert resp.status_code == 201

    def test_import_works_without_auth_for_public_user(self, client):
        """In public/demo mode, importing positions without auth should succeed."""
        resp = client.post("/api/portfolio/import", json={
            "positions": [{"symbol": "AAPL", "shares": 10, "avg_cost": 150.00}]
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["imported"] == 1

    def test_import_empty_fails(self, client, auth_headers):
        resp = client.post("/api/portfolio/import", json={
            "positions": []
        }, headers=auth_headers)
        assert resp.status_code == 422
