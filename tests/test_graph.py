import pytest
from app import create_app, db
from app.seed_loader import load_seed_data
from app.services import get_dependency_graph, get_blocked_engineers

@pytest.fixture
def app_context():
    app = create_app()
    with app.app_context():
        db.create_all()
        load_seed_data(app)
        yield app
        db.session.remove()
        db.drop_all()


def test_dependency_graph(app_context):
    result = get_dependency_graph("task-001")

    assert "task-002" in result["downstream"]
    assert "task-006" in result["downstream"]
    assert result["upstream"] == []


def test_blocked_engineers(app_context):
    result = get_blocked_engineers("task-001")

    assert "engineer-b" in result
    assert len(result) == 1