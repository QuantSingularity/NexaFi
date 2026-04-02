"""
Database utilities and connection management for NexaFi
Implements connection pooling, transaction management, and database migrations
"""

import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Dict, List, Tuple

logger = logging.get_logger(__name__)


class DatabaseManager:
    """Database connection and transaction manager"""

    def __init__(self, db_path: str, pool_size: int = 10) -> None:
        self.db_path = db_path
        self.pool_size = pool_size
        self.connections = []
        self.lock = threading.Lock()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._initialize_pool()

    def _initialize_pool(self) -> Any:
        """Initialize connection pool"""
        for _ in range(self.pool_size):
            conn = self._create_connection()
            self.connections.append(conn)

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def get_connection(self) -> Any:
        """Get connection from pool"""
        conn = None
        try:
            with self.lock:
                if self.connections:
                    conn = self.connections.pop()
                else:
                    conn = self._create_connection()
            yield conn
        finally:
            if conn:
                with self.lock:
                    if len(self.connections) < self.pool_size:
                        self.connections.append(conn)
                    else:
                        conn.close()

    @contextmanager
    def transaction(self) -> Any:
        """Database transaction context manager"""
        with self.get_connection() as conn:
            try:
                conn.execute("BEGIN")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def execute_query(self, query: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """Execute SELECT query"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()

    def execute_update(self, query: str, params: Tuple = ()) -> int:
        """Execute INSERT/UPDATE/DELETE query"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.rowcount

    def execute_insert(self, query: str, params: Tuple = ()) -> int:
        """Execute INSERT query and return last row ID"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.lastrowid

    def close_all_connections(self) -> Any:
        """Close all connections in pool"""
        with self.lock:
            for conn in self.connections:
                conn.close()
            self.connections.clear()


class MigrationManager:
    """Database migration management"""

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager
        self.migrations_table = "schema_migrations"
        self._ensure_migrations_table()

    def _ensure_migrations_table(self) -> Any:
        """Create migrations tracking table"""
        query = f"\n        CREATE TABLE IF NOT EXISTS {self.migrations_table} (\n            version TEXT PRIMARY KEY,\n            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n            description TEXT\n        )\n        "
        self.db_manager.execute_update(query)

    def get_applied_migrations(self) -> List[str]:
        """Get list of applied migration versions"""
        query = f"SELECT version FROM {self.migrations_table} ORDER BY version"
        rows = self.db_manager.execute_query(query)
        return [row["version"] for row in rows]

    def apply_migration(self, version: str, description: str, sql: str) -> Any:
        """Apply a database migration"""
        applied_migrations = self.get_applied_migrations()
        if version in applied_migrations:
            logger.info(f"Migration {version} already applied")
            return
        logger.info(f"Applying migration {version}: {description}")
        with self.db_manager.transaction() as conn:
            for statement in sql.split(";"):
                statement = statement.strip()
                if statement:
                    conn.execute(statement)
            conn.execute(
                f"INSERT INTO {self.migrations_table} (version, description) VALUES (?, ?)",
                (version, description),
            )
        logger.info(f"Migration {version} applied successfully")

    def rollback_migration(self, version: str, rollback_sql: str) -> Any:
        """Rollback a database migration"""
        applied_migrations = self.get_applied_migrations()
        if version not in applied_migrations:
            logger.info(f"Migration {version} not applied")
            return
        logger.info(f"Rolling back migration {version}")
        with self.db_manager.transaction() as conn:
            for statement in rollback_sql.split(";"):
                statement = statement.strip()
                if statement:
                    conn.execute(statement)
            conn.execute(
                f"DELETE FROM {self.migrations_table} WHERE version = ?", (version,)
            )
        logger.info(f"Migration {version} rolled back successfully")


class BaseModel:
    """Base model class with common database operations"""

    table_name = None
    db_manager = None

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def set_db_manager(cls: Any, db_manager: DatabaseManager) -> Any:
        """Set database manager for all models"""
        cls.db_manager = db_manager

    @classmethod
    def find_by_id(cls: Any, id_value: Any) -> Any:
        """Find record by ID"""
        query = f"SELECT * FROM {cls.table_name} WHERE id = ?"
        rows = cls.db_manager.execute_query(query, (id_value,))
        if rows:
            return cls(**dict(rows[0]))
        return None

    @classmethod
    def find_all(cls: Any, where_clause: str = "", params: Tuple = ()) -> Any:
        """Find all records matching criteria"""
        query = f"SELECT * FROM {cls.table_name}"
        if where_clause:
            query += f" WHERE {where_clause}"
        rows = cls.db_manager.execute_query(query, params)
        return [cls(**dict(row)) for row in rows]

    @classmethod
    def find_one(cls: Any, where_clause: str, params: Tuple = ()) -> Any:
        """Find one record matching criteria"""
        query = f"SELECT * FROM {cls.table_name} WHERE {where_clause} LIMIT 1"
        rows = cls.db_manager.execute_query(query, params)
        if rows:
            return cls(**dict(rows[0]))
        return None

    def save(self) -> Any:
        """Save record to database"""
        if hasattr(self, "id") and self.id:
            return self._update()
        else:
            return self._insert()

    def _insert(self) -> Any:
        """Insert new record"""
        fields = [k for k in self.__dict__.keys() if k != "id"]
        values = [getattr(self, k) for k in fields]
        placeholders = ", ".join(["?" for _ in fields])
        field_names = ", ".join(fields)
        query = f"INSERT INTO {self.table_name} ({field_names}) VALUES ({placeholders})"
        self.id = self.db_manager.execute_insert(query, tuple(values))
        return self

    def _update(self) -> Any:
        """Update existing record"""
        fields = [k for k in self.__dict__.keys() if k != "id"]
        values = [getattr(self, k) for k in fields]
        set_clause = ", ".join([f"{field} = ?" for field in fields])
        query = f"UPDATE {self.table_name} SET {set_clause} WHERE id = ?"
        values.append(self.id)
        self.db_manager.execute_update(query, tuple(values))
        return self

    def delete(self) -> Any:
        """Delete record from database"""
        if hasattr(self, "id") and self.id:
            query = f"DELETE FROM {self.table_name} WHERE id = ?"
            self.db_manager.execute_update(query, (self.id,))

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


INITIAL_MIGRATIONS = {
    "001_create_users_table": {
        "description": "Create users table with robust security features",
        "sql": "\n        CREATE TABLE IF NOT EXISTS users (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            email TEXT UNIQUE NOT NULL,\n            password_hash TEXT NOT NULL,\n            first_name TEXT NOT NULL,\n            last_name TEXT NOT NULL,\n            phone TEXT,\n            company_name TEXT,\n            is_active BOOLEAN DEFAULT 1,\n            email_verified BOOLEAN DEFAULT 0,\n            failed_login_attempts INTEGER DEFAULT 0,\n            locked_until TIMESTAMP NULL,\n            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n        );\n\n        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);\n        CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);\n        ",
    },
    "002_create_user_roles_table": {
        "description": "Create user roles and permissions",
        "sql": "\n        CREATE TABLE IF NOT EXISTS user_roles (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            user_id INTEGER NOT NULL,\n            role_name TEXT NOT NULL,\n            granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n            granted_by INTEGER,\n            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,\n            FOREIGN KEY (granted_by) REFERENCES users(id)\n        );\n\n        CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);\n        CREATE INDEX IF NOT EXISTS idx_user_roles_role ON user_roles(role_name);\n        ",
    },
    "003_create_audit_log_table": {
        "description": "Create audit log table",
        "sql": "\n        CREATE TABLE IF NOT EXISTS audit_log (\n            id INTEGER PRIMARY KEY AUTOINCREMENT,\n            event_id TEXT UNIQUE NOT NULL,\n            event_type TEXT NOT NULL,\n            user_id TEXT,\n            resource_type TEXT,\n            resource_id TEXT,\n            action TEXT NOT NULL,\n            details TEXT,\n            ip_address TEXT,\n            user_agent TEXT,\n            success BOOLEAN NOT NULL,\n            error_message TEXT,\n            event_hash TEXT NOT NULL,\n            chain_hash TEXT NOT NULL,\n            previous_hash TEXT,\n            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n        );\n\n        CREATE INDEX IF NOT EXISTS idx_audit_log_event_type ON audit_log(event_type);\n        CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id);\n        CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at);\n        ",
    },
}


def initialize_database(db_path: str) -> Tuple[DatabaseManager, MigrationManager]:
    """Initialize database with migrations"""
    db_manager = DatabaseManager(db_path)
    migration_manager = MigrationManager(db_manager)
    for version, migration in INITIAL_MIGRATIONS.items():
        migration_manager.apply_migration(
            version, migration["description"], migration["sql"]
        )
    return (db_manager, migration_manager)
