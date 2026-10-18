import os
import sys

SRC = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.abspath(os.path.join(SRC, "..", "..", ".."))
for path in (
    os.path.join(CODE, "ml_services"),
    os.path.join(CODE, "backend", "shared"),
    SRC,
):
    if os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)

from app_factory import create_app

app = create_app()

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5004)), debug=debug_mode)
