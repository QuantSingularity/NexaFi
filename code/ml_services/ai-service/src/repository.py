import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ai_models.core.errors import NotFoundError
from database.manager import DatabaseManager


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads(value: Any) -> Any:
    if isinstance(value, str) and value:
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _dumps(value: Any) -> Optional[str]:
    return None if value is None else json.dumps(value, default=str)


def _paged(page: int, per_page: int) -> Tuple[int, int]:
    per_page = max(1, min(int(per_page), 100))
    page = max(1, int(page))
    return per_page, (page - 1) * per_page


class Repository:
    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def _rows(self, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        return [dict(r) for r in self.db.execute_query(sql, params)]

    def healthy(self) -> bool:
        try:
            self.db.execute_query("SELECT 1")
            return True
        except Exception:
            return False

    def record_prediction(
        self,
        user_id: str,
        model_name: str,
        prediction_type: str,
        input_data: Any,
        result: Any,
        confidence: Optional[float],
        explanation: Any,
        latency_ms: int,
    ) -> str:
        prediction_id = str(uuid.uuid4())
        self.db.execute_update(
            "INSERT INTO ai_predictions (id, user_id, model_id, prediction_type, input_data, prediction_result, "
            "confidence_score, explanation, status, execution_time_ms, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                prediction_id,
                user_id,
                model_name,
                prediction_type,
                _dumps(input_data),
                _dumps(result),
                confidence,
                _dumps(explanation),
                "completed",
                latency_ms,
                _now(),
            ),
        )
        return prediction_id

    @staticmethod
    def _prediction(row: Dict[str, Any]) -> Dict[str, Any]:
        for key in ("input_data", "prediction_result", "explanation"):
            row[key] = _loads(row.get(key))
        return row

    def list_predictions(
        self, user_id: str, prediction_type: Optional[str], page: int, per_page: int
    ) -> Dict[str, Any]:
        per_page, offset = _paged(page, per_page)
        where, params = "user_id = ?", [user_id]
        if prediction_type:
            where += " AND prediction_type = ?"
            params.append(prediction_type)
        total = self._rows(
            f"SELECT COUNT(*) AS n FROM ai_predictions WHERE {where}", tuple(params)
        )[0]["n"]
        rows = self._rows(
            f"SELECT * FROM ai_predictions WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            tuple(params + [per_page, offset]),
        )
        return {
            "predictions": [self._prediction(r) for r in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    def get_prediction(self, user_id: str, prediction_id: str) -> Dict[str, Any]:
        rows = self._rows(
            "SELECT * FROM ai_predictions WHERE id = ? AND user_id = ?",
            (prediction_id, user_id),
        )
        if not rows:
            raise NotFoundError("Prediction not found")
        return self._prediction(rows[0])

    def recent_inputs(
        self, prediction_type: str, limit: int = 500
    ) -> List[Dict[str, Any]]:
        rows = self._rows(
            "SELECT input_data FROM ai_predictions WHERE prediction_type = ? ORDER BY created_at DESC LIMIT ?",
            (prediction_type, limit),
        )
        return [
            i for i in (_loads(r["input_data"]) for r in rows) if isinstance(i, dict)
        ]

    def save_insights(
        self, user_id: str, insights: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        saved = []
        for item in insights:
            insight_id = str(uuid.uuid4())
            self.db.execute_update(
                "INSERT INTO financial_insights (id, user_id, insight_type, title, description, severity, category, "
                "data_points, recommendations, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    insight_id,
                    user_id,
                    item["insight_type"],
                    item["title"],
                    item["description"],
                    item["severity"],
                    item.get("category"),
                    _dumps(item.get("evidence")),
                    _dumps(item.get("recommendations")),
                    _now(),
                    _now(),
                ),
            )
            saved.append(
                {**item, "id": insight_id, "is_read": False, "is_dismissed": False}
            )
        return saved

    @staticmethod
    def _insight(row: Dict[str, Any]) -> Dict[str, Any]:
        row["evidence"] = _loads(row.pop("data_points", None))
        row["recommendations"] = _loads(row.get("recommendations")) or []
        row["is_read"] = bool(row.get("is_read"))
        row["is_dismissed"] = bool(row.get("is_dismissed"))
        return row

    def list_insights(
        self,
        user_id: str,
        severity: Optional[str],
        unread_only: bool,
        page: int,
        per_page: int,
    ) -> Dict[str, Any]:
        per_page, offset = _paged(page, per_page)
        where, params = "user_id = ? AND is_dismissed = 0", [user_id]
        if severity:
            where += " AND severity = ?"
            params.append(severity)
        if unread_only:
            where += " AND is_read = 0"
        total = self._rows(
            f"SELECT COUNT(*) AS n FROM financial_insights WHERE {where}", tuple(params)
        )[0]["n"]
        rows = self._rows(
            f"SELECT * FROM financial_insights WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            tuple(params + [per_page, offset]),
        )
        return {
            "insights": [self._insight(r) for r in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    def update_insight(
        self, user_id: str, insight_id: str, changes: Dict[str, Any]
    ) -> Dict[str, Any]:
        rows = self._rows(
            "SELECT * FROM financial_insights WHERE id = ? AND user_id = ?",
            (insight_id, user_id),
        )
        if not rows:
            raise NotFoundError("Insight not found")
        fields = {
            k: int(bool(v))
            for k, v in changes.items()
            if k in ("is_read", "is_dismissed")
        }
        if fields:
            sets = ", ".join(f"{k} = ?" for k in fields)
            self.db.execute_update(
                f"UPDATE financial_insights SET {sets}, updated_at = ? WHERE id = ?",
                tuple(fields.values()) + (_now(), insight_id),
            )
        return self._insight(
            self._rows("SELECT * FROM financial_insights WHERE id = ?", (insight_id,))[
                0
            ]
        )

    def create_session(
        self, user_id: str, name: Optional[str], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        session_id = str(uuid.uuid4())
        self.db.execute_update(
            "INSERT INTO conversation_sessions (id, user_id, session_name, context, created_at, updated_at, last_activity_at) VALUES (?,?,?,?,?,?,?)",
            (
                session_id,
                user_id,
                name or "New conversation",
                _dumps(context),
                _now(),
                _now(),
                _now(),
            ),
        )
        return self.get_session(user_id, session_id)

    def get_session(self, user_id: str, session_id: str) -> Dict[str, Any]:
        rows = self._rows(
            "SELECT * FROM conversation_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )
        if not rows:
            raise NotFoundError("Session not found")
        row = rows[0]
        row["context"] = _loads(row.get("context")) or {}
        row["is_active"] = bool(row.get("is_active"))
        return row

    def list_sessions(self, user_id: str, page: int, per_page: int) -> Dict[str, Any]:
        per_page, offset = _paged(page, per_page)
        total = self._rows(
            "SELECT COUNT(*) AS n FROM conversation_sessions WHERE user_id = ? AND is_active = 1",
            (user_id,),
        )[0]["n"]
        rows = self._rows(
            "SELECT id, session_name, last_activity_at, created_at FROM conversation_sessions WHERE user_id = ? AND is_active = 1 "
            "ORDER BY last_activity_at DESC LIMIT ? OFFSET ?",
            (user_id, per_page, offset),
        )
        return {"sessions": rows, "total": total, "page": page, "per_page": per_page}

    def close_session(self, user_id: str, session_id: str) -> None:
        self.get_session(user_id, session_id)
        self.db.execute_update(
            "UPDATE conversation_sessions SET is_active = 0, updated_at = ? WHERE id = ?",
            (_now(), session_id),
        )

    def update_session_context(self, session_id: str, context: Dict[str, Any]) -> None:
        self.db.execute_update(
            "UPDATE conversation_sessions SET context = ?, last_activity_at = ?, updated_at = ? WHERE id = ?",
            (_dumps(context), _now(), _now(), session_id),
        )

    def add_message(
        self,
        session_id: str,
        message_type: str,
        content: str,
        metadata: Any,
        processing_ms: Optional[int],
    ) -> Dict[str, Any]:
        message_id = str(uuid.uuid4())
        created = _now()
        self.db.execute_update(
            "INSERT INTO conversation_messages (id, session_id, message_type, content, metadata, processing_time_ms, created_at) VALUES (?,?,?,?,?,?,?)",
            (
                message_id,
                session_id,
                message_type,
                content,
                _dumps(metadata),
                processing_ms,
                created,
            ),
        )
        return {
            "id": message_id,
            "session_id": session_id,
            "message_type": message_type,
            "content": content,
            "metadata": metadata,
            "created_at": created,
        }

    def list_messages(self, session_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        rows = self._rows(
            "SELECT * FROM conversation_messages WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
            (session_id, limit),
        )
        for row in rows:
            row["metadata"] = _loads(row.get("metadata"))
        return rows

    def upsert_model(
        self,
        name: str,
        model_type: str,
        version: str,
        description: str,
        config: Any,
        metrics: Any,
        training_info: Any,
    ) -> None:
        with self.db.transaction(immediate=True) as conn:
            existing = conn.execute(
                "SELECT id FROM ai_models WHERE name = ?", (name,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE ai_models SET model_type = ?, version = ?, description = ?, model_config = ?, "
                    "training_data_info = ?, performance_metrics = ?, updated_at = ? WHERE name = ?",
                    (
                        model_type,
                        version,
                        description,
                        _dumps(config),
                        _dumps(training_info),
                        _dumps(metrics),
                        _now(),
                        name,
                    ),
                )
                return
            conn.execute(
                "INSERT INTO ai_models (id, name, model_type, version, description, model_config, "
                "training_data_info, performance_metrics, is_active, is_production, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,1,0,?,?)",
                (
                    str(uuid.uuid4()),
                    name,
                    model_type,
                    version,
                    description,
                    _dumps(config),
                    _dumps(training_info),
                    _dumps(metrics),
                    _now(),
                    _now(),
                ),
            )
