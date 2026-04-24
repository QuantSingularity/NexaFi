AI_MIGRATIONS = {
    "001_create_ai_models_table": {
        "description": "Create AI models table",
        "sql": """
        CREATE TABLE IF NOT EXISTS ai_models (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            model_type TEXT NOT NULL,
            version TEXT NOT NULL,
            description TEXT,
            model_config TEXT,
            training_data_info TEXT,
            performance_metrics TEXT,
            is_active BOOLEAN DEFAULT 1,
            is_production BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "002_create_ai_predictions_table": {
        "description": "Create AI predictions table",
        "sql": """
        CREATE TABLE IF NOT EXISTS ai_predictions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            prediction_type TEXT NOT NULL,
            input_data TEXT NOT NULL,
            prediction_result TEXT NOT NULL,
            confidence_score REAL,
            explanation TEXT,
            status TEXT DEFAULT 'completed',
            execution_time_ms INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "003_create_financial_insights_table": {
        "description": "Create financial insights table",
        "sql": """
        CREATE TABLE IF NOT EXISTS financial_insights (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            insight_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            severity TEXT DEFAULT 'info',
            category TEXT,
            data_points TEXT,
            recommendations TEXT,
            is_read BOOLEAN DEFAULT 0,
            is_dismissed BOOLEAN DEFAULT 0,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "004_create_conversation_sessions_table": {
        "description": "Create conversation sessions table",
        "sql": """
        CREATE TABLE IF NOT EXISTS conversation_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            session_name TEXT,
            context TEXT,
            is_active BOOLEAN DEFAULT 1,
            last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "005_create_conversation_messages_table": {
        "description": "Create conversation messages table",
        "sql": """
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            message_type TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata TEXT,
            tokens_used INTEGER,
            processing_time_ms INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "006_create_feature_store_table": {
        "description": "Create feature store table",
        "sql": """
        CREATE TABLE IF NOT EXISTS feature_store (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            feature_name TEXT NOT NULL,
            feature_group TEXT NOT NULL,
            feature_value TEXT NOT NULL,
            feature_type TEXT NOT NULL,
            calculation_method TEXT,
            data_sources TEXT,
            valid_from TIMESTAMP NOT NULL,
            valid_until TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "007_create_model_training_jobs_table": {
        "description": "Create model training jobs table",
        "sql": """
        CREATE TABLE IF NOT EXISTS model_training_jobs (
            id TEXT PRIMARY KEY,
            model_id TEXT NOT NULL,
            job_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            training_config TEXT,
            dataset_info TEXT,
            metrics TEXT,
            logs TEXT,
            error_message TEXT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
}
