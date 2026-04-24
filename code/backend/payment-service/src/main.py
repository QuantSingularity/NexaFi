import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(__file__))
)  # local service root (routes, models, migrations)
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "shared")
)  # shared library

from database.manager import BaseModel, initialize_database
from flask import Flask, send_from_directory
from flask_cors import CORS
from routes.user import payment_bp

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), "static"))
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "nexafi-default-secret-change-in-production"
)
CORS(app, origins="*", allow_headers=["Content-Type", "Authorization", "X-User-ID"])
app.register_blueprint(payment_bp, url_prefix="/api/v1/payment")
db_path = os.path.join(os.path.dirname(__file__), "database", "app.db")
os.makedirs(os.path.dirname(db_path), exist_ok=True)
db_manager, migration_manager = initialize_database(db_path)
BaseModel.set_db_manager(db_manager)
PAYMENT_MIGRATIONS = {
    "001_create_payment_tables": {
        "description": "Create payment_methods, transactions, wallets, and recurring_payments tables",
        "sql": "\n        CREATE TABLE IF NOT EXISTS payment_methods (\n            id TEXT PRIMARY KEY,\n            user_id TEXT NOT NULL,\n            type TEXT NOT NULL,\n            provider TEXT NOT NULL,\n            external_id TEXT,\n            details TEXT,\n            is_default INTEGER DEFAULT 0,\n            is_active INTEGER DEFAULT 1,\n            is_verified INTEGER DEFAULT 0,\n            verification_status TEXT DEFAULT 'pending',\n            last_used_at TEXT,\n            expires_at TEXT,\n            created_at TEXT,\n            updated_at TEXT\n        );\n\n        CREATE TABLE IF NOT EXISTS transactions (\n            id TEXT PRIMARY KEY,\n            user_id TEXT NOT NULL,\n            payment_method_id TEXT,\n            transaction_type TEXT NOT NULL,\n            amount REAL NOT NULL,\n            currency TEXT DEFAULT 'USD',\n            description TEXT,\n            reference TEXT,\n            status TEXT NOT NULL,\n            external_transaction_id TEXT,\n            provider_response TEXT,\n            fees REAL DEFAULT 0.0,\n            net_amount REAL NOT NULL,\n            failure_reason TEXT,\n            metadata TEXT,\n            processed_at TEXT,\n            settled_at TEXT,\n            created_at TEXT,\n            updated_at TEXT\n        );\n\n        CREATE TABLE IF NOT EXISTS wallets (\n            id TEXT PRIMARY KEY,\n            user_id TEXT NOT NULL,\n            currency TEXT NOT NULL,\n            balance REAL DEFAULT 0.0,\n            available_balance REAL DEFAULT 0.0,\n            pending_balance REAL DEFAULT 0.0,\n            reserved_balance REAL DEFAULT 0.0,\n            is_active INTEGER DEFAULT 1,\n            created_at TEXT,\n            updated_at TEXT\n        );\n\n        CREATE TABLE IF NOT EXISTS wallet_balance_history (\n            id TEXT PRIMARY KEY,\n            wallet_id TEXT NOT NULL,\n            transaction_id TEXT,\n            change_type TEXT NOT NULL,\n            amount REAL NOT NULL,\n            balance_before REAL NOT NULL,\n            balance_after REAL NOT NULL,\n            description TEXT,\n            created_at TEXT\n        );\n\n        CREATE TABLE IF NOT EXISTS recurring_payments (\n            id TEXT PRIMARY KEY,\n            user_id TEXT NOT NULL,\n            payment_method_id TEXT NOT NULL,\n            amount REAL NOT NULL,\n            currency TEXT DEFAULT 'USD',\n            frequency TEXT NOT NULL,\n            description TEXT,\n            start_date TEXT NOT NULL,\n            end_date TEXT,\n            next_payment_date TEXT NOT NULL,\n            total_payments INTEGER,\n            payments_made INTEGER DEFAULT 0,\n            status TEXT DEFAULT 'active',\n            metadata TEXT,\n            created_at TEXT,\n            updated_at TEXT\n        );\n        ",
    }
}
for version, migration in PAYMENT_MIGRATIONS.items():
    migration_manager.apply_migration(
        version, migration["description"], migration["sql"]
    )


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path: str) -> object:
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return ("Static folder not configured", 404)
    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, "index.html")
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, "index.html")
        else:
            return ("Payment Service API - NexaFi Platform", 200)


@app.errorhandler(404)
def not_found(error: Exception) -> object:
    return ({"error": "Endpoint not found"}, 404)


@app.errorhandler(500)
def internal_error(error: Exception) -> object:
    return ({"error": "Internal server error"}, 500)


if __name__ == "__main__":
    os.makedirs(os.path.join(os.path.dirname(__file__), "database"), exist_ok=True)
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5003)), debug=debug_mode)
