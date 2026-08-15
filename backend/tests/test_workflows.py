import os
from datetime import date, timedelta

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_crm.db")
os.environ.setdefault("CRM_ADMIN_USERNAME", "admin")
os.environ.setdefault("CRM_ADMIN_PASSWORD", "test-password")
os.environ.setdefault("CRM_AUTH_SECRET", "test-secret")

from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app


def setup_module():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def client_with_token():
    client = TestClient(app)
    response = client.post("/api/auth/login", json={"username": "admin", "password": "test-password"})
    assert response.status_code == 200
    client.headers["Authorization"] = f"Bearer {response.json()['token']}"
    return client


def test_auth_health_and_customer_followup_workflow():
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/api/customers").status_code == 401
    client = client_with_token()
    customer = client.post("/api/customers", json={"name": "Test Customer", "phone": "9876543210"})
    assert customer.status_code == 201
    customer_id = customer.json()["id"]
    assert client.post(f"/api/customers/{customer_id}/calls", json={"call_status": "busy"}).status_code == 201
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    followup = client.post(f"/api/customers/{customer_id}/followups", json={"followup_date": tomorrow, "followup_time": "10:00", "reason": "Customer busy"})
    assert followup.status_code == 201
    assert client.post(f"/api/customers/{customer_id}/followups", json={"followup_date": tomorrow, "followup_time": "10:00"}).status_code == 409
    followup_id = followup.json()["id"]
    assert client.patch(f"/api/followups/{followup_id}", json={"status": "completed"}).status_code == 200
    assert client.get(f"/api/customers?search=Test+Customer").json()["total"] == 1
