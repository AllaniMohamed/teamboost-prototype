import pytest
from app import create_app
from app.services import search_related_tasks

@pytest.fixture
def app_context():
    app = create_app()
    with app.app_context():
        yield app


def test_semantic_search_returns_related_tasks(app_context):
    results = search_related_tasks(
        "task-001",
        k=3,
        min_score=0.3,
        filters={"exclude_task_id": "task-001"}
    )

    task_ids = [r["task_id"] for r in results]

    # Expect auth-related task to appear
    assert "task-005" in task_ids