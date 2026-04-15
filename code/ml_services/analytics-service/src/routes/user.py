import uuid
from datetime import datetime
from functools import wraps
from typing import Any

from flask import Blueprint, jsonify, request
from models.user import (
    Dashboard,
    DataSource,
    Metric,
    MetricHistory,
    Report,
    ReportExecution,
)

analytics_bp = Blueprint("analytics", __name__)


def require_user_id(f: Any) -> Any:
    """Decorator to extract user_id from request headers"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return (jsonify({"error": "User ID is required in headers"}), 401)
        request.user_id = user_id
        return f(*args, **kwargs)

    return decorated_function


@analytics_bp.route("/dashboards", methods=["GET"])
@require_user_id
def get_dashboards() -> Any:
    """Get all dashboards for the current user."""
    try:
        dashboards = Dashboard.find_all("user_id = ?", (request.user_id,))
        return (jsonify([d.to_dict() for d in dashboards]), 200)
    except Exception as e:
        return (
            jsonify({"error": "Failed to fetch dashboards", "details": str(e)}),
            500,
        )


@analytics_bp.route("/dashboards", methods=["POST"])
@require_user_id
def create_dashboard() -> Any:
    """Create a new dashboard."""
    try:
        data = request.get_json()
        new_dashboard = Dashboard(
            id=str(uuid.uuid4()),
            user_id=request.user_id,
            name=data["name"],
            description=data.get("description"),
            layout=data.get("layout", "{}"),
            filters=data.get("filters", "{}"),
            is_public=data.get("is_public", False),
            is_active=True,
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        new_dashboard.save()
        return (jsonify(new_dashboard.to_dict()), 201)
    except Exception as e:
        return (
            jsonify({"error": "Failed to create dashboard", "details": str(e)}),
            400,
        )


@analytics_bp.route("/dashboards/<dashboard_id>", methods=["GET"])
@require_user_id
def get_dashboard(dashboard_id: Any) -> Any:
    """Get a specific dashboard by ID."""
    dashboard = Dashboard.find_one(
        "id = ? AND user_id = ?", (dashboard_id, request.user_id)
    )
    if not dashboard:
        return (jsonify({"error": "Dashboard not found"}), 404)
    return (jsonify(dashboard.to_dict()), 200)


@analytics_bp.route("/dashboards/<dashboard_id>", methods=["PUT"])
@require_user_id
def update_dashboard(dashboard_id: Any) -> Any:
    """Update an existing dashboard."""
    try:
        dashboard = Dashboard.find_one(
            "id = ? AND user_id = ?", (dashboard_id, request.user_id)
        )
        if not dashboard:
            return (jsonify({"error": "Dashboard not found"}), 404)
        data = request.get_json()
        dashboard.name = data.get("name", dashboard.name)
        dashboard.description = data.get("description", dashboard.description)
        dashboard.set_layout(data.get("layout", dashboard.get_layout()))
        dashboard.set_filters(data.get("filters", dashboard.get_filters()))
        dashboard.is_public = data.get("is_public", dashboard.is_public)
        dashboard.is_active = data.get("is_active", dashboard.is_active)
        dashboard.updated_at = datetime.utcnow().isoformat()
        dashboard.save()
        return (jsonify(dashboard.to_dict()), 200)
    except Exception as e:
        return (
            jsonify({"error": "Failed to update dashboard", "details": str(e)}),
            400,
        )


@analytics_bp.route("/dashboards/<dashboard_id>", methods=["DELETE"])
@require_user_id
def delete_dashboard(dashboard_id: Any) -> Any:
    """Delete a dashboard."""
    try:
        dashboard = Dashboard.find_one(
            "id = ? AND user_id = ?", (dashboard_id, request.user_id)
        )
        if not dashboard:
            return (jsonify({"error": "Dashboard not found"}), 404)
        dashboard.delete()
        return (jsonify({"message": "Dashboard deleted successfully"}), 204)
    except Exception as e:
        return (
            jsonify({"error": "Failed to delete dashboard", "details": str(e)}),
            500,
        )


@analytics_bp.route("/reports", methods=["GET"])
@require_user_id
def get_reports() -> Any:
    """Get all reports for the current user."""
    try:
        reports = Report.find_all("user_id = ?", (request.user_id,))
        return (jsonify([r.to_dict() for r in reports]), 200)
    except Exception as e:
        return (jsonify({"error": "Failed to fetch reports", "details": str(e)}), 500)


@analytics_bp.route("/reports", methods=["POST"])
@require_user_id
def create_report() -> Any:
    """Create a new report."""
    try:
        data = request.get_json()
        new_report = Report(
            id=str(uuid.uuid4()),
            user_id=request.user_id,
            name=data["name"],
            description=data.get("description"),
            report_type=data["report_type"],
            data_source_id=data.get("data_source_id"),
            parameters=data.get("parameters", "{}"),
            schedule_config=data.get("schedule_config", "{}"),
            is_active=data.get("is_active", True),
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        new_report.save()
        return (jsonify(new_report.to_dict()), 201)
    except Exception as e:
        return (jsonify({"error": "Failed to create report", "details": str(e)}), 400)


@analytics_bp.route("/reports/<report_id>", methods=["GET"])
@require_user_id
def get_report(report_id: Any) -> Any:
    """Get a specific report by ID."""
    report = Report.find_one("id = ? AND user_id = ?", (report_id, request.user_id))
    if not report:
        return (jsonify({"error": "Report not found"}), 404)
    return (jsonify(report.to_dict()), 200)


@analytics_bp.route("/reports/<report_id>", methods=["PUT"])
@require_user_id
def update_report(report_id: Any) -> Any:
    """Update an existing report."""
    try:
        report = Report.find_one("id = ? AND user_id = ?", (report_id, request.user_id))
        if not report:
            return (jsonify({"error": "Report not found"}), 404)
        data = request.get_json()
        report.name = data.get("name", report.name)
        report.description = data.get("description", report.description)
        report.report_type = data.get("report_type", report.report_type)
        report.data_source_id = data.get("data_source_id", report.data_source_id)
        report.set_parameters(data.get("parameters", report.get_parameters()))
        report.set_schedule_config(
            data.get("schedule_config", report.get_schedule_config())
        )
        report.is_active = data.get("is_active", report.is_active)
        report.updated_at = datetime.utcnow().isoformat()
        report.save()
        return (jsonify(report.to_dict()), 200)
    except Exception as e:
        return (jsonify({"error": "Failed to update report", "details": str(e)}), 400)


@analytics_bp.route("/reports/<report_id>", methods=["DELETE"])
@require_user_id
def delete_report(report_id: Any) -> Any:
    """Delete a report."""
    try:
        report = Report.find_one("id = ? AND user_id = ?", (report_id, request.user_id))
        if not report:
            return (jsonify({"error": "Report not found"}), 404)
        report.delete()
        return (jsonify({"message": "Report deleted successfully"}), 204)
    except Exception as e:
        return (jsonify({"error": "Failed to delete report", "details": str(e)}), 500)


@analytics_bp.route("/reports/<report_id>/execute", methods=["POST"])
@require_user_id
def execute_report(report_id: Any) -> Any:
    """Execute a report (simulated)."""
    try:
        report = Report.find_one("id = ? AND user_id = ?", (report_id, request.user_id))
        if not report:
            return (jsonify({"error": "Report not found"}), 404)
        execution = ReportExecution(
            id=str(uuid.uuid4()),
            report_id=report_id,
            status="running",
            started_at=datetime.utcnow().isoformat(),
            triggered_by=request.user_id,
            parameters_used=request.get_json().get("parameters", "{}"),
        )
        execution.save()
        execution.mark_completed(
            result_data={"summary": "Simulated report data"}, row_count=100
        )
        execution.save()
        report.last_run_at = datetime.utcnow().isoformat()
        report.save()
        return (
            jsonify(
                {
                    "message": "Report execution simulated successfully",
                    "execution": execution.to_dict(),
                }
            ),
            202,
        )
    except Exception as e:
        return (jsonify({"error": "Failed to execute report", "details": str(e)}), 500)


@analytics_bp.route("/reports/<report_id>/executions", methods=["GET"])
@require_user_id
def get_report_executions(report_id: Any) -> Any:
    """Get all executions for a report."""
    try:
        report = Report.find_one("id = ? AND user_id = ?", (report_id, request.user_id))
        if not report:
            return (jsonify({"error": "Report not found"}), 404)
        executions = ReportExecution.find_all("report_id = ?", (report_id,))
        executions.sort(key=lambda x: x.created_at, reverse=True)
        return (jsonify([e.to_dict() for e in executions]), 200)
    except Exception as e:
        return (
            jsonify({"error": "Failed to fetch report executions", "details": str(e)}),
            500,
        )


@analytics_bp.route("/data-sources", methods=["GET"])
@require_user_id
def get_data_sources() -> Any:
    """Get all data sources for the current user."""
    try:
        data_sources = DataSource.find_all("user_id = ?", (request.user_id,))
        return (jsonify([d.to_dict() for d in data_sources]), 200)
    except Exception as e:
        return (
            jsonify({"error": "Failed to fetch data sources", "details": str(e)}),
            500,
        )


@analytics_bp.route("/data-sources", methods=["POST"])
@require_user_id
def create_data_source() -> Any:
    """Create a new data source."""
    try:
        data = request.get_json()
        new_source = DataSource(
            id=str(uuid.uuid4()),
            user_id=request.user_id,
            name=data["name"],
            description=data.get("description"),
            source_type=data["source_type"],
            connection_config=data.get("connection_config", "{}"),
            authentication=data.get("authentication", "{}"),
            schema_config=data.get("schema_config", "{}"),
            sample_data=data.get("sample_data", "{}"),
            is_active=data.get("is_active", True),
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        new_source.save()
        return (jsonify(new_source.to_dict()), 201)
    except Exception as e:
        return (
            jsonify({"error": "Failed to create data source", "details": str(e)}),
            400,
        )


@analytics_bp.route("/data-sources/<source_id>", methods=["GET"])
@require_user_id
def get_data_source(source_id: Any) -> Any:
    """Get a specific data source by ID."""
    data_source = DataSource.find_one(
        "id = ? AND user_id = ?", (source_id, request.user_id)
    )
    if not data_source:
        return (jsonify({"error": "Data source not found"}), 404)
    return (jsonify(data_source.to_dict(include_sensitive=True)), 200)


@analytics_bp.route("/data-sources/<source_id>", methods=["PUT"])
@require_user_id
def update_data_source(source_id: Any) -> Any:
    """Update an existing data source."""
    try:
        data_source = DataSource.find_one(
            "id = ? AND user_id = ?", (source_id, request.user_id)
        )
        if not data_source:
            return (jsonify({"error": "Data source not found"}), 404)
        data = request.get_json()
        data_source.name = data.get("name", data_source.name)
        data_source.description = data.get("description", data_source.description)
        data_source.source_type = data.get("source_type", data_source.source_type)
        data_source.set_connection_config(
            data.get("connection_config", data_source.get_connection_config())
        )
        data_source.set_authentication(
            data.get("authentication", data_source.get_authentication())
        )
        data_source.set_schema_config(
            data.get("schema_config", data_source.get_schema_config())
        )
        data_source.set_sample_data(
            data.get("sample_data", data_source.get_sample_data())
        )
        data_source.is_active = data.get("is_active", data_source.is_active)
        data_source.updated_at = datetime.utcnow().isoformat()
        data_source.save()
        return (jsonify(data_source.to_dict()), 200)
    except Exception as e:
        return (
            jsonify({"error": "Failed to update data source", "details": str(e)}),
            400,
        )


@analytics_bp.route("/data-sources/<source_id>", methods=["DELETE"])
@require_user_id
def delete_data_source(source_id: Any) -> Any:
    """Delete a data source."""
    try:
        data_source = DataSource.find_one(
            "id = ? AND user_id = ?", (source_id, request.user_id)
        )
        if not data_source:
            return (jsonify({"error": "Data source not found"}), 404)
        data_source.delete()
        return (jsonify({"message": "Data source deleted successfully"}), 204)
    except Exception as e:
        return (
            jsonify({"error": "Failed to delete data source", "details": str(e)}),
            500,
        )


@analytics_bp.route("/metrics", methods=["GET"])
@require_user_id
def get_metrics() -> Any:
    """Get all metrics for the current user."""
    try:
        metrics = Metric.find_all("user_id = ?", (request.user_id,))
        return (jsonify([m.to_dict() for m in metrics]), 200)
    except Exception as e:
        return (jsonify({"error": "Failed to fetch metrics", "details": str(e)}), 500)


@analytics_bp.route("/metrics", methods=["POST"])
@require_user_id
def create_metric() -> Any:
    """Create a new metric."""
    try:
        data = request.get_json()
        new_metric = Metric(
            id=str(uuid.uuid4()),
            user_id=request.user_id,
            name=data["name"],
            description=data.get("description"),
            metric_type=data["metric_type"],
            calculation_method=data["calculation_method"],
            formula=data.get("formula"),
            data_source_id=data.get("data_source_id"),
            unit=data.get("unit"),
            format_config=data.get("format_config", "{}"),
            target_value=data.get("target_value"),
            warning_threshold=data.get("warning_threshold"),
            critical_threshold=data.get("critical_threshold"),
            is_active=data.get("is_active", True),
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        new_metric.save()
        return (jsonify(new_metric.to_dict()), 201)
    except Exception as e:
        return (jsonify({"error": "Failed to create metric", "details": str(e)}), 400)


@analytics_bp.route("/metrics/<metric_id>", methods=["GET"])
@require_user_id
def get_metric(metric_id: Any) -> Any:
    """Get a specific metric by ID."""
    metric = Metric.find_one("id = ? AND user_id = ?", (metric_id, request.user_id))
    if not metric:
        return (jsonify({"error": "Metric not found"}), 404)
    return (jsonify(metric.to_dict()), 200)


@analytics_bp.route("/metrics/<metric_id>", methods=["PUT"])
@require_user_id
def update_metric(metric_id: Any) -> Any:
    """Update an existing metric."""
    try:
        metric = Metric.find_one("id = ? AND user_id = ?", (metric_id, request.user_id))
        if not metric:
            return (jsonify({"error": "Metric not found"}), 404)
        data = request.get_json()
        metric.name = data.get("name", metric.name)
        metric.description = data.get("description", metric.description)
        metric.metric_type = data.get("metric_type", metric.metric_type)
        metric.calculation_method = data.get(
            "calculation_method", metric.calculation_method
        )
        metric.formula = data.get("formula", metric.formula)
        metric.data_source_id = data.get("data_source_id", metric.data_source_id)
        metric.unit = data.get("unit", metric.unit)
        metric.set_format_config(data.get("format_config", metric.get_format_config()))
        metric.target_value = data.get("target_value", metric.target_value)
        metric.warning_threshold = data.get(
            "warning_threshold", metric.warning_threshold
        )
        metric.critical_threshold = data.get(
            "critical_threshold", metric.critical_threshold
        )
        metric.is_active = data.get("is_active", metric.is_active)
        metric.updated_at = datetime.utcnow().isoformat()
        metric.save()
        return (jsonify(metric.to_dict()), 200)
    except Exception as e:
        return (jsonify({"error": "Failed to update metric", "details": str(e)}), 400)


@analytics_bp.route("/metrics/<metric_id>", methods=["DELETE"])
@require_user_id
def delete_metric(metric_id: Any) -> Any:
    """Delete a metric."""
    try:
        metric = Metric.find_one("id = ? AND user_id = ?", (metric_id, request.user_id))
        if not metric:
            return (jsonify({"error": "Metric not found"}), 404)
        metric.delete()
        return (jsonify({"message": "Metric deleted successfully"}), 204)
    except Exception as e:
        return (jsonify({"error": "Failed to delete metric", "details": str(e)}), 500)


@analytics_bp.route("/metrics/<metric_id>/history", methods=["GET"])
@require_user_id
def get_metric_history(metric_id: Any) -> Any:
    """Get historical data for a metric."""
    try:
        metric = Metric.find_one("id = ? AND user_id = ?", (metric_id, request.user_id))
        if not metric:
            return (jsonify({"error": "Metric not found"}), 404)
        history = MetricHistory.find_all("metric_id = ?", (metric_id,))
        history.sort(key=lambda x: x.timestamp, reverse=True)
        return (jsonify([h.to_dict() for h in history]), 200)
    except Exception as e:
        return (
            jsonify({"error": "Failed to fetch metric history", "details": str(e)}),
            500,
        )


@analytics_bp.route("/metrics/<metric_id>/calculate", methods=["POST"])
@require_user_id
def calculate_metric(metric_id: Any) -> Any:
    """Calculate a metric (simulated)."""
    try:
        metric = Metric.find_one("id = ? AND user_id = ?", (metric_id, request.user_id))
        if not metric:
            return (jsonify({"error": "Metric not found"}), 404)
        new_value = metric.current_value * 1.05 if metric.current_value else 1000.0
        metric.previous_value = metric.current_value
        metric.current_value = new_value
        metric.last_calculated = datetime.utcnow().isoformat()
        metric.update_status()
        metric.save()
        new_history = MetricHistory(
            metric_id=metric_id,
            value=new_value,
            timestamp=datetime.utcnow().isoformat(),
            calculation_details={"method": "Simulated 5% growth"},
            data_points=1,
        )
        new_history.save()
        return (
            jsonify(
                {
                    "message": "Metric calculated successfully",
                    "metric": metric.to_dict(),
                    "history": new_history.to_dict(),
                }
            ),
            200,
        )
    except Exception as e:
        return (
            jsonify({"error": "Failed to calculate metric", "details": str(e)}),
            500,
        )
