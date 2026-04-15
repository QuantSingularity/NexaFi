CREDIT_MIGRATIONS = {
    "001_create_credit_score_models_table": {
        "description": "Create credit score models table",
        "sql": """
        CREATE TABLE IF NOT EXISTS credit_score_models (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            version TEXT NOT NULL,
            description TEXT,
            model_type TEXT,
            features TEXT,
            weights TEXT,
            thresholds TEXT,
            accuracy REAL,
            precision REAL,
            recall REAL,
            f1_score REAL,
            is_active BOOLEAN DEFAULT 1,
            is_default BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "002_create_credit_scores_table": {
        "description": "Create credit scores table",
        "sql": """
        CREATE TABLE IF NOT EXISTS credit_scores (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            score INTEGER NOT NULL,
            grade TEXT,
            risk_level TEXT,
            payment_history_score REAL,
            credit_utilization_score REAL,
            length_of_history_score REAL,
            credit_mix_score REAL,
            new_credit_score REAL,
            debt_to_income_ratio REAL,
            annual_income REAL,
            total_debt REAL,
            available_credit REAL,
            business_revenue REAL,
            business_age_months INTEGER,
            industry_risk_factor REAL,
            input_features TEXT,
            calculation_details TEXT,
            confidence_score REAL,
            expires_at TIMESTAMP,
            is_current BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "003_create_loan_applications_table": {
        "description": "Create loan applications table",
        "sql": """
        CREATE TABLE IF NOT EXISTS loan_applications (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            loan_type TEXT NOT NULL,
            requested_amount REAL NOT NULL,
            purpose TEXT,
            term_months INTEGER,
            applicant_data TEXT,
            financial_data TEXT,
            business_data TEXT,
            status TEXT DEFAULT 'pending',
            decision_date TIMESTAMP,
            decision_reason TEXT,
            credit_score_id TEXT,
            risk_assessment TEXT,
            approval_probability REAL,
            approved_amount REAL,
            interest_rate REAL,
            monthly_payment REAL,
            total_interest REAL,
            assigned_to TEXT,
            priority TEXT DEFAULT 'normal',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "004_create_loans_table": {
        "description": "Create loans table",
        "sql": """
        CREATE TABLE IF NOT EXISTS loans (
            id TEXT PRIMARY KEY,
            application_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            loan_number TEXT UNIQUE NOT NULL,
            loan_type TEXT NOT NULL,
            principal_amount REAL NOT NULL,
            interest_rate REAL NOT NULL,
            term_months INTEGER NOT NULL,
            monthly_payment REAL NOT NULL,
            status TEXT DEFAULT 'active',
            disbursement_date TIMESTAMP,
            first_payment_date TIMESTAMP,
            maturity_date TIMESTAMP,
            current_balance REAL,
            principal_balance REAL,
            interest_balance REAL,
            fees_balance REAL,
            total_payments_made REAL DEFAULT 0,
            payments_count INTEGER DEFAULT 0,
            last_payment_date TIMESTAMP,
            next_payment_date TIMESTAMP,
            days_past_due INTEGER DEFAULT 0,
            late_fees REAL DEFAULT 0,
            is_delinquent BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "005_create_loan_payments_table": {
        "description": "Create loan payments table",
        "sql": """
        CREATE TABLE IF NOT EXISTS loan_payments (
            id TEXT PRIMARY KEY,
            loan_id TEXT NOT NULL,
            payment_number INTEGER NOT NULL,
            payment_date TIMESTAMP NOT NULL,
            due_date TIMESTAMP NOT NULL,
            total_amount REAL NOT NULL,
            principal_amount REAL NOT NULL,
            interest_amount REAL NOT NULL,
            fees_amount REAL DEFAULT 0,
            late_fee_amount REAL DEFAULT 0,
            payment_method TEXT,
            payment_status TEXT DEFAULT 'completed',
            transaction_id TEXT,
            remaining_balance REAL,
            principal_balance_after REAL,
            interest_balance_after REAL,
            is_extra_payment BOOLEAN DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "006_create_risk_assessments_table": {
        "description": "Create risk assessments table",
        "sql": """
        CREATE TABLE IF NOT EXISTS risk_assessments (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            assessment_type TEXT NOT NULL,
            risk_factors TEXT,
            risk_scores TEXT,
            overall_risk_score REAL NOT NULL,
            risk_level TEXT NOT NULL,
            recommendations TEXT,
            mitigation_strategies TEXT,
            valid_until TIMESTAMP,
            confidence_level REAL,
            data_sources TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "007_create_loan_documents_table": {
        "description": "Create loan documents table",
        "sql": """
        CREATE TABLE IF NOT EXISTS loan_documents (
            id TEXT PRIMARY KEY,
            application_id TEXT NOT NULL,
            document_type TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            mime_type TEXT,
            status TEXT DEFAULT 'pending',
            verification_notes TEXT,
            verified_by TEXT,
            verified_at TIMESTAMP,
            extracted_data TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
    "008_create_loan_application_history_table": {
        "description": "Create loan application history table",
        "sql": """
        CREATE TABLE IF NOT EXISTS loan_application_history (
            id TEXT PRIMARY KEY,
            application_id TEXT NOT NULL,
            action TEXT NOT NULL,
            old_status TEXT,
            new_status TEXT,
            notes TEXT,
            changed_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    },
}
