"""
Integration tests for customer, follow-up, call, and health endpoints.

All tests use the FastAPI TestClient with SQLite. No external database required.
"""
import os
from datetime import date, timedelta

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_crm.db")
os.environ.setdefault("CRM_ADMIN_USERNAME", "admin")
os.environ.setdefault("CRM_ADMIN_PASSWORD", "test-password")
os.environ.setdefault("CRM_AUTH_SECRET", "test-secret")

from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test setup
# ---------------------------------------------------------------------------

def setup_module():
    """Drop and recreate all tables before test run."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def get_auth_client():
    """Return a TestClient with a valid auth token."""
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test-password"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    authed = TestClient(app)
    authed.headers["Authorization"] = f"Bearer {resp.json()['token']}"
    return authed


# ---------------------------------------------------------------------------
# Health tests
# ---------------------------------------------------------------------------

def test_health_liveness():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_legacy_alias():
    resp = client.get("/api/health")
    assert resp.status_code == 200


def test_health_readiness():
    resp = client.get("/health/ready")
    # Will be 200 if SQLite is accessible (which it always is in tests)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------

def test_login_success():
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test-password"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["username"] == "admin"


def test_login_wrong_password():
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert resp.status_code == 401


def test_unauthenticated_access_rejected():
    resp = client.get("/api/customers")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Customer CRUD tests
# ---------------------------------------------------------------------------

def test_create_customer():
    authed = get_auth_client()
    resp = authed.post(
        "/api/customers",
        json={"name": "Test User", "phone": "9111111111"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test User"
    assert data["phone"] == "9111111111"
    assert "id" in data


def test_create_customer_duplicate_phone():
    authed = get_auth_client()
    authed.post("/api/customers", json={"name": "Dup User A", "phone": "9222222222"})
    resp = authed.post("/api/customers", json={"name": "Dup User B", "phone": "9222222222"})
    assert resp.status_code == 409


def test_create_customer_duplicate_consumer_number():
    authed = get_auth_client()
    authed.post("/api/customers", json={"name": "Cons A", "consumer_number": "CON-999"})
    resp = authed.post("/api/customers", json={"name": "Cons B", "consumer_number": "CON-999"})
    assert resp.status_code == 409


def test_create_customer_missing_contact_identifier():
    authed = get_auth_client()
    resp = authed.post("/api/customers", json={"name": "No Contact"})
    assert resp.status_code == 400


def test_create_customer_no_name():
    authed = get_auth_client()
    resp = authed.post("/api/customers", json={"phone": "9333333333"})
    assert resp.status_code in (400, 422)  # pydantic validation or service validation


def test_get_customer_by_id():
    authed = get_auth_client()
    resp = authed.post("/api/customers", json={"name": "Get Test", "phone": "9444444444"})
    assert resp.status_code == 201
    customer_id = resp.json()["id"]

    resp = authed.get(f"/api/customers/{customer_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == customer_id


def test_get_nonexistent_customer():
    authed = get_auth_client()
    resp = authed.get("/api/customers/999999")
    assert resp.status_code == 404


def test_customer_list_pagination():
    authed = get_auth_client()
    resp = authed.get("/api/customers?page=1&limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "pages" in data
    assert len(data["items"]) <= 5


def test_customer_list_search():
    authed = get_auth_client()
    authed.post("/api/customers", json={"name": "SearchableUnique XYZ9", "phone": "9555555555"})
    resp = authed.get("/api/customers?search=SearchableUnique+XYZ9")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_update_customer_status():
    authed = get_auth_client()
    resp = authed.post("/api/customers", json={"name": "Update Test", "phone": "9666666666"})
    assert resp.status_code == 201
    customer_id = resp.json()["id"]

    resp = authed.patch(f"/api/customers/{customer_id}", json={"status": "interested"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "interested"


# ---------------------------------------------------------------------------
# Call log tests
# ---------------------------------------------------------------------------

def test_create_call_log():
    authed = get_auth_client()
    resp = authed.post("/api/customers", json={"name": "Call Test", "phone": "9777777777"})
    customer_id = resp.json()["id"]

    resp = authed.post(
        f"/api/customers/{customer_id}/calls",
        json={"call_status": "interested", "notes": "Will call back"},
    )
    assert resp.status_code == 201
    assert resp.json()["call_status"] == "interested"


def test_list_call_logs():
    authed = get_auth_client()
    resp = authed.post("/api/customers", json={"name": "Call List Test", "phone": "9888888888"})
    customer_id = resp.json()["id"]
    authed.post(f"/api/customers/{customer_id}/calls", json={"call_status": "busy"})

    resp = authed.get(f"/api/customers/{customer_id}/calls")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


# ---------------------------------------------------------------------------
# Follow-up tests
# ---------------------------------------------------------------------------

def test_create_followup():
    authed = get_auth_client()
    resp = authed.post("/api/customers", json={"name": "Followup Test", "phone": "9000000001"})
    customer_id = resp.json()["id"]
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    resp = authed.post(
        f"/api/customers/{customer_id}/followups",
        json={"followup_date": tomorrow, "followup_time": "10:00", "reason": "Busy"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["followup_date"] == tomorrow
    assert data["status"] == "pending"


def test_duplicate_followup_rejected():
    authed = get_auth_client()
    resp = authed.post("/api/customers", json={"name": "Dup Followup", "phone": "9000000002"})
    customer_id = resp.json()["id"]
    tomorrow = (date.today() + timedelta(days=2)).isoformat()

    authed.post(
        f"/api/customers/{customer_id}/followups",
        json={"followup_date": tomorrow, "followup_time": "11:00"},
    )
    resp = authed.post(
        f"/api/customers/{customer_id}/followups",
        json={"followup_date": tomorrow, "followup_time": "11:00"},
    )
    assert resp.status_code == 409


def test_past_followup_date_rejected():
    authed = get_auth_client()
    resp = authed.post("/api/customers", json={"name": "Past Test", "phone": "9000000003"})
    customer_id = resp.json()["id"]
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    resp = authed.post(
        f"/api/customers/{customer_id}/followups",
        json={"followup_date": yesterday},
    )
    assert resp.status_code == 400


def test_complete_followup():
    authed = get_auth_client()
    resp = authed.post("/api/customers", json={"name": "Complete Test", "phone": "9000000004"})
    customer_id = resp.json()["id"]
    tomorrow = (date.today() + timedelta(days=3)).isoformat()

    resp = authed.post(
        f"/api/customers/{customer_id}/followups",
        json={"followup_date": tomorrow},
    )
    followup_id = resp.json()["id"]

    resp = authed.patch(f"/api/followups/{followup_id}", json={"status": "completed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_delete_followup():
    authed = get_auth_client()
    resp = authed.post("/api/customers", json={"name": "Delete Test", "phone": "9000000005"})
    customer_id = resp.json()["id"]
    tomorrow = (date.today() + timedelta(days=4)).isoformat()

    resp = authed.post(
        f"/api/customers/{customer_id}/followups",
        json={"followup_date": tomorrow},
    )
    followup_id = resp.json()["id"]

    resp = authed.delete(f"/api/followups/{followup_id}")
    assert resp.status_code == 200

    resp = authed.patch(f"/api/followups/{followup_id}", json={"status": "completed"})
    assert resp.status_code == 404


def test_today_followups_returns_list():
    authed = get_auth_client()
    resp = authed.get("/api/followups/today")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_upcoming_followups_returns_list():
    authed = get_auth_client()
    resp = authed.get("/api/followups/upcoming?days=7")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_overdue_followups_returns_list():
    authed = get_auth_client()
    resp = authed.get("/api/followups/overdue")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# Dashboard tests
# ---------------------------------------------------------------------------

def test_dashboard_stats():
    authed = get_auth_client()
    resp = authed.get("/api/dashboard/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_customers" in data
    assert "today_followups" in data
    assert "overdue_followups" in data
    assert "upcoming_followups" in data
    assert "calls_today" in data
    assert isinstance(data["total_customers"], int)
