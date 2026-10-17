import json
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "shared"))
from database.manager import BaseModel


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
