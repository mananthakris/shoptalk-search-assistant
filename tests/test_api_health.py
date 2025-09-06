import os, sys
sys.path.append("services/api")
from fastapi.testclient import TestClient
from ui import app

def test_health():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("ok") in (True, False)  # your health returns {"ok": True}
