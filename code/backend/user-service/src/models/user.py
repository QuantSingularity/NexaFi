from datetime import datetime, timedelta
from typing import Any, Dict, Optional


class BaseModel:
    """Placeholder for BaseModel to avoid import errors in this file.
    The actual BaseModel is imported and set in main.py."""


class User(BaseModel):
    table_name: Optional[str] = "users"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        if not hasattr(self, "created_at"):
            self.created_at = datetime.utcnow()
        if not hasattr(self, "updated_at"):
            self.updated_at = datetime.utcnow()
        if not hasattr(self, "is_active"):
            self.is_active = True
        if not hasattr(self, "email_verified"):
            self.email_verified = False
        if not hasattr(self, "failed_login_attempts"):
            self.failed_login_attempts = 0

    def set_password(self, password: str, auth_manager: Any) -> Any:
        """Set hashed password"""
        self.password_hash = auth_manager.hash_password(password)

    def check_password(self, password: str, auth_manager: Any) -> bool:
        """Check password against hash"""
        return auth_manager.verify_password(password, self.password_hash)

    def is_locked(self) -> bool:
        """Check if account is locked"""
        if self.locked_until:
            locked_until = datetime.fromisoformat(
                self.locked_until.replace("Z", "+00:00")
            )
            return datetime.utcnow() < locked_until
        return False

    def lock_account(self, duration_minutes: int = 30) -> Any:
        """Lock account for specified duration"""
        self.locked_until = (
            datetime.utcnow() + timedelta(minutes=duration_minutes)
        ).isoformat()
        self.save()

    def unlock_account(self) -> Any:
        """Unlock account"""
        self.locked_until = None
        self.failed_login_attempts = 0
        self.save()

    def increment_failed_attempts(self) -> Any:
        """Increment failed login attempts"""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.lock_account()
        self.save()

    def reset_failed_attempts(self) -> Any:
        """Reset failed login attempts"""
        self.failed_login_attempts = 0
        self.save()

    def get_roles(self) -> list:
        """Get user roles"""
        query = "SELECT role_name FROM user_roles WHERE user_id = ?"
        rows = self.db_manager.execute_query(query, (self.id,))
        return [row["role_name"] for row in rows]

    def add_role(self, role_name: str, granted_by: Optional[int] = None) -> Any:
        """Add role to user"""
        query = (
            "INSERT INTO user_roles (user_id, role_name, granted_by) VALUES (?, ?, ?)"
        )
        self.db_manager.execute_insert(query, (self.id, role_name, granted_by))

    def remove_role(self, role_name: str) -> Any:
        """Remove role from user"""
        query = "DELETE FROM user_roles WHERE user_id = ? AND role_name = ?"
        self.db_manager.execute_update(query, (self.id, role_name))

    def to_dict(self, include_sensitive: Any = False) -> Dict[str, Any]:
        """Convert user to dictionary"""
        data = super().to_dict()
        if not include_sensitive:
            data.pop("password_hash", None)
            data.pop("failed_login_attempts", None)
            data.pop("locked_until", None)
        data["roles"] = self.get_roles()
        return data


class UserSession(BaseModel):
    table_name: Optional[str] = "user_sessions"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        if not hasattr(self, "created_at"):
            self.created_at = datetime.utcnow()
        if not hasattr(self, "updated_at"):
            self.updated_at = datetime.utcnow()
        if not hasattr(self, "is_active"):
            self.is_active = True
        if not hasattr(self, "expires_at"):
            self.expires_at = datetime.utcnow() + timedelta(days=7)

    def is_expired(self) -> bool:
        """Check if session is expired"""
        return datetime.utcnow() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary"""
        data = super().to_dict()
        data["is_expired"] = self.is_expired()
        return data
