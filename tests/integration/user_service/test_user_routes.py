from datetime import datetime, timedelta
from typing import Any
from unittest.mock import patch

import jwt
import pytest

from NexaFi.backend.user_service.src.main import app
from NexaFi.backend.user_service.src.models.user import (
    AuditLog,
    EmailVerification,
    PasswordReset,
    Permission,
    Role,
    RolePermission,
    User,
    UserCustomField,
    UserProfile,
    UserRole,
    UserSession,
    db,
)


@pytest.fixture(scope="module")
def client() -> Any:
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SECRET_KEY"] = "test-secret-key"
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            admin_role = Role(name="admin")
            user_role = Role(name="business_owner")
            db.session.add_all([admin_role, user_role])
            db.session.commit()
            manage_users_perm = Permission(name="manage_users")
            view_users_perm = Permission(name="view_users")
            db.session.add_all([manage_users_perm, view_users_perm])
            db.session.commit()
            admin_role_perm = RolePermission(
                role_id=admin_role.id, permission_id=manage_users_perm.id
            )
            db.session.add(admin_role_perm)
            db.session.commit()
        yield client
        with app.app_context():
            db.drop_all()


@pytest.fixture(autouse=True)
def run_around_tests(client: Any) -> Any:
    with app.app_context():
        User.query.delete()
        UserProfile.query.delete()
        UserSession.query.delete()
        AuditLog.query.delete()
        UserCustomField.query.delete()
        PasswordReset.query.delete()
        EmailVerification.query.delete()
        db.session.commit()
    yield


def create_test_user(
    email: Any,
    password: Any,
    first_name: Any,
    last_name: Any,
    is_active: Any = True,
    mfa_enabled: Any = False,
) -> Any:
    user = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        is_active=is_active,
        mfa_enabled=mfa_enabled,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def generate_auth_token(
    user_id: Any, expiration_delta: Any = timedelta(hours=1)
) -> Any:
    """Generates a JWT token, accepting an optional expiration delta."""
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + expiration_delta,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


class TestAuthRoutes:

    def test_register_success(self, client: Any) -> Any:
        data = {
            "email": "test@example.com",
            "password": "password123",
            "first_name": "John",
            "last_name": "Doe",
        }
        response = client.post("/api/v1/auth/register", json=data)
        assert response.status_code == 201
        json_data = response.get_json()
        assert json_data["message"] == "User registered successfully"
        assert "access_token" in json_data
        with app.app_context():
            user = User.query.filter_by(email="test@example.com").first()
            assert user is not None
            assert user.check_password("password123")

    def test_register_missing_fields(self, client: Any) -> Any:
        data = {
            "email": "test@example.com",
            "password": "password123",
            "first_name": "John",
        }
        response = client.post("/api/v1/auth/register", json=data)
        assert response.status_code == 400
        assert response.get_json()["error"] == "last_name is required"

    def test_register_email_exists(self, client: Any) -> Any:
        create_test_user("existing@example.com", "password123", "Jane", "Doe")
        data = {
            "email": "existing@example.com",
            "password": "newpassword",
            "first_name": "Jane",
            "last_name": "Doe",
        }
        response = client.post("/api/v1/auth/register", json=data)
        assert response.status_code == 409
        assert response.get_json()["error"] == "Email already registered"

    def test_login_success(self, client: Any) -> Any:
        create_test_user("login@example.com", "password123", "Login", "User")
        data = {"email": "login@example.com", "password": "password123"}
        response = client.post("/api/v1/auth/login", json=data)
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["message"] == "Login successful"
        assert "access_token" in json_data

    def test_login_invalid_credentials(self, client: Any) -> Any:
        create_test_user("invalid@example.com", "password123", "Invalid", "User")
        data = {"email": "invalid@example.com", "password": "wrongpassword"}
        response = client.post("/api/v1/auth/login", json=data)
        assert response.status_code == 401
        assert response.get_json()["error"] == "Invalid credentials"

    def test_login_deactivated_user(self, client: Any) -> Any:
        """Test login failure for an inactive user account."""
        create_test_user(
            "deactivated@example.com",
            "password123",
            "Deactivated",
            "User",
            is_active=False,
        )
        data = {"email": "deactivated@example.com", "password": "password123"}
        response = client.post("/api/v1/auth/login", json=data)
        assert response.status_code == 401
        assert response.get_json()["error"] == "Account is deactivated"

    def test_logout_success(self, client: Any) -> Any:
        user = create_test_user("logout@example.com", "password123", "Logout", "User")
        token = generate_auth_token(user.id)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post("/api/v1/auth/logout", headers=headers)
        assert response.status_code == 200
        assert response.get_json()["message"] == "Logout successful"
        with app.app_context():
            session = UserSession.query.filter_by(session_token=token).first()
            assert session is not None
            assert session.is_active == False

    def test_refresh_token_success(self, client: Any) -> Any:
        user = create_test_user("refresh@example.com", "password123", "Refresh", "User")
        old_access_token = generate_auth_token(user.id)
        refresh_token = "some_refresh_token"
        with app.app_context():
            session = UserSession(
                user_id=user.id,
                session_token=old_access_token,
                refresh_token=refresh_token,
                ip_address="127.0.0.1",
                user_agent="test",
                expires_at=datetime.utcnow() + timedelta(hours=1),
            )
            db.session.add(session)
            db.session.commit()
        data = {"refresh_token": refresh_token}
        response = client.post("/api/v1/auth/refresh", json=data)
        assert response.status_code == 200
        json_data = response.get_json()
        assert "access_token" in json_data
        assert "refresh_token" in json_data
        assert json_data["access_token"] != old_access_token


