import pytest
from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app():
    """Create application for testing."""
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        # Create dress_id sequence for SQLite (no-op, use autoincrement instead)
        yield app
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    """Per-test database session with rollback."""
    with app.app_context():
        _db.session.begin_nested()
        yield _db
        _db.session.rollback()
