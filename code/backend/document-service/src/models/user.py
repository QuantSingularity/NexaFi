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
                0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared")
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
                0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared")
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
                0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared")
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
                0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared")
            )
            from database.manager import BaseModel as SharedBaseModel

            if hasattr(SharedBaseModel, "save"):
                SharedBaseModel.save(self)
        except (ImportError, AttributeError):
            pass

    def delete(self) -> object:
        pass

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


class Document(BaseModel):
    table_name: Optional[str] = "documents"

    def get_metadata(self) -> object:
        return json.loads(self.metadata) if self.metadata else {}

    def set_metadata(self, metadata: object) -> object:
        self.metadata = json.dumps(metadata)

    def get_extracted_data(self) -> object:
        return json.loads(self.extracted_data) if self.extracted_data else {}

    def set_extracted_data(self, data: object) -> object:
        self.extracted_data = json.dumps(data)

    def to_dict(self) -> object:
        data = super().to_dict()
        data["metadata"] = self.get_metadata()
        data["extracted_data"] = self.get_extracted_data()
        return data


class DocumentTemplate(BaseModel):
    table_name: Optional[str] = "document_templates"

    def get_fields(self) -> object:
        return json.loads(self.fields) if self.fields else []

    def set_fields(self, fields: object) -> object:
        self.fields = json.dumps(fields)

    def get_metadata(self) -> object:
        return json.loads(self.metadata) if self.metadata else {}

    def set_metadata(self, metadata: object) -> object:
        self.metadata = json.dumps(metadata)

    def to_dict(self) -> object:
        data = super().to_dict()
        data["fields"] = self.get_fields()
        data["metadata"] = self.get_metadata()
        return data


class DocumentShare(BaseModel):
    table_name: Optional[str] = "document_shares"

    def to_dict(self) -> object:
        return super().to_dict()


class DocumentVersion(BaseModel):
    table_name: Optional[str] = "document_versions"

    def to_dict(self) -> object:
        return super().to_dict()
