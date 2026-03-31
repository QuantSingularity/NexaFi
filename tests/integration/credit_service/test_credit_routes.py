from typing import Any

import pytest

from NexaFi.backend.credit_service.src.main import app
from NexaFi.backend.credit_service.src.models.user import User, db


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


class TestCreditServiceRoutes:

    def test_get_users_empty(self, client: Any) -> Any:
        response = client.get("/api/users")
        assert response.status_code == 200
        assert response.get_json() == []

    def test_create_user_success(self, client: Any) -> Any:
        data = {"username": "testuser", "email": "test@example.com"}
        response = client.post("/api/users", json=data)
        assert response.status_code == 201
        json_data = response.get_json()
        assert json_data["username"] == "testuser"
        assert json_data["email"] == "test@example.com"
        assert "id" in json_data
        with app.app_context():
            user = User.query.filter_by(username="testuser").first()
            assert user is not None

    def test_get_user_success(self, client: Any) -> Any:
        with app.app_context():
            user = User(username="existinguser", email="existing@example.com")
            db.session.add(user)
            db.session.commit()
            user_id = user.id
        response = client.get(f"/api/users/{user_id}")
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["username"] == "existinguser"

    def test_get_user_not_found(self, client: Any) -> Any:
        response = client.get("/api/users/999")
        assert response.status_code == 404

    def test_update_user_success(self, client: Any) -> Any:
        with app.app_context():
            user = User(username="olduser", email="old@example.com")
            db.session.add(user)
            db.session.commit()
            user_id = user.id
        data = {"username": "newuser", "email": "new@example.com"}
        response = client.put(f"/api/users/{user_id}", json=data)
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["username"] == "newuser"
        assert json_data["email"] == "new@example.com"
        with app.app_context():
            updated_user = User.query.get(user_id)
            assert updated_user.username == "newuser"

    def test_update_user_not_found(self, client: Any) -> Any:
        data = {"username": "newuser", "email": "new@example.com"}
        response = client.put("/api/users/999", json=data)
        assert response.status_code == 404

    def test_delete_user_success(self, client: Any) -> Any:
        with app.app_context():
            user = User(username="todelete", email="todelete@example.com")
            db.session.add(user)
            db.session.commit()
            user_id = user.id
        response = client.delete(f"/api/users/{user_id}")
        assert response.status_code == 204
        with app.app_context():
            deleted_user = User.query.get(user_id)
            assert deleted_user is None

    def test_delete_user_not_found(self, client: Any) -> Any:
        response = client.delete("/api/users/999")
        assert response.status_code == 404
