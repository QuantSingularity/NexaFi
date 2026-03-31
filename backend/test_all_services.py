#!/usr/bin/env python3
"""
from typing import Dict, List

Comprehensive service testing script
Tests each service's ability to start and respond to health checks
"""

import os
import subprocess
import sys
import time

import requests

# Add shared to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "shared"))

services = [
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


def start_service(service):
    """Start a service and return the process"""
    base_dir = os.path.dirname(__file__)
    service_path = os.path.join(base_dir, service["path"])
    os.path.join(service_path, service["main"])

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


def check_health(service, timeout=10):
    """Check if service responds to health check"""
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


def test_service(service):
    """Test a single service"""
    print(f"\n{'='*60}")
    print(f"Testing {service['name']}")
    print(f"{'='*60}")

    process = start_service(service)
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
    healthy, response = check_health(service)

    if healthy:
        print(f"✓ {service['name']} is healthy")
        print(f"  Response: {response}")
        return True, process
    else:
        print(f"✗ {service['name']} failed health check")
        # Get some output
        try:
            stdout_data = process.stdout.read(500) if process.stdout else ""
            stderr_data = process.stderr.read(500) if process.stderr else ""
            if stdout_data:
                print(f"  STDOUT: {stdout_data}")
            if stderr_data:
                print(f"  STDERR: {stderr_data}")
        except:
            pass
        return False, process


def cleanup():
    """Stop all running processes"""
    print("\nCleaning up processes...")
    for process in running_processes:
        try:
            process.terminate()
            process.wait(timeout=5)
        except:
            try:
                process.kill()
            except:
                pass


def main():
    results: Dict[str, Any] = {}
    try:
        for service in services:
            success, process = test_service(service)
            results[service["name"]] = success

            # Stop the process after testing
            if process:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except:
                    process.kill()
                running_processes.remove(process)

        # Summary
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
        cleanup()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
