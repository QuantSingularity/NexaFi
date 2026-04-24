import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(__file__))
)  # local service root (routes, models, migrations)
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "..", "..", "backend", "shared"
    ),
)  # shared library
from database.manager import BaseModel, initialize_database
from flask import Flask, send_from_directory
from flask_cors import CORS
from routes.user import user_bp

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), "static"))
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "nexafi-default-secret-change-in-production"
)
CORS(app, origins="*", allow_headers=["Content-Type", "Authorization", "X-User-ID"])
app.register_blueprint(user_bp, url_prefix="/api/v1")
db_path = os.path.join(os.path.dirname(__file__), "database", "app.db")
os.makedirs(os.path.dirname(db_path), exist_ok=True)
db_manager, migration_manager = initialize_database(db_path)
BaseModel.set_db_manager(db_manager)

from migrations import AI_MIGRATIONS

for version, migration in AI_MIGRATIONS.items():
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
            return ("AI Service API - NexaFi Platform", 200)


@app.errorhandler(404)
def not_found(error: Exception) -> object:
    return ({"error": "Endpoint not found"}, 404)


@app.errorhandler(500)
def internal_error(error: Exception) -> object:
    return ({"error": "Internal server error"}, 500)


if __name__ == "__main__":
    os.makedirs(os.path.join(os.path.dirname(__file__), "database"), exist_ok=True)
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5004)), debug=debug_mode)
