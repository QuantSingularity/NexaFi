import json
from typing import Any, Dict, Optional


class BaseModel:
    """Base model with database operations - delegates to shared BaseModel"""

    table_name = None
    db_manager = None

    def __init__(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def find_by_id(cls, id_value: object) -> object:
        """Find record by ID - delegates to actual shared BaseModel if available"""
        # Import actual BaseModel from shared if available
        try:
            import os
            import sys

            sys.path.insert(
                0,
                os.path.join(
                    os.path.dirname(__file__),
                    "..",
                    "..",
                    "..",
                    "..",
                    "backend",
                    "shared",
                ),
            )
            from database.manager import BaseModel as SharedBaseModel

            return (
                SharedBaseModel.find_by_id(id_value)
                if hasattr(SharedBaseModel, "find_by_id")
                else None
            )
        except (ImportError, AttributeError):
            return None

    @classmethod
    def find_all(cls, where_clause: str = "", params: tuple = ()) -> object:
        """Find all records - delegates to actual shared BaseModel if available"""
        try:
            import os
            import sys

            sys.path.insert(
                0,
                os.path.join(
                    os.path.dirname(__file__),
                    "..",
                    "..",
                    "..",
                    "..",
                    "backend",
                    "shared",
                ),
            )
            from database.manager import BaseModel as SharedBaseModel

            return (
                SharedBaseModel.find_all(where_clause, params)
                if hasattr(SharedBaseModel, "find_all")
                else []
            )
        except (ImportError, AttributeError):
            return []

    @classmethod
    def find_one(cls, where_clause: str, params: tuple = ()) -> object:
        """Find one record - delegates to actual shared BaseModel if available"""
        try:
            import os
            import sys

            sys.path.insert(
                0,
                os.path.join(
                    os.path.dirname(__file__),
                    "..",
                    "..",
                    "..",
                    "..",
                    "backend",
                    "shared",
                ),
            )
            from database.manager import BaseModel as SharedBaseModel

            return (
                SharedBaseModel.find_one(where_clause, params)
                if hasattr(SharedBaseModel, "find_one")
                else None
            )
        except (ImportError, AttributeError):
            return None

    def save(self) -> None:
        """Save record - delegates to actual shared BaseModel if available"""
        try:
            import os
            import sys

            sys.path.insert(
                0,
                os.path.join(
                    os.path.dirname(__file__),
                    "..",
                    "..",
                    "..",
                    "..",
                    "backend",
                    "shared",
                ),
            )
            from database.manager import BaseModel as SharedBaseModel

            if hasattr(SharedBaseModel, "save"):
                SharedBaseModel.save(self)
        except (ImportError, AttributeError):
            pass

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


class AIModel(BaseModel):
    table_name: Optional[str] = "ai_models"

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        for key in ["model_config", "training_data_info", "performance_metrics"]:
            if key in data and isinstance(data[key], str):
                try:
                    data[key] = json.loads(data[key])
                except json.JSONDecodeError:
                    pass
        return data


class AIPrediction(BaseModel):
    table_name: Optional[str] = "ai_predictions"

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        for key in ["input_data", "prediction_result", "explanation"]:
            if key in data and isinstance(data[key], str):
                try:
                    data[key] = json.loads(data[key])
                except json.JSONDecodeError:
                    pass
        if "confidence_score" in data and data["confidence_score"] is not None:
            data["confidence_score"] = float(data["confidence_score"])
        return data


class FinancialInsight(BaseModel):
    table_name: Optional[str] = "financial_insights"

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        for key in ["data_points", "recommendations"]:
            if key in data and isinstance(data[key], str):
                try:
                    data[key] = json.loads(data[key])
                except json.JSONDecodeError:
                    pass
        return data


class ConversationSession(BaseModel):
    table_name: Optional[str] = "conversation_sessions"

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        if "context" in data and isinstance(data["context"], str):
            try:
                data["context"] = json.loads(data["context"])
            except json.JSONDecodeError:
                pass
        data.pop("messages", None)
        return data


class ConversationMessage(BaseModel):
    table_name: Optional[str] = "conversation_messages"

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        if "metadata" in data and isinstance(data["metadata"], str):
            try:
                data["metadata"] = json.loads(data["metadata"])
            except json.JSONDecodeError:
                pass
        return data


class FeatureStore(BaseModel):
    table_name: Optional[str] = "feature_store"

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        if "feature_value" in data and isinstance(data["feature_value"], str):
            try:
                data["feature_value"] = json.loads(data["feature_value"])
            except json.JSONDecodeError:
                pass
        if "data_sources" in data and isinstance(data["data_sources"], str):
            try:
                data["data_sources"] = json.loads(data["data_sources"])
            except json.JSONDecodeError:
                pass
        return data


class ModelTrainingJob(BaseModel):
    table_name: Optional[str] = "model_training_jobs"

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        for key in ["training_config", "dataset_info", "metrics"]:
            if key in data and isinstance(data[key], str):
                try:
                    data[key] = json.loads(data[key])
                except json.JSONDecodeError:
                    pass
        return data
