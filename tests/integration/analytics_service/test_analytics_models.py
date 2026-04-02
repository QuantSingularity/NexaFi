import json
import time
from typing import Any

import pytest

from backend.analytics_service.src.main import app
from backend.analytics_service.src.models.user import (
    Dashboard,
    DataSource,
    Metric,
    Report,
    ReportExecution,
    Widget,
    db,
)


@pytest.fixture(scope="module")
def client() -> Any:
    """
    Setup the test client and initialize the in-memory database.
    """
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.session.remove()
            db.drop_all()


@pytest.fixture(autouse=True)
def run_around_tests(client: Any) -> Any:
    """
    Clean up data between tests to ensure isolation.
    """
    with app.app_context():
        Widget.query.delete()
        Dashboard.query.delete()
        ReportExecution.query.delete()
        Report.query.delete()
        DataSource.query.delete()
        Metric.query.delete()
        db.session.commit()
    yield


class TestDashboardModel:

    def test_dashboard_creation(self) -> Any:
        dashboard = Dashboard(
            user_id="user123",
            name="My Financial Dashboard",
            description="Overview of financial health",
            layout=json.dumps({"rows": [{"columns": [{}, {}]}]}),
            widgets=json.dumps(
                [{"id": "widget1", "type": "chart"}, {"id": "widget2", "type": "table"}]
            ),
        )
        db.session.add(dashboard)
        db.session.commit()
        retrieved_dashboard = Dashboard.query.filter_by(user_id="user123").first()
        assert retrieved_dashboard is not None
        assert retrieved_dashboard.name == "My Financial Dashboard"
        assert retrieved_dashboard.get_layout() == {"rows": [{"columns": [{}, {}]}]}
        assert retrieved_dashboard.get_widgets()[0]["id"] == "widget1"

    def test_dashboard_to_dict(self) -> Any:
        dashboard = Dashboard(
            user_id="user123",
            name="My Financial Dashboard",
            description="Overview of financial health",
        )
        db.session.add(dashboard)
        db.session.commit()
        dashboard_dict = dashboard.to_dict()
        assert dashboard_dict["name"] == "My Financial Dashboard"
        assert "created_at" in dashboard_dict


class TestWidgetModel:

    def test_widget_creation(self) -> Any:
        widget = Widget(
            dashboard_id="dash123",
            name="Revenue Chart",
            widget_type="chart",
            data_source="/api/revenue",
            config=json.dumps({"chartType": "bar", "colors": ["#ff0000"]}),
        )
        db.session.add(widget)
        db.session.commit()
        retrieved_widget = Widget.query.filter_by(name="Revenue Chart").first()
        assert retrieved_widget is not None
        assert retrieved_widget.widget_type == "chart"
        assert retrieved_widget.get_config()["chartType"] == "bar"

    def test_widget_cache(self) -> Any:
        widget = Widget(
            dashboard_id="dash123",
            name="Test Cache Widget",
            widget_type="metric",
            data_source="/api/data",
            cache_duration=1,
        )
        db.session.add(widget)
        db.session.commit()
        assert not widget.is_cache_valid()
        widget.set_cached_data({"value": 100})
        db.session.commit()
        assert widget.is_cache_valid()
        time.sleep(1.1)
        assert not widget.is_cache_valid()


class TestReportModel:

    def test_report_creation(self) -> Any:
        report = Report(
            user_id="user123",
            name="Monthly Sales Report",
            report_type="financial",
            query="SELECT * FROM sales",
            schedule_type="monthly",
        )
        db.session.add(report)
        db.session.commit()
        retrieved_report = Report.query.filter_by(name="Monthly Sales Report").first()
        assert retrieved_report is not None
        assert retrieved_report.report_type == "financial"
        assert retrieved_report.calculate_next_run() is not None


class TestReportExecutionModel:

    def test_report_execution_creation(self) -> Any:
        report = Report(
            user_id="user123", name="Daily Report", report_type="operational"
        )
        db.session.add(report)
        db.session.commit()
        execution = ReportExecution(report_id=report.id, status="running")
        db.session.add(execution)
        db.session.commit()
        retrieved_execution = ReportExecution.query.filter_by(
            report_id=report.id
        ).first()
        assert retrieved_execution is not None
        assert retrieved_execution.status == "running"

    def test_report_execution_completion(self) -> Any:
        report = Report(
            user_id="user123", name="Daily Report", report_type="operational"
        )
        db.session.add(report)
        db.session.commit()
        execution = ReportExecution(report_id=report.id, status="running")
        db.session.add(execution)
        db.session.commit()
        execution.mark_completed(result_data={"total_sales": 1000}, row_count=10)
        db.session.commit()
        updated_execution = ReportExecution.query.get(execution.id)
        assert updated_execution.status == "completed"
        assert updated_execution.get_result_data()["total_sales"] == 1000
        assert updated_execution.row_count == 10
        assert updated_execution.execution_time is not None

    def test_report_execution_failure(self) -> Any:
        report = Report(
            user_id="user123", name="Daily Report", report_type="operational"
        )
        db.session.add(report)
        db.session.commit()
        execution = ReportExecution(report_id=report.id, status="running")
        db.session.add(execution)
        db.session.commit()
        execution.mark_failed("Database connection error")
        db.session.commit()
        updated_execution = ReportExecution.query.get(execution.id)
        assert updated_execution.status == "failed"
        assert updated_execution.error_message == "Database connection error"


class TestDataSourceModel:

    def test_data_source_creation(self) -> Any:
        data_source = DataSource(
            user_id="user123",
            name="CRM Data",
            source_type="database",
            connection_config=json.dumps({"host": "localhost", "port": 5432}),
            schema_config=json.dumps({"table": "customers", "fields": ["id", "name"]}),
        )
        db.session.add(data_source)
        db.session.commit()
        retrieved_data_source = DataSource.query.filter_by(name="CRM Data").first()
        assert retrieved_data_source is not None
        assert retrieved_data_source.source_type == "database"
        assert retrieved_data_source.get_connection_config()["host"] == "localhost"


class TestMetricModel:

    def test_metric_creation(self) -> Any:
        metric = Metric(
            user_id="user123",
            name="Total Revenue",
            metric_type="kpi",
            calculation_method="sum",
            formula="SELECT SUM(amount) FROM transactions",
            unit="$",
        )
        db.session.add(metric)
        db.session.commit()
        retrieved_metric = Metric.query.filter_by(name="Total Revenue").first()
        assert retrieved_metric is not None
        assert retrieved_metric.metric_type == "kpi"
        assert retrieved_metric.unit == "$"
