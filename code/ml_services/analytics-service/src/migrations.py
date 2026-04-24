ANALYTICS_MIGRATIONS = {
    "001_create_dashboards_table": {
        "description": "Create dashboards table",
        "sql": """
        CREATE TABLE IF NOT EXISTS dashboards (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            layout TEXT,
            filters TEXT,
            is_public BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "002_create_reports_table": {
        "description": "Create reports table",
        "sql": """
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            report_type TEXT NOT NULL,
            data_source_id TEXT,
            parameters TEXT,
            schedule_config TEXT,
            last_run_at TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "003_create_report_executions_table": {
        "description": "Create report executions table",
        "sql": """
        CREATE TABLE IF NOT EXISTS report_executions (
            id TEXT PRIMARY KEY,
            report_id TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            result_file_path TEXT,
            row_count INTEGER,
            error_message TEXT,
            execution_time REAL,
            triggered_by TEXT,
            parameters_used TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "004_create_data_sources_table": {
        "description": "Create data sources table",
        "sql": """
        CREATE TABLE IF NOT EXISTS data_sources (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            source_type TEXT NOT NULL,
            connection_config TEXT,
            authentication TEXT,
            schema_config TEXT,
            sample_data TEXT,
            status TEXT DEFAULT 'active',
            last_tested TIMESTAMP,
            last_error TEXT,
            cache_enabled BOOLEAN DEFAULT 1,
            cache_duration INTEGER DEFAULT 3600,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "005_create_metrics_table": {
        "description": "Create metrics table",
        "sql": """
        CREATE TABLE IF NOT EXISTS metrics (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            metric_type TEXT NOT NULL,
            calculation_method TEXT NOT NULL,
            formula TEXT,
            data_source_id TEXT,
            unit TEXT,
            format_config TEXT,
            target_value REAL,
            warning_threshold REAL,
            critical_threshold REAL,
            current_value REAL,
            previous_value REAL,
            last_calculated TIMESTAMP,
            status TEXT DEFAULT 'normal',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "006_create_metric_history_table": {
        "description": "Create metric history table",
        "sql": """
        CREATE TABLE IF NOT EXISTS metric_history (
            id TEXT PRIMARY KEY,
            metric_id TEXT NOT NULL,
            value REAL NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            calculation_details TEXT,
            data_points INTEGER
        );
        """,
    },
}
