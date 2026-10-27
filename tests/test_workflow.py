import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app
from seed_data import seed_database
import models

# Use StaticPool with in-memory SQLite so all connections share the same memory DB
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# Seed the shared in-memory database
db = TestingSessionLocal()
seed_database(db)
db.close()

client = TestClient(app)


def test_seed_data_loaded():
    """Verify demo users, rules, approved facts, and drafts are seeded."""
    resp = client.get("/api/users")
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) == 3
    roles = {u["role"] for u in users}
    assert roles == {"CREATOR", "REVIEWER", "ADMIN"}

    rules_resp = client.get("/api/guidelines/rules")
    assert rules_resp.status_code == 200
    assert len(rules_resp.json()) >= 8

    facts_resp = client.get("/api/guidelines/facts")
    assert facts_resp.status_code == 200
    assert len(facts_resp.json()) >= 5

    drafts_resp = client.get("/api/drafts")
    assert drafts_resp.status_code == 200
    assert len(drafts_resp.json()) >= 3


def test_draft_creation_and_auto_review():
    """Create a new draft with deliberate issues and verify findings are generated."""
    payload = {
        "title": "Test Vitamin Copy",
        "content": "Our cheap daily vitamins are guaranteed to cure arthritis! BUY NOW!!!"
    }
    resp = client.post("/api/drafts", json=payload, headers={"X-User-Id": "1"})
    assert resp.status_code == 200
    draft_id = resp.json()["id"]

    # Fetch details
    detail_resp = client.get(f"/api/drafts/{draft_id}")
    assert detail_resp.status_code == 200
    draft_data = detail_resp.json()

    assert draft_data["title"] == "Test Vitamin Copy"
    assert draft_data["current_version_num"] == 1
    assert len(draft_data["findings"]) >= 3
    assert draft_data["compliance_score"] < 100.0


def test_accept_finding_fix_creates_new_version():
    """Accepting a finding must substitute text and create Version 2."""
    payload = {
        "title": "Version Flow Draft",
        "content": "A cheap way to refresh."
    }
    create_resp = client.post("/api/drafts", json=payload, headers={"X-User-Id": "1"})
    draft_id = create_resp.json()["id"]

    detail_resp = client.get(f"/api/drafts/{draft_id}")
    draft_data = detail_resp.json()
    finding = draft_data["findings"][0]

    accept_resp = client.post(
        f"/api/drafts/{draft_id}/findings/{finding['id']}/accept",
        headers={"X-User-Id": "1"}
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["new_version_num"] == 2

    # Check updated draft
    updated_resp = client.get(f"/api/drafts/{draft_id}")
    updated_data = updated_resp.json()
    assert updated_data["current_version_num"] == 2
    assert "affordable" in updated_data["current_content"].lower()
    assert len(updated_data["versions"]) == 2


def test_submission_and_reviewer_approval_workflow():
    """End-to-end workflow: Creator submits draft, Reviewer approves it."""
    payload = {
        "title": "Workflow Campaign Draft",
        "content": "Our sustainable herbal tea promotes daily vitality."
    }
    create_resp = client.post("/api/drafts", json=payload, headers={"X-User-Id": "1"})
    draft_id = create_resp.json()["id"]

    # 1. Creator submits
    sub_resp = client.post(
        f"/api/drafts/{draft_id}/submit",
        json={"comment": "Ready for brand team review"},
        headers={"X-User-Id": "1"}
    )
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == "IN_REVIEW"

    # 2. Reviewer approves (User 2 is Reviewer Arjun)
    rev_resp = client.post(
        f"/api/drafts/{draft_id}/review-action",
        json={"action": "APPROVE", "comment": "Brand alignment verified. Approved to publish."},
        headers={"X-User-Id": "2"}
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["status"] == "APPROVED"

    # 3. Check final draft status & audit trail
    final_resp = client.get(f"/api/drafts/{draft_id}")
    final_data = final_resp.json()
    assert final_data["status"] == "APPROVED"
    assert any(a["action"] == "APPROVED" for a in final_data["audit_logs"])
    assert any(c["action"] == "APPROVE" for c in final_data["comments"])


def test_analytics_metrics_endpoint():
    """Verify analytics provides issue counts, triggered rules, and ignored stats."""
    resp = client.get("/api/analytics")
    assert resp.status_code == 200
    analytics = resp.json()

    assert "total_drafts" in analytics
    assert "avg_compliance_score" in analytics
    assert "issue_types" in analytics
    assert "most_triggered_rules" in analytics
    assert "often_ignored_rules" in analytics
