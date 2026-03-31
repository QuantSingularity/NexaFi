import json
from datetime import datetime
from typing import Any, Dict, Optional


class BaseModel:
    """Base model with database operations - delegates to shared BaseModel"""

    table_name = None
    db_manager = None

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def find_by_id(cls: Any, id_value: Any) -> Any:
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
    def find_all(cls: Any, where_clause: str = "", params: tuple = ()) -> Any:
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
    def find_one(cls: Any, where_clause: str, params: tuple = ()) -> Any:
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

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


class Dashboard(BaseModel):
    table_name: Optional[str] = "dashboards"

    def get_layout(self) -> Any:
        return json.loads(self.layout) if self.layout else {}

    def set_layout(self, layout: Any) -> Any:
        self.layout = json.dumps(layout)

    def get_filters(self) -> Any:
        return json.loads(self.filters) if self.filters else {}

    def set_filters(self, filters: Any) -> Any:
        self.filters = json.dumps(filters)

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["layout"] = self.get_layout()
        data["filters"] = self.get_filters()
        return data


class Report(BaseModel):
    table_name: Optional[str] = "reports"

    def get_parameters(self) -> Any:
        return json.loads(self.parameters) if self.parameters else {}

    def set_parameters(self, params: Any) -> Any:
        self.parameters = json.dumps(params)

    def get_schedule_config(self) -> Any:
        return json.loads(self.schedule_config) if self.schedule_config else {}

    def set_schedule_config(self, config: Any) -> Any:
        self.schedule_config = json.dumps(config)

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["parameters"] = self.get_parameters()
        data["schedule_config"] = self.get_schedule_config()
        return data


class ReportExecution(BaseModel):
    table_name: Optional[str] = "report_executions"

    def get_result_data(self) -> Any:
        return json.loads(self.result_data) if self.result_data else None

    def set_result_data(self, data: Any) -> Any:
        self.result_data = json.dumps(data)

    def get_parameters_used(self) -> Any:
        return json.loads(self.parameters_used) if self.parameters_used else {}

    def set_parameters_used(self, params: Any) -> Any:
        self.parameters_used = json.dumps(params)

    def mark_completed(self, result_data: Any = None, row_count: Any = None) -> Any:
        self.status = "completed"
        self.completed_at = datetime.utcnow()
        if result_data:
            self.set_result_data(result_data)
        if row_count is not None:
            self.row_count = row_count
        if self.started_at:
            started_at_dt = (
                datetime.fromisoformat(self.started_at)
                if isinstance(self.started_at, str)
                else self.started_at
            )
            self.execution_time = (self.completed_at - started_at_dt).total_seconds()

    def mark_failed(self, error_message: Any) -> Any:
        self.status = "failed"
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
        if self.started_at:
            started_at_dt = (
                datetime.fromisoformat(self.started_at)
                if isinstance(self.started_at, str)
                else self.started_at
            )
            self.execution_time = (self.completed_at - started_at_dt).total_seconds()

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["parameters_used"] = self.get_parameters_used()
        for key in ["started_at", "completed_at", "created_at"]:
            if key in data and data[key] and isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        return data


class DataSource(BaseModel):
    table_name: Optional[str] = "data_sources"

    def get_connection_config(self) -> Any:
        return json.loads(self.connection_config) if self.connection_config else {}

    def set_connection_config(self, config: Any) -> Any:
        self.connection_config = json.dumps(config)

    def get_authentication(self) -> Any:
        return json.loads(self.authentication) if self.authentication else {}

    def set_authentication(self, auth: Any) -> Any:
        self.authentication = json.dumps(auth)

    def get_schema_config(self) -> Any:
        return json.loads(self.schema_config) if self.schema_config else {}

    def set_schema_config(self, schema: Any) -> Any:
        self.schema_config = json.dumps(schema)

    def get_sample_data(self) -> Any:
        return json.loads(self.sample_data) if self.sample_data else None

    def set_sample_data(self, data: Any) -> Any:
        self.sample_data = json.dumps(data)

    def to_dict(self, include_sensitive: Any = False) -> Any:
        data = super().to_dict()
        data["schema_config"] = self.get_schema_config()
        data["sample_data"] = self.get_sample_data()
        if include_sensitive:
            data["connection_config"] = self.get_connection_config()
            data["authentication"] = self.get_authentication()
        for key in ["last_tested", "created_at", "updated_at"]:
            if key in data and data[key] and isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        return data


class Metric(BaseModel):
    table_name: Optional[str] = "metrics"

    def get_format_config(self) -> Any:
        return json.loads(self.format_config) if self.format_config else {}

    def set_format_config(self, config: Any) -> Any:
        self.format_config = json.dumps(config)

    def calculate_change(self) -> Any:
        """Calculate percentage change from previous value"""
        if self.previous_value and self.previous_value != 0:
            return (
                (self.current_value - self.previous_value) / self.previous_value * 100
            )
        return 0

    def update_status(self) -> Any:
        """Update status based on thresholds"""
        if self.current_value is None:
            self.status = "unknown"
        elif self.critical_threshold and self.current_value <= self.critical_threshold:
            self.status = "critical"
        elif self.warning_threshold and self.current_value <= self.warning_threshold:
            self.status = "warning"
        else:
            self.status = "normal"

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["format_config"] = self.get_format_config()
        data["change_percentage"] = self.calculate_change()
        for key in ["last_calculated", "created_at", "updated_at"]:
            if key in data and data[key] and isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        return data


class MetricHistory(BaseModel):
    table_name: Optional[str] = "metric_history"

    def get_calculation_details(self) -> Any:
        return json.loads(self.calculation_details) if self.calculation_details else {}

    def set_calculation_details(self, details: Any) -> Any:
        self.calculation_details = json.dumps(details)

    def to_dict(self) -> Any:
        data = super().to_dict()
        data["calculation_details"] = self.get_calculation_details()
        if (
            "timestamp" in data
            and data["timestamp"]
            and isinstance(data["timestamp"], datetime)
        ):
            data["timestamp"] = data["timestamp"].isoformat()
        return data
