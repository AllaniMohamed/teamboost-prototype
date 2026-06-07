import pytest
from app import create_app
from app.agent import _run_investigation_internal
from app.database import db


@pytest.fixture
def app_context():
    app = create_app()
    app.config["TESTING"] = True

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_dependency_block_classification(app_context):
    investigation_id = _run_investigation_internal("pr-042")

    assert investigation_id is not None
    assert isinstance(investigation_id, int)