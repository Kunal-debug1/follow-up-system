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
def test_customer_archive_and_restore_workflow():
    client = client_with_token()
    # Create customer
    resp = client.post("/api/customers", json={"name": "Archive Test Customer", "phone": "9876500001"})
    assert resp.status_code == 201
    cid = resp.json()["id"]

    # Customer appears in active list
    resp = client.get("/api/customers?search=Archive+Test+Customer")
    assert resp.status_code == 200
    assert any(c["id"] == cid for c in resp.json()["items"])

    # Archive customer
    resp = client.post(f"/api/customers/{cid}/archive")
    assert resp.status_code == 200
    assert resp.json()["is_archived"] is True

    # Customer does NOT appear in active list
    resp = client.get("/api/customers?search=Archive+Test+Customer")
    assert resp.status_code == 200
    assert not any(c["id"] == cid for c in resp.json()["items"])

    # Customer DOES appear in archived list
    resp = client.get("/api/customers?search=Archive+Test+Customer&archived=true")
    assert resp.status_code == 200
    assert any(c["id"] == cid for c in resp.json()["items"])

    # Restore customer
    resp = client.post(f"/api/customers/{cid}/restore")
    assert resp.status_code == 200
    assert resp.json()["is_archived"] is False

    # Customer back in active list
    resp = client.get("/api/customers?search=Archive+Test+Customer")
    assert resp.status_code == 200
    assert any(c["id"] == cid for c in resp.json()["items"])


def test_complete_followup_workflow():
    client = client_with_token()
    # Create customer
    c_resp = client.post("/api/customers", json={"name": "Complete FU Test", "phone": "9876500002"})
    cid = c_resp.json()["id"]

    # Create initial follow-up
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    day_after = (date.today() + timedelta(days=2)).isoformat()
    fu_resp = client.post(
        f"/api/customers/{cid}/followups",
        json={"followup_date": tomorrow, "reason": "Initial outreach"},
    )
    assert fu_resp.status_code == 201
    fuid = fu_resp.json()["id"]

    # Complete follow-up and schedule next
    comp_resp = client.post(
        f"/api/followups/{fuid}/complete",
        json={
            "outcome": "interested",
            "notes": "Discussed product demo",
            "create_next": True,
            "next_date": day_after,
            "next_time": "14:30",
            "next_reason": "Demo follow-up",
        },
    )
    assert comp_resp.status_code == 200
    data = comp_resp.json()
    assert data["completed"]["status"] == "completed"
    assert data["completed"]["outcome"] == "interested"
    assert data["next_followup"] is not None
    assert data["next_followup"]["followup_date"] == day_after
    assert data["next_followup"]["status"] == "pending"


def test_customer_timeline_and_recent_calls():
    client = client_with_token()
    # Create customer
    c_resp = client.post("/api/customers", json={"name": "Timeline User", "phone": "9876500003"})
    cid = c_resp.json()["id"]

    # Log call
    call_resp = client.post(f"/api/customers/{cid}/calls", json={"call_status": "interested", "notes": "Had a great chat"})
    assert call_resp.status_code == 201

    # Check timeline
    t_resp = client.get(f"/api/customers/{cid}/timeline")
    assert t_resp.status_code == 200
    events = t_resp.json()
    assert len(events) >= 2  # created + call
    event_types = [e["event_type"] for e in events]
    assert "created" in event_types
    assert "call" in event_types

    # Check recent calls endpoint includes this customer
    rc_resp = client.get("/api/calls/recent")
    assert rc_resp.status_code == 200
    calls = rc_resp.json()
    assert any(c["customer_id"] == cid and c["customer_name"] == "Timeline User" for c in calls)
