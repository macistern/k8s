import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_root_returns_success_message(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "success"
    assert body["message"] == "API funcionando correctamente."


def test_health_returns_healthy(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "healthy"}


def test_ready_returns_ready(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ready"}


def test_api_root_matches_root(client):
    root_response = client.get("/")
    for path in ("/api", "/api/"):
        response = client.get(path)
        assert response.status_code == root_response.status_code
        assert response.get_json() == root_response.get_json()


def test_api_health_matches_health(client):
    assert client.get("/api/health").get_json() == client.get("/health").get_json()


def test_api_ready_matches_ready(client):
    assert client.get("/api/ready").get_json() == client.get("/ready").get_json()