class TestMfaRoutes:

    def test_setup_mfa_success(self, client: Any) -> Any:
        user = create_test_user("mfa_setup@example.com", "password123", "MFA", "User")
        token = generate_auth_token(user.id)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post("/api/v1/auth/mfa/setup", headers=headers)
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["message"] == "MFA setup initiated"
        assert "secret" in json_data
        assert "qr_code" in json_data
        assert "backup_codes" in json_data

    def test_enable_mfa_success(self, client: Any) -> Any:
        user = create_test_user(
            "mfa_enable@example.com", "password123", "MFA", "Enable"
        )
        token = generate_auth_token(user.id)
        headers = {"Authorization": f"Bearer {token}"}
        with patch(
            "NexaFi.backend.user_service.src.models.user.User.verify_mfa_token",
            return_value=True,
        ):
            with app.app_context():
                user.mfa_secret = "mock_secret"
                db.session.commit()
            data = {"token": "123456"}
            response = client.post(
                "/api/v1/auth/mfa/enable", headers=headers, json=data
            )
            assert response.status_code == 200
            assert response.get_json()["message"] == "MFA enabled successfully"
            with app.app_context():
                updated_user = User.query.get(user.id)
                assert updated_user.mfa_enabled == True


class TestPasswordResetRoutes:

    def test_request_password_reset_success(self, client: Any) -> Any:
        user = create_test_user("reset@example.com", "password123", "Reset", "User")
        data = {"email": "reset@example.com"}
        response = client.post("/api/v1/auth/password-reset/request", json=data)
        assert response.status_code == 200
        assert response.get_json()["message"] == "Password reset email sent"
        with app.app_context():
            reset_request = PasswordReset.query.filter_by(user_id=user.id).first()
            assert reset_request is not None

    def test_reset_password_success(self, client: Any) -> Any:
        user = create_test_user("reset2@example.com", "oldpassword", "Reset2", "User")
        reset_token = "test_reset_token"
        with app.app_context():
            reset_req = PasswordReset(
                user_id=user.id,
                token=reset_token,
                expires_at=datetime.utcnow() + timedelta(hours=1),
            )
            db.session.add(reset_req)
            db.session.commit()
        data = {"token": reset_token, "new_password": "newsecurepassword"}
        response = client.post("/api/v1/auth/password-reset/confirm", json=data)
        assert response.status_code == 200
        assert response.get_json()["message"] == "Password reset successfully"
        with app.app_context():
            updated_user = User.query.get(user.id)
            assert updated_user.check_password("newsecurepassword")


