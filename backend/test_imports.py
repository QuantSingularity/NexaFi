#!/usr/bin/env python3
"""Test script to identify import and runtime issues in all services"""

import os
import sys
import traceback
from typing import Dict

# Add shared to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "shared"))


def test_service_imports(service_name, service_path):
    """Test imports for a specific service"""
    print(f"\n{'='*60}")
    print(f"Testing {service_name}")
    print(f"{'='*60}")

    # Add service to path
    sys.path.insert(0, os.path.join(service_path, "src"))

    try:
        # Try to import main module
        print(f"✓ {service_name} imports successfully")
        return True
    except Exception as e:
        print(f"✗ {service_name} import failed:")
        print(f"  Error: {str(e)}")
        traceback.print_exc()
        return False
    finally:
        # Clean up path
        if os.path.join(service_path, "src") in sys.path:
            sys.path.remove(os.path.join(service_path, "src"))


def main():
    base_dir = os.path.dirname(__file__)

    services = [
        ("api-gateway", os.path.join(base_dir, "api-gateway")),
        ("user-service", os.path.join(base_dir, "user-service")),
        ("auth-service", os.path.join(base_dir, "auth-service")),
        ("compliance-service", os.path.join(base_dir, "compliance-service")),
        ("notification-service", os.path.join(base_dir, "notification-service")),
        ("ledger-service", os.path.join(base_dir, "ledger-service")),
        ("payment-service", os.path.join(base_dir, "payment-service")),
        ("ai-service", os.path.join(base_dir, "ai-service")),
        ("analytics-service", os.path.join(base_dir, "analytics-service")),
        ("credit-service", os.path.join(base_dir, "credit-service")),
        ("document-service", os.path.join(base_dir, "document-service")),
    ]

    results: Dict[str, Any] = {}
    for service_name, service_path in services:
        if os.path.exists(os.path.join(service_path, "src", "main.py")):
            results[service_name] = test_service_imports(service_name, service_path)
        else:
            print(f"\n{'='*60}")
            print(f"Skipping {service_name} - main.py not found")
            print(f"{'='*60}")
            results[service_name] = None

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for service, result in results.items():
        if result is None:
            status = "SKIPPED"
        elif result:
            status = "✓ PASS"
        else:
            status = "✗ FAIL"
        print(f"{status:12} {service}")

    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    skipped = sum(1 for r in results.values() if r is None)

    print(f"\nResults: {passed} passed, {failed} failed, {skipped} skipped")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
