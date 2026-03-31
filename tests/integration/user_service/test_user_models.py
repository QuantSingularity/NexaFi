import json
from datetime import datetime, timedelta
from typing import Any

import pyotp
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
            admin_role = Role(name="admin", display_name="Administrator")
            business_owner_role = Role(
                name="business_owner", display_name="Business Owner"
            )
            db.session.add_all([admin_role, business_owner_role])
            db.session.commit()
            manage_users_perm = Permission(
                name="manage_users", display_name="Manage Users"
            )
            view_users_perm = Permission(name="view_users", display_name="View Users")
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


class TestUserModel:

    def test_user_creation(self) -> Any:
        user = User(
            email="test@example.com",
            password_hash="hashed_password",
            first_name="John",
            last_name="Doe",
        )
        db.session.add(user)
        db.session.commit()
        retrieved_user = User.query.filter_by(email="test@example.com").first()
        assert retrieved_user is not None
        assert retrieved_user.first_name == "John"

    def test_set_and_check_password(self) -> Any:
        user = User(email="password@example.com", first_name="Pass", last_name="Word")
        user.set_password("secure_password")
        db.session.add(user)
        db.session.commit()
        retrieved_user = User.query.filter_by(email="password@example.com").first()
        assert retrieved_user.check_password("secure_password") == True
        assert retrieved_user.check_password("wrong_password") == False

    def test_account_locking(self) -> Any:
        user = create_test_user("lock@example.com", "password", "Lock", "User")
        assert user.is_locked() == False
        user.lock_account(duration_minutes=1)
        db.session.commit()
        assert user.is_locked() == True
        user.locked_until = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()
        assert user.is_locked() == False

    def test_failed_login_attempts(self) -> Any:
        user = create_test_user("failed@example.com", "password", "Failed", "Login")
        assert user.failed_login_attempts == 0
        assert user.is_locked() == False
        for _ in range(4):
            user.increment_failed_login()
            db.session.commit()
        assert user.failed_login_attempts == 4
        assert user.is_locked() == False
        user.increment_failed_login()
        db.session.commit()
        assert user.failed_login_attempts == 0
        assert user.is_locked() == True

    def test_mfa_setup_and_verification(self) -> Any:
        user = create_test_user("mfa@example.com", "password", "MFA", "User")
        assert user.mfa_enabled == False
        assert user.mfa_secret is None
        secret, backup_codes = user.setup_mfa()
        db.session.commit()
        assert user.mfa_secret is not None
        assert len(backup_codes) == 10
        assert json.loads(user.backup_codes) == backup_codes
        totp = pyotp.TOTP(secret)
        assert user.verify_mfa_token(totp.now()) == True
        first_backup_code = backup_codes[0]
        assert user.verify_mfa_token(first_backup_code) == True
        assert first_backup_code not in json.loads(user.backup_codes)

    def test_has_permission(self) -> Any:
        user = create_test_user("perm@example.com", "password", "Perm", "User")
        with app.app_context():
            admin_role = Role.query.filter_by(name="admin").first()
            user_role_obj = UserRole(user_id=user.id, role_id=admin_role.id)
            db.session.add(user_role_obj)
            db.session.commit()
        assert user.has_permission("manage_users") == True
        assert user.has_permission("non_existent_permission") == False

    def test_get_permissions(self) -> Any:
        user = create_test_user("getperm@example.com", "password", "Get", "Perm")
        with app.app_context():
            view_users_perm = Permission.query.filter_by(name="view_users").first()
            viewer_role = Role(name="viewer", display_name="Viewer")
            db.session.add(viewer_role)
            db.session.commit()
            viewer_role_perm = RolePermission(
                role_id=viewer_role.id, permission_id=view_users_perm.id
            )
            db.session.add(viewer_role_perm)
            user_role_obj = UserRole(user_id=user.id, role_id=viewer_role.id)
            db.session.add(user_role_obj)
            db.session.commit()
        permissions = user.get_permissions()
        assert "manage_users" not in permissions
        assert "view_users" in permissions


class TestUserProfileModel:

    def test_user_profile_creation(self) -> Any:
        user = create_test_user("profile@example.com", "password", "Profile", "User")
        profile = UserProfile(
            user_id=user.id, company_name="Test Co.", timezone="America/New_York"
        )
        db.session.add(profile)
        db.session.commit()
        retrieved_profile = UserProfile.query.filter_by(user_id=user.id).first()
        assert retrieved_profile is not None
        assert retrieved_profile.company_name == "Test Co."