class TestEmailVerificationRoutes:

    def test_request_email_verification_success(self, client: Any) -> Any:
        user = create_test_user("verify@example.com", "password123", "Verify", "User")
        user.is_email_verified = False
        with app.app_context():
            db.session.commit()
        token = generate_auth_token(user.id)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            "/api/v1/auth/email-verification/request", headers=headers
        )
        assert response.status_code == 200
        assert response.get_json()["message"] == "Verification email sent"
        with app.app_context():
            verification_req = EmailVerification.query.filter_by(
                user_id=user.id
            ).first()
            assert verification_req is not None

    def test_verify_email_success(self, client: Any) -> Any:
        user = create_test_user("verify2@example.com", "password123", "Verify2", "User")
        user.is_email_verified = False
        verification_token = "test_verification_token"
        with app.app_context():
            email_ver = EmailVerification(
                user_id=user.id,
                token=verification_token,
                expires_at=datetime.utcnow() + timedelta(hours=1),
            )
            db.session.add(email_ver)
            db.session.commit()
        data = {"token": verification_token}
        response = client.post("/api/v1/auth/email-verification/confirm", json=data)
        assert response.status_code == 200
        assert response.get_json()["message"] == "Email verified successfully"
        with app.app_context():
            updated_user = User.query.get(user.id)
            assert updated_user.is_email_verified == True


class TestUserManagementRoutes:

    def test_unauthorized_access_admin_route(self, client: Any) -> Any:
        """Test accessing a protected admin route without a token."""
        response = client.get("/api/v1/users")
        assert response.status_code == 401
        assert response.get_json()["error"] == "Missing Authorization Header"

    def test_expired_token_access(self, client: Any) -> Any:
        """Test accessing a protected route with an expired token."""
        user = create_test_user(
            "expired@example.com", "password123", "Expired", "Token"
        )
        expired_token = generate_auth_token(
            user.id, expiration_delta=timedelta(hours=-1)
        )
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 401
        assert "Token expired" in response.get_json()["error"]

    def test_forbidden_access_admin_route(self, client: Any) -> Any:
        """Test non-admin user accessing an admin-only route."""
        non_admin_user = create_test_user(
            "nonadmin@example.com", "password123", "Non", "Admin"
        )
        with app.app_context():
            business_owner_role = Role.query.filter_by(name="business_owner").first()
            user_role = UserRole(
                user_id=non_admin_user.id, role_id=business_owner_role.id
            )
            db.session.add(user_role)
            db.session.commit()
        token = generate_auth_token(non_admin_user.id)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/users", headers=headers)
        assert response.status_code == 403
        assert response.get_json()["error"] == "Permission denied"

    def test_get_current_user_success(self, client: Any) -> Any:
        user = create_test_user("current@example.com", "password123", "Current", "User")
        token = generate_auth_token(user.id)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["user"]["email"] == "current@example.com"

    def test_update_current_user_success(self, client: Any) -> Any:
        user = create_test_user("update@example.com", "password123", "Update", "User")
        token = generate_auth_token(user.id)
        headers = {"Authorization": f"Bearer {token}"}
        data = {"first_name": "Updated", "phone": "123-456-7890"}
        response = client.put("/api/v1/users/me", headers=headers, json=data)
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["message"] == "User profile updated successfully"
        assert json_data["user"]["first_name"] == "Updated"
        with app.app_context():
            updated_user = User.query.get(user.id)
            assert updated_user.first_name == "Updated"

    def test_get_all_users_success(self, client: Any) -> Any:
        admin_user = create_test_user(
            "admin@example.com", "password123", "Admin", "User"
        )
        with app.app_context():
            admin_role = Role.query.filter_by(name="admin").first()
            user_role = UserRole(user_id=admin_user.id, role_id=admin_role.id)
            db.session.add(user_role)
            db.session.commit()
        create_test_user("user1@example.com", "password123", "User1", "One")
        create_test_user("user2@example.com", "password123", "User2", "Two")
        token = generate_auth_token(admin_user.id)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/users", headers=headers)
        assert response.status_code == 200
        json_data = response.get_json()
        assert len(json_data["users"]) >= 3

    def test_get_user_by_id_success(self, client: Any) -> Any:
        admin_user = create_test_user(
            "admin_get@example.com", "password123", "AdminGet", "User"
        )
        with app.app_context():
            admin_role = Role.query.filter_by(name="admin").first()
            user_role = UserRole(user_id=admin_user.id, role_id=admin_role.id)
            db.session.add(user_role)
            db.session.commit()
        target_user = create_test_user(
            "target@example.com", "password123", "Target", "User"
        )
        token = generate_auth_token(admin_user.id)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(f"/api/v1/users/{target_user.id}", headers=headers)
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["user"]["email"] == "target@example.com"

    def test_delete_user_success(self, client: Any) -> Any:
        admin_user = create_test_user(
            "admin_delete@example.com", "password123", "AdminDelete", "User"
        )
        with app.app_context():
            admin_role = Role.query.filter_by(name="admin").first()
            user_role = UserRole(user_id=admin_user.id, role_id=admin_role.id)
            db.session.add(user_role)
            db.session.commit()
        user_to_delete = create_test_user(
            "delete@example.com", "password123", "Delete", "User"
        )
        token = generate_auth_token(admin_user.id)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.delete(f"/api/v1/users/{user_to_delete.id}", headers=headers)
        assert response.status_code == 200
        assert response.get_json()["message"] == "User deleted successfully"
        with app.app_context():
            deleted_user = User.query.get(user_to_delete.id)
            assert deleted_user.is_active == False


