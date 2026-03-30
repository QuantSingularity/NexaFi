from typing import Any
import pytest
from NexaFi.backend.document_service.src.main import app
from NexaFi.backend.document_service.src.models.user import User, db


@pytest.fixture(scope="module")
def client() -> Any:
    """
    Setup the test client and initialize the in-memory database.
    """
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.session.remove()
            db.drop_all()


@pytest.fixture(autouse=True)
def run_around_tests(client: Any) -> Any:
    """
    Clean up User table between tests to ensure isolation.
    """
    with app.app_context():
        User.query.delete()
        db.session.commit()
    yield


class TestUserModel:

    def test_user_creation(self) -> Any:
        user = User(username="testuser", email="test@example.com")
        db.session.add(user)
        db.session.commit()
        retrieved_user = User.query.filter_by(username="testuser").first()
        assert retrieved_user is not None
        assert retrieved_user.email == "test@example.com"

    def test_user_to_dict(self) -> Any:
        user = User(username="testuser2", email="test2@example.com")
        db.session.add(user)
        db.session.commit()
        user_dict = user.to_dict()
        assert user_dict["username"] == "testuser2"
        assert user_dict["email"] == "test2@example.com"
        assert "id" in user_dict
