import os

from app_factory import create_app

app = create_app()

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5004)), debug=debug_mode)
