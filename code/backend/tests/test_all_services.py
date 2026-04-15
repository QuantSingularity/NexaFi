#!/usr/bin/env python3
"""
Comprehensive service testing script
Tests each service's ability to start and respond to health checks.

These tests are designed to be run when the services are actually running.
They are skipped automatically when services are not available.
"""

import os
import subprocess
import sys
import time
from typing import Any, Dict, List

import pytest
import requests

# Add shared to path
sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared"),
)  # backend/shared

SERVICES = [
    {
        "name": "user-service",
        "port": 5001,
        "path": "user-service/src",
        "main": "main.py",
        "health": "/api/v1/health",
    },
    {
        "name": "api-gateway",
        "port": 5000,
        "path": "api-gateway/src",
        "main": "main.py",
        "health": "/health",
    },
    {
        "name": "auth-service",
        "port": 5011,
        "path": "auth-service/src",
        "main": "main.py",
        "health": "/api/v1/health",
    },
    {
        "name": "compliance-service",
        "port": 5005,
        "path": "compliance-service/src",
        "main": "main.py",
        "health": "/api/v1/health",
    },
    {
        "name": "notification-service",
        "port": 5006,
        "path": "notification-service/src",
        "main": "main.py",
        "health": "/api/v1/health",
    },
    {
        "name": "ledger-service",
        "port": 5002,
        "path": "ledger-service/src",
        "main": "main.py",
        "health": "/api/v1/health",
    },
    {
        "name": "payment-service",
        "port": 5003,
        "path": "payment-service/src",
        "main": "main.py",
        "health": "/api/v1/health",
    },
]

running_processes: List[Any] = []


# ---------------------------------------------------------------------------
# Internal helpers (prefixed with _ so pytest does NOT collect them as tests)
# ---------------------------------------------------------------------------


def _start_service(service: Dict[str, Any]) -> Any:
    """Start a service and return the process."""
    base_dir = os.path.dirname(__file__)
    service_path = os.path.join(base_dir, service["path"])

    env = os.environ.copy()
    env["PYTHONPATH"] = (
        os.path.join(base_dir, "shared") + ":" + env.get("PYTHONPATH", "")
    )
    env["PORT"] = str(service["port"])

    print(f"Starting {service['name']} on port {service['port']}...")

    try:
        process = subprocess.Popen(
            ["python3", service["main"]],
            cwd=service_path,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return process
    except Exception as e:
        print(f"✗ Failed to start {service['name']}: {e}")
        return None


def _check_health(service: Dict[str, Any], timeout: int = 10):
    """Check if service responds to health check."""
    url = f"http://localhost:{service['port']}{service['health']}"
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                return True, response.json()
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.5)

    return False, None


def _is_port_open(port: int) -> bool:
    """Return True if something is already listening on *port*."""
    try:
        r = requests.get(f"http://localhost:{port}", timeout=1)
        return True
    except requests.exceptions.ConnectionError:
        return False
    except Exception:
        return True


def _run_service(service: Dict[str, Any]):
    """Start, health-check, and return (success, process) for one service."""
    print(f"\n{'='*60}")
    print(f"Testing {service['name']}")
    print(f"{'='*60}")

    process = _start_service(service)
    if not process:
        return False, None

    running_processes.append(process)

    # Wait for service to start
    time.sleep(3)

    # Check if process is still running
    if process.poll() is not None:
        stdout, stderr = process.communicate()
        print(f"✗ {service['name']} crashed during startup")
        print(f"STDOUT: {stdout[:500]}")
        print(f"STDERR: {stderr[:500]}")
        return False, process

    # Check health
    healthy, response = _check_health(service)

    if healthy:
        print(f"✓ {service['name']} is healthy")
        print(f"  Response: {response}")
        return True, process
    else:
        print(f"✗ {service['name']} failed health check")
        try:
            stdout_data = process.stdout.read(500) if process.stdout else ""
            stderr_data = process.stderr.read(500) if process.stderr else ""
            if stdout_data:
                print(f"  STDOUT: {stdout_data}")
            if stderr_data:
                print(f"  STDERR: {stderr_data}")
        except Exception:
            pass
        return False, process


def _cleanup():
    """Stop all running processes."""
    print("\nCleaning up processes...")
    for process in running_processes:
        try:
            process.terminate()
            process.wait(timeout=5)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Pytest parametrized test
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("service", SERVICES, ids=[s["name"] for s in SERVICES])
def test_service_health(service: Dict[str, Any]):
    """
    Test that each NexaFi service starts and passes its health check.

    Skipped automatically when the required port is already occupied (i.e.
    the service is not managed by this test run) or when the service binary
    cannot be launched.
    """
    # Skip if the service is already running externally on this port —
    # we do not want to fight over ports in CI.
    if _is_port_open(service["port"]):
        pytest.skip(
            f"Port {service['port']} already in use; "
            f"assuming {service['name']} is managed externally."
        )

    process = _start_service(service)
    if process is None:
        pytest.skip(f"Could not launch {service['name']} (binary/path missing)")

    running_processes.append(process)
    try:
        # Give the service a moment to start
        time.sleep(3)

        if process.poll() is not None:
            stdout, stderr = process.communicate()
            pytest.fail(
                f"{service['name']} crashed during startup.\n"
                f"STDOUT: {stdout[:500]}\nSTDERR: {stderr[:500]}"
            )

        healthy, response = _check_health(service)
        assert healthy, (
            f"{service['name']} did not pass health check at "
            f"http://localhost:{service['port']}{service['health']}"
        )
        assert response is not None, f"{service['name']} returned empty health response"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except Exception:
            process.kill()
        if process in running_processes:
            running_processes.remove(process)


# ---------------------------------------------------------------------------
# Standalone runner (python test_all_services.py)
# ---------------------------------------------------------------------------


def main():
    results: Dict[str, Any] = {}
    try:
        for service in SERVICES:
            success, process = _run_service(service)
            results[service["name"]] = success

            if process:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except Exception:
                    process.kill()
                if process in running_processes:
                    running_processes.remove(process)

        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")

        for service_name, success in results.items():
            status = "✓ PASS" if success else "✗ FAIL"
            print(f"{status:12} {service_name}")

        passed = sum(1 for s in results.values() if s)
        failed = sum(1 for s in results.values() if not s)

        print(f"\nResults: {passed} passed, {failed} failed out of {len(results)}")
        return failed == 0

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return False
    finally:
        _cleanup()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