class TestRoleModel:

    def test_role_creation(self) -> Any:
        role = Role(
            name="new_role", display_name="New Role", description="A new test role"
        )
        db.session.add(role)
        db.session.commit()
        retrieved_role = Role.query.filter_by(name="new_role").first()
        assert retrieved_role is not None
        assert retrieved_role.display_name == "New Role"

    def test_role_has_permission(self) -> Any:
        with app.app_context():
            admin_role = Role.query.filter_by(name="admin").first()
            assert admin_role.has_permission("manage_users") == True
            assert admin_role.has_permission("non_existent_permission") == False


class TestPermissionModel:

    def test_permission_creation(self) -> Any:
        permission = Permission(
            name="test_perm",
            display_name="Test Permission",
            resource="test",
            action="do",
        )
        db.session.add(permission)
        db.session.commit()
        retrieved_permission = Permission.query.filter_by(name="test_perm").first()
        assert retrieved_permission is not None
        assert retrieved_permission.resource == "test"


class TestUserSessionModel:

    def test_user_session_creation_and_expiration(self) -> Any:
        user = create_test_user("session@example.com", "password", "Session", "User")
        session = UserSession(
            user_id=user.id,
            session_token="test_session_token",
            refresh_token="test_refresh_token",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db.session.add(session)
        db.session.commit()
        retrieved_session = UserSession.query.filter_by(user_id=user.id).first()
        assert retrieved_session is not None
        assert retrieved_session.is_expired() == False
        retrieved_session.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()
        assert retrieved_session.is_expired() == True

    def test_extend_session(self) -> Any:
        user = create_test_user("extend@example.com", "password", "Extend", "User")
        session = UserSession(
            user_id=user.id,
            session_token="extend_session_token",
            refresh_token="extend_refresh_token",
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )
        db.session.add(session)
        db.session.commit()
        old_expires_at = session.expires_at
        session.extend_session(hours=2)
        db.session.commit()
        assert session.expires_at > old_expires_at
        expected_expiration = datetime.utcnow() + timedelta(hours=2)
        time_difference = abs(session.expires_at - expected_expiration)
        assert time_difference < timedelta(seconds=5)


class TestAuditLogModel:

    def test_audit_log_creation(self) -> Any:
        user = create_test_user("audit@example.com", "password", "Audit", "User")
        log = AuditLog(
            user_id=user.id,
            action="user_login",
            resource_type="user",
            resource_id=user.id,
            status="success",
        )
        db.session.add(log)
        db.session.commit()
        retrieved_log = AuditLog.query.filter_by(user_id=user.id).first()
        assert retrieved_log is not None
        assert retrieved_log.action == "user_login"


class TestUserCustomFieldModel:

    def test_user_custom_field_creation(self) -> Any:
        user = create_test_user("custom@example.com", "password", "Custom", "User")
        custom_field = UserCustomField(
            user_id=user.id,
            field_name="favorite_color",
            field_value="blue",
            field_type="text",
        )
        db.session.add(custom_field)
        db.session.commit()
        retrieved_field = UserCustomField.query.filter_by(user_id=user.id).first()
        assert retrieved_field is not None
        assert retrieved_field.field_name == "favorite_color"
        assert retrieved_field.field_value == "blue"


class TestPasswordResetModel:

    def test_password_reset_creation_and_expiration(self) -> Any:
        user = create_test_user("reset_model@example.com", "password", "Reset", "Model")
        reset = PasswordReset(
            user_id=user.id,
            token="reset_token_123",
            expires_at=datetime.utcnow() + timedelta(minutes=30),
        )
        db.session.add(reset)
        db.session.commit()
        retrieved_reset = PasswordReset.query.filter_by(user_id=user.id).first()
        assert retrieved_reset is not None
        assert retrieved_reset.is_expired() == False
        retrieved_reset.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()
        assert retrieved_reset.is_expired() == True


class TestEmailVerificationModel:

    def test_email_verification_creation_and_expiration(self) -> Any:
        user = create_test_user(
            "verify_model@example.com", "password", "Verify", "Model"
        )
        verification = EmailVerification(
            user_id=user.id,
            token="verify_token_123",
            expires_at=datetime.utcnow() + timedelta(minutes=30),
        )
        db.session.add(verification)
        db.session.commit()
        retrieved_verification = EmailVerification.query.filter_by(
            user_id=user.id
        ).first()
        assert retrieved_verification is not None
        assert retrieved_verification.is_expired() == False
        retrieved_verification.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()
        assert retrieved_verification.is_expired() == True
