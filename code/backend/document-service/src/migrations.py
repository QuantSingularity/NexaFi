DOCUMENT_MIGRATIONS = {
    "001_create_documents_table": {
        "description": "Create documents table",
        "sql": """
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            document_type TEXT NOT NULL,
            title TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            mime_type TEXT,
            file_size INTEGER,
            status TEXT DEFAULT 'uploaded',
            metadata TEXT,
            extracted_data TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "002_create_document_templates_table": {
        "description": "Create document templates table",
        "sql": """
        CREATE TABLE IF NOT EXISTS document_templates (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            template_type TEXT NOT NULL,
            fields TEXT,
            metadata TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "003_create_document_shares_table": {
        "description": "Create document shares table",
        "sql": """
        CREATE TABLE IF NOT EXISTS document_shares (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            shared_with_user_id TEXT,
            shared_with_email TEXT,
            permission_level TEXT NOT NULL,
            expires_at TIMESTAMP,
            shared_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "004_create_document_versions_table": {
        "description": "Create document versions table",
        "sql": """
        CREATE TABLE IF NOT EXISTS document_versions (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            version_number INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
}
