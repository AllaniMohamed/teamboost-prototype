import pytest
from app import create_app
from app.database import db
from app.agent import _run_investigation_internal
from app.models import Investigation


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_investigate_dependency_block(client):
    # Step 1: Call API (queue version)
    response = client.post(
        "/api/investigate",
        json={"pr_id": "pr-042"}
    )
    assert response.status_code == 200

    data = response.get_json()
    assert "job_id" in data

    # Step 2: Simulate worker execution synchronously
    with client.application.app_context():
        investigation_id = _run_investigation_internal("pr-042")

        investigation = Investigation.query.get(investigation_id)

        assert investigation.classification in ["DEPENDENCY_BLOCK", "SELF_STALL"]
        assert investigation.notification is not None
        assert investigation.created_at is not None