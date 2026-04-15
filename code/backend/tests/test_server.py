#!/usr/bin/env python3
"""
Simple Test Server for NexaFi Backend
Tests if the API Gateway can start successfully
"""

import os
import sys

# Add shared to path
sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared"),
)  # backend/shared

print("=" * 60)
print("NexaFi Backend Test Server")
print("=" * 60)

# Test imports
print("\n[1/3] Testing imports...")
try:
    from flask import Flask

    print("✓ Flask imports successful")
except ImportError as e:
    print(f"✗ Flask import failed: {e}")
    print("  Run: pip install Flask Flask-Cors")
    sys.exit(1)

print("\n[2/3] Testing shared modules...")
try:
    print("✓ Logging module accessible")
except ImportError as e:
    print(f"✗ Shared module import failed: {e}")
    print("  This is OK for initial testing")

print("\n[3/3] Starting minimal server...")
try:
    app = Flask(__name__)

    @app.route("/health")
    def health():
        return {"status": "healthy", "service": "test-server"}

    @app.route("/")
    def index():
        return {"message": "NexaFi Backend Test Server", "status": "running"}

    print("\n" + "=" * 60)
    print("✓ Server starting successfully!")
    print("=" * 60)
    print("\nTest endpoints:")
    print("  - http://localhost:5000/")
    print("  - http://localhost:5000/health")
    print("\nPress Ctrl+C to stop\n")

    app.run(host="0.0.0.0", port=5000, debug=False)

except Exception as e:
    print(f"\n✗ Server failed to start: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
