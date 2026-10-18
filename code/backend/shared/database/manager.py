import json
import logging
import os
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Iterator, List, Optional, Tuple

try:
    import fcntl
except ImportError:
    fcntl = None

logger = logging.getLogger(__name__)


@contextmanager
def _process_lock(path: str) -> Iterator[None]:
    if fcntl is None:
        yield
        return
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    handle = open(path, "a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _is_busy_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "locked" in message or "busy" in message


class DatabaseManager:

    BUSY_TIMEOUT_SECONDS = 30.0
    WAL_ATTEMPTS = 20

    def __init__(self, db_path: str, pool_size: int = 10) -> None:
        self.db_path = db_path
        self.pool_size = pool_size
        self.connections: List[sqlite3.Connection] = []
        self.lock = threading.Lock()
        directory = os.path.dirname(db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with _process_lock(f"{db_path}.init.lock"):
            self._enable_wal()
        self._initialize_pool()

    def _enable_wal(self) -> None:
        delay = 0.05
        for attempt in range(self.WAL_ATTEMPTS):
            conn = sqlite3.connect(
                self.db_path,
                timeout=self.BUSY_TIMEOUT_SECONDS,
                isolation_level=None,
            )
            try:
                current = conn.execute("PRAGMA journal_mode").fetchone()[0]
                if str(current).lower() == "wal":
                    return
                conn.execute("PRAGMA journal_mode = WAL")
                return
            except sqlite3.OperationalError as exc:
                if not _is_busy_error(exc) or attempt == self.WAL_ATTEMPTS - 1:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 2.0)
            finally:
                conn.close()

    def _initialize_pool(self) -> None:
        for _ in range(self.pool_size):
            self.connections.append(self._create_connection())

    def _create_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=self.BUSY_TIMEOUT_SECONDS,
            isolation_level=None,
        )
        conn.execute(f"PRAGMA busy_timeout = {int(self.BUSY_TIMEOUT_SECONDS * 1000)}")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def get_connection(self) -> Iterator[sqlite3.Connection]:
        conn = None
        try:
            with self.lock:
                if self.connections:
                    conn = self.connections.pop()
            if conn is None:
                conn = self._create_connection()
            yield conn
        finally:
            if conn is not None:
                try:
                    if conn.in_transaction:
                        conn.rollback()
                except sqlite3.Error:
                    try:
                        conn.close()
                    except sqlite3.Error:
                        pass
                    conn = None
            if conn is not None:
                with self.lock:
                    if len(self.connections) < self.pool_size:
                        self.connections.append(conn)
                        conn = None
                if conn is not None:
                    conn.close()

    @contextmanager
    def transaction(self, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        with self.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            try:
                yield conn
                conn.commit()
            except BaseException:
                if conn.in_transaction:
                    conn.rollback()
                raise

    def execute_query(self, query: str, params: Tuple = ()) -> Any:
        with self.get_connection() as conn:
            if not params and self._is_script(query):
                conn.executescript(query)
                return []
            cursor = conn.execute(query, params)
            q = query.strip().upper()
            if q.startswith(("SELECT", "WITH", "PRAGMA")):
                return cursor.fetchall()
            return cursor

    @staticmethod
    def _is_script(query: str) -> bool:
        statements = [part for part in query.split(";") if part.strip()]
        return len(statements) > 1 and sqlite3.complete_statement(query.strip())

    def fetch_all(self, query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def fetch_one(self, query: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def execute_update(self, query: str, params: Tuple = ()) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.rowcount

    def execute_insert(self, query: str, params: Tuple = ()) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.lastrowid

    def close_all_connections(self) -> None:
        with self.lock:
            for conn in self.connections:
                conn.close()
            self.connections.clear()


class MigrationManager:

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager
        self.migrations_table = "schema_migrations"
        self._ensure_migrations_table()

    def _ensure_migrations_table(self) -> None:
        query = (
            f"CREATE TABLE IF NOT EXISTS {self.migrations_table} ("
            "version TEXT PRIMARY KEY, "
            "applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "description TEXT)"
        )
        self.db_manager.execute_update(query)

    def get_applied_migrations(self) -> List[str]:
        query = f"SELECT version FROM {self.migrations_table} ORDER BY version"
        rows = self.db_manager.execute_query(query)
        return [row["version"] for row in rows]

    def apply_migration(self, version: str, description: str, sql: str) -> None:
        if version in self.get_applied_migrations():
            logger.info(f"Migration {version} already applied")
            return
        with self.db_manager.transaction(immediate=True) as conn:
            already = conn.execute(
                f"SELECT 1 FROM {self.migrations_table} WHERE version = ?", (version,)
            ).fetchone()
            if already:
                logger.info(f"Migration {version} already applied by another process")
                return
            logger.info(f"Applying migration {version}: {description}")
            for statement in sql.split(";"):
                statement = statement.strip()
                if statement:
                    conn.execute(statement)
            conn.execute(
                f"INSERT OR IGNORE INTO {self.migrations_table} (version, description) VALUES (?, ?)",
                (version, description),
            )
        logger.info(f"Migration {version} applied successfully")

    def rollback_migration(self, version: str, rollback_sql: str) -> None:
        applied_migrations = self.get_applied_migrations()
        if version not in applied_migrations:
            logger.info(f"Migration {version} not applied")
            return
        logger.info(f"Rolling back migration {version}")
        with self.db_manager.transaction(immediate=True) as conn:
            for statement in rollback_sql.split(";"):
                statement = statement.strip()
                if statement:
                    conn.execute(statement)
            conn.execute(
                f"DELETE FROM {self.migrations_table} WHERE version = ?", (version,)
            )
        logger.info(f"Migration {version} rolled back successfully")


class BaseModel:

    table_name = None
    db_manager = None
    _schema_cache: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    _ORDER_PATTERN = re.compile(
        r"^[A-Za-z_][A-Za-z0-9_\.]*(\s+(ASC|DESC))?(\s*,\s*[A-Za-z_][A-Za-z0-9_\.]*(\s+(ASC|DESC))?)*$",
        re.IGNORECASE,
    )

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)
        for column in self._column_names():
            if not hasattr(self, column):
                setattr(self, column, None)

    @classmethod
    def set_db_manager(cls, db_manager: DatabaseManager) -> None:
        cls.db_manager = db_manager
        BaseModel._schema_cache = {}

    @classmethod
    def _table_info(cls) -> List[Dict[str, Any]]:
        if not cls.table_name or cls.db_manager is None:
            return []
        key = (cls.db_manager.db_path, cls.table_name)
        cached = BaseModel._schema_cache.get(key)
        if cached is not None:
            return cached
        try:
            rows = cls.db_manager.fetch_all(f"PRAGMA table_info({cls.table_name})")
        except Exception:
            rows = []
        if rows:
            BaseModel._schema_cache[key] = rows
        return rows

    @classmethod
    def _column_names(cls) -> List[str]:
        return [row["name"] for row in cls._table_info()]

    @staticmethod
    def _adapt(value: Any) -> Any:
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, default=str)
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return value

    @classmethod
    def _validate_order(cls, order_by: str) -> str:
        if not cls._ORDER_PATTERN.match(order_by.strip()):
            raise ValueError(f"Invalid order_by clause: {order_by}")
        return order_by.strip()

    @classmethod
    def find_by_id(cls, id_value: Any) -> Optional["BaseModel"]:
        query = f"SELECT * FROM {cls.table_name} WHERE id = ?"
        rows = cls.db_manager.execute_query(query, (id_value,))
        if rows:
            return cls(**dict(rows[0]))
        return None

    @classmethod
    def find_all(
        cls,
        where_clause: str = "",
        params: Tuple = (),
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List["BaseModel"]:
        query = f"SELECT * FROM {cls.table_name}"
        if where_clause:
            query += f" WHERE {where_clause}"
        if order_by:
            query += f" ORDER BY {cls._validate_order(order_by)}"
        values = list(params)
        if limit is not None:
            query += " LIMIT ?"
            values.append(int(limit))
        elif offset:
            query += " LIMIT -1"
        if offset:
            query += " OFFSET ?"
            values.append(int(offset))
        rows = cls.db_manager.execute_query(query, tuple(values))
        return [cls(**dict(row)) for row in rows]

    @classmethod
    def find_one(cls, where_clause: str, params: Tuple = ()) -> Optional["BaseModel"]:
        query = f"SELECT * FROM {cls.table_name} WHERE {where_clause} LIMIT 1"
        rows = cls.db_manager.execute_query(query, params)
        if rows:
            return cls(**dict(rows[0]))
        return None

    @classmethod
    def count(cls, where_clause: str = "", params: Tuple = ()) -> int:
        query = f"SELECT COUNT(*) AS total FROM {cls.table_name}"
        if where_clause:
            query += f" WHERE {where_clause}"
        rows = cls.db_manager.execute_query(query, params)
        return int(rows[0]["total"]) if rows else 0

    def _exists(self) -> bool:
        row = self.db_manager.fetch_one(
            f"SELECT 1 AS present FROM {self.table_name} WHERE id = ?", (self.id,)
        )
        return row is not None

    def save(self) -> "BaseModel":
        if getattr(self, "id", None) and self._exists():
            return self._update()
        return self._insert()

    def _persisted_fields(self, skip_none: bool) -> List[str]:
        columns = self._column_names()
        if columns:
            names = [c for c in columns if c != "id" and hasattr(self, c)]
        else:
            names = [
                k for k in self.__dict__.keys() if k != "id" and not k.startswith("_")
            ]
        if skip_none:
            names = [n for n in names if getattr(self, n) is not None]
        return names

    def _text_primary_key(self) -> bool:
        for row in self._table_info():
            if row["name"] == "id":
                return "INT" not in str(row["type"]).upper()
        return False

    def _insert(self) -> "BaseModel":
        fields = self._persisted_fields(skip_none=True)
        generated = None
        if getattr(self, "id", None):
            fields = ["id"] + fields
            generated = self.id
        elif self._text_primary_key():
            generated = str(uuid.uuid4())
            fields = ["id"] + fields
            self.id = generated
        values = [self._adapt(getattr(self, k)) for k in fields]
        placeholders = ", ".join(["?" for _ in fields])
        field_names = ", ".join(fields)
        query = f"INSERT INTO {self.table_name} ({field_names}) VALUES ({placeholders})"
        row_id = self.db_manager.execute_insert(query, tuple(values))
        if generated is None:
            self.id = row_id
        self._store_adapted(fields, values)
        self._refresh()
        return self

    def _refresh(self) -> None:
        row = self.db_manager.fetch_one(
            f"SELECT * FROM {self.table_name} WHERE id = ?", (self.id,)
        )
        if not row:
            return
        for key, value in row.items():
            if getattr(self, key, None) is None:
                setattr(self, key, value)

    def _update(self) -> "BaseModel":
        fields = self._persisted_fields(skip_none=False)
        if not fields:
            return self
        values = [self._adapt(getattr(self, k)) for k in fields]
        set_clause = ", ".join([f"{field} = ?" for field in fields])
        query = f"UPDATE {self.table_name} SET {set_clause} WHERE id = ?"
        values.append(self.id)
        self.db_manager.execute_update(query, tuple(values))
        self._store_adapted(fields, values[:-1])
        return self

    def _store_adapted(self, fields: List[str], values: List[Any]) -> None:
        for name, adapted in zip(fields, values):
            if isinstance(getattr(self, name, None), (dict, list, tuple)):
                setattr(self, name, adapted)

    def delete(self) -> None:
        if getattr(self, "id", None):
            query = f"DELETE FROM {self.table_name} WHERE id = ?"
            self.db_manager.execute_update(query, (self.id,))

    def to_dict(self) -> Dict[str, Any]:
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
    db_manager = DatabaseManager(db_path)
    with _process_lock(f"{db_path}.migrate.lock"):
        migration_manager = MigrationManager(db_manager)
        for version, migration in INITIAL_MIGRATIONS.items():
            migration_manager.apply_migration(
                version, migration["description"], migration["sql"]
            )
    return (db_manager, migration_manager)
