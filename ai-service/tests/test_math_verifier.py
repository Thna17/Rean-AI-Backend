import pytest
from fastapi.testclient import TestClient
from api.routes.math_verifier import router
from fastapi import FastAPI

app = FastAPI()
app.include_router(router)

client = TestClient(app)

def test_verify_math_expression():
    response = client.post("/verify", json={"expression": "2*x + 3*x"})
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is True
    assert data["simplified"] == "5*x"

def test_verify_math_equation():
    response = client.post("/verify", json={"expression": "5*x + 3 = 18"})
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is True
    assert data["solution"] == "[3]"

def test_verify_math_invalid():
    response = client.post("/verify", json={"expression": "2*x +"})
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is False
    assert "error" in data