class TestRolePermissionRoutes:

    def test_get_roles_success(self, client: Any) -> Any:
        user = create_test_user("role_user@example.com", "password123", "Role", "User")
        token = generate_auth_token(user.id)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/roles", headers=headers)
        assert response.status_code == 200
        json_data = response.get_json()
        assert len(json_data["roles"]) >= 2

    def test_assign_role_success(self, client: Any) -> Any:
        admin_user = create_test_user(
            "admin_role@example.com", "password123", "Admin", "Role"
        )
        with app.app_context():
            admin_role = Role.query.filter_by(name="admin").first()
            user_role = UserRole(user_id=admin_user.id, role_id=admin_role.id)
            db.session.add(user_role)
            db.session.commit()
        target_user = create_test_user(
            "assign_role@example.com", "password123", "Assign", "Role"
        )
        with app.app_context():
            business_owner_role = Role.query.filter_by(name="business_owner").first()
        token = generate_auth_token(admin_user.id)
        headers = {"Authorization": f"Bearer {token}"}
        data = {"user_id": target_user.id, "role_id": business_owner_role.id}
        response = client.post("/api/v1/roles/assign", headers=headers, json=data)
        assert response.status_code == 200
        assert response.get_json()["message"] == "Role assigned successfully"
        with app.app_context():
            user_has_role = UserRole.query.filter_by(
                user_id=target_user.id, role_id=business_owner_role.id
            ).first()
            assert user_has_role is not None


class TestAuditLogRoutes:

    def test_get_audit_logs_success(self, client: Any) -> Any:
        admin_user = create_test_user(
            "admin_audit@example.com", "password123", "Admin", "Audit"
        )
        with app.app_context():
            admin_role = Role.query.filter_by(name="admin").first()
            user_role = UserRole(user_id=admin_user.id, role_id=admin_role.id)
            db.session.add(user_role)
            db.session.commit()
        with app.app_context():
            audit_log = AuditLog(
                user_id=admin_user.id,
                action="test_action",
                resource_type="test_resource",
                resource_id="123",
            )
            db.session.add(audit_log)
            db.session.commit()
        token = generate_auth_token(admin_user.id)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/audit-logs", headers=headers)
        assert response.status_code == 200
        json_data = response.get_json()
        assert len(json_data["audit_logs"]) >= 1
        assert json_data["audit_logs"][0]["action"] == "test_action"
