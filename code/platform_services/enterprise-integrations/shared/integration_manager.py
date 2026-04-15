"""
Enterprise Integration Manager for NexaFi
Centralized management of all enterprise system integrations
"""

import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

import redis
import schedule
from flask import Flask, jsonify, request
from flask_cors import CORS
from prometheus_client import Counter, Gauge, Histogram, generate_latest

from .base_integration import BaseIntegration, SyncResult, setup_database

try:
    from ..sap.sap_integration import SAPIntegration, create_sap_integration
except ImportError:
    SAPIntegration = None
try:
    from ..oracle.oracle_integration import OracleIntegration, create_oracle_integration
except ImportError:
    OracleIntegration = None


@dataclass
class IntegrationRegistry:
    """Registry of available integrations"""

    name: str
    integration_class: Type[BaseIntegration]
    factory_function: callable
    description: str
    supported_entities: List[str]
    required_config: List[str]


class EnterpriseIntegrationManager:
    """Centralized manager for all enterprise integrations"""

    def __init__(
        self,
        config_file: Optional[str] = None,
        database_url: Optional[str] = None,
        redis_url: Optional[str] = None,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.integrations: Dict[str, BaseIntegration] = {}
        self.registry: Dict[str, IntegrationRegistry] = {}
        self.scheduler_thread = None
        self.is_running = False
        self.config = {}
        if database_url:
            self.db_session = setup_database(database_url)
        else:
            self.db_session = None
        if redis_url:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
        else:
            self.redis_client = None
        if config_file and os.path.exists(config_file):
            self._load_config(config_file)
        self._register_integrations()
        self.app = Flask(__name__)
        CORS(self.app)
        self._setup_routes()
        self.sync_counter = Counter(
            "integration_syncs_total", "Total syncs", ["system", "entity", "status"]
        )
        self.sync_duration = Histogram(
            "integration_sync_duration_seconds", "Sync duration", ["system", "entity"]
        )
        self.active_integrations = Gauge(
            "active_integrations_total", "Active integrations"
        )
        self.last_sync_time = Gauge(
            "integration_last_sync_timestamp",
            "Last sync timestamp",
            ["system", "entity"],
        )

    def _load_config(self, config_file: str) -> Any:
        """Load configuration from file"""
        try:
            with open(config_file, "r") as f:
                self.config = json.load(f)
            self.logger.info(f"Configuration loaded from {config_file}")
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {str(e)}")

    def _register_integrations(self) -> Any:
        """Register available integrations"""
        if SAPIntegration:
            self.registry["sap"] = IntegrationRegistry(
                name="SAP",
                integration_class=SAPIntegration,
                factory_function=create_sap_integration,
                description="SAP ERP, S/4HANA, SuccessFactors integration",
                supported_entities=[
                    "business_partners",
                    "general_ledger",
                    "purchase_orders",
                    "invoices",
                ],
                required_config=["base_url", "username", "password", "client"],
            )
        if OracleIntegration:
            self.registry["oracle"] = IntegrationRegistry(
                name="Oracle",
                integration_class=OracleIntegration,
                factory_function=create_oracle_integration,
                description="Oracle ERP Cloud, Database, HCM integration",
                supported_entities=[
                    "suppliers",
                    "invoices",
                    "general_ledger",
                    "employees",
                ],
                required_config=["base_url", "username", "password"],
            )
        self.logger.info(f"Registered {len(self.registry)} integration types")

    def create_integration(
        self, system_name: str, integration_type: str, config: Dict[str, Any]
    ) -> bool:
        """Create and register a new integration"""
        try:
            if integration_type not in self.registry:
                raise ValueError(f"Unknown integration type: {integration_type}")
            registry_entry = self.registry[integration_type]
            for required_field in registry_entry.required_config:
                if required_field not in config:
                    raise ValueError(
                        f"Missing required configuration: {required_field}"
                    )
            if integration_type == "sap":
                integration = registry_entry.factory_function(
                    config.get("system_type", "S4HANA")
                )
            elif integration_type == "oracle":
                integration = registry_entry.factory_function(
                    config.get("system_type", "ERP_CLOUD")
                )
            else:
                integration = registry_entry.factory_function()
            if not integration.test_connection():
                raise Exception("Integration connection test failed")
            self.integrations[system_name] = integration
            self.active_integrations.set(len(self.integrations))
            self.logger.info(f"Created integration: {system_name} ({integration_type})")
            return True
        except Exception as e:
            self.logger.error(f"Failed to create integration {system_name}: {str(e)}")
            return False

    def remove_integration(self, system_name: str) -> bool:
        """Remove an integration"""
        try:
            if system_name in self.integrations:
                del self.integrations[system_name]
                self.active_integrations.set(len(self.integrations))
                self.logger.info(f"Removed integration: {system_name}")
                return True
            else:
                self.logger.warning(f"Integration not found: {system_name}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to remove integration {system_name}: {str(e)}")
            return False

    def sync_integration(
        self, system_name: str, entity_type: str, **kwargs
    ) -> Optional[SyncResult]:
        """Sync specific integration"""
        if system_name not in self.integrations:
            self.logger.error(f"Integration not found: {system_name}")
            return None
        integration = self.integrations[system_name]
        try:
            start_time = time.time()
            result = integration.sync_data(entity_type, **kwargs)
            duration = time.time() - start_time
            status = "success" if result.success else "error"
            self.sync_counter.labels(
                system=system_name, entity=entity_type, status=status
            ).inc()
            self.sync_duration.labels(system=system_name, entity=entity_type).observe(
                duration
            )
            self.last_sync_time.labels(system=system_name, entity=entity_type).set(
                time.time()
            )
            return result
        except Exception as e:
            self.logger.error(f"Sync failed for {system_name}.{entity_type}: {str(e)}")
            self.sync_counter.labels(
                system=system_name, entity=entity_type, status="error"
            ).inc()
            return None

    def sync_all(self, entity_type: Optional[str] = None) -> Dict[str, SyncResult]:
        """Sync all integrations"""
        results: Dict[str, Any] = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_system: Dict[str, Any] = {}
            for system_name, integration in self.integrations.items():
                if entity_type:
                    future = executor.submit(
                        self.sync_integration, system_name, entity_type
                    )
                else:
                    future = executor.submit(
                        self.sync_integration, system_name, "default"
                    )
                future_to_system[future] = system_name
            for future in as_completed(future_to_system):
                system_name = future_to_system[future]
                try:
                    result = future.result()
                    if result:
                        results[system_name] = result
                except Exception as e:
                    self.logger.error(f"Sync failed for {system_name}: {str(e)}")
        return results

    def schedule_sync(
        self, system_name: str, entity_type: str, interval_minutes: int, **kwargs
    ) -> Any:
        """Schedule periodic sync for an integration"""

        def sync_job():
            try:
                result = self.sync_integration(system_name, entity_type, **kwargs)
                self.logger.info(
                    f"Scheduled sync completed: {system_name}.{entity_type} - {result}"
                )
            except Exception as e:
                self.logger.error(
                    f"Scheduled sync failed: {system_name}.{entity_type} - {str(e)}"
                )

        schedule.every(interval_minutes).minutes.do(sync_job)
        self.logger.info(
            f"Scheduled sync for {system_name}.{entity_type} every {interval_minutes} minutes"
        )

    def start_scheduler(self) -> Any:
        """Start the integration scheduler"""
        if self.is_running:
            return
        self.is_running = True

        def run_scheduler():
            while self.is_running:
                schedule.run_pending()
                time.sleep(1)

        self.scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self.scheduler_thread.start()
        self.logger.info("Integration scheduler started")

    def stop_scheduler(self) -> Any:
        """Stop the integration scheduler"""
        self.is_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join()
        self.logger.info("Integration scheduler stopped")

    def get_integration_status(
        self, system_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get status of integrations"""
        if system_name:
            if system_name in self.integrations:
                return self.integrations[system_name].get_integration_status()
            else:
                return {"error": f"Integration not found: {system_name}"}
        else:
            status: Dict[str, Any] = {}
            for name, integration in self.integrations.items():
                status[name] = integration.get_integration_status()
            return status

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all integrations"""
        healthy_count = 0
        total_count = len(self.integrations)
        system_status: Dict[str, Any] = {}
        for system_name, integration in self.integrations.items():
            try:
                is_healthy = integration.test_connection()
                system_status[system_name] = "healthy" if is_healthy else "unhealthy"
                if is_healthy:
                    healthy_count += 1
            except Exception as e:
                system_status[system_name] = f"error: {str(e)}"
        overall_health = (
            "healthy"
            if healthy_count == total_count
            else "degraded" if healthy_count > 0 else "unhealthy"
        )
        return {
            "overall_health": overall_health,
            "healthy_systems": healthy_count,
            "total_systems": total_count,
            "system_status": system_status,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _setup_routes(self) -> Any:
        """Setup Flask routes for API and webhooks"""

        @self.app.route("/health", methods=["GET"])
        def health():
            return jsonify(self.health_check())

        @self.app.route("/status", methods=["GET"])
        def status():
            system_name = request.args.get("system")
            return jsonify(self.get_integration_status(system_name))

        @self.app.route("/integrations", methods=["GET"])
        def list_integrations():
            return jsonify(
                {
                    "integrations": list(self.integrations.keys()),
                    "registry": {
                        name: {
                            "name": reg.name,
                            "description": reg.description,
                            "supported_entities": reg.supported_entities,
                            "required_config": reg.required_config,
                        }
                        for name, reg in self.registry.items()
                    },
                }
            )

        @self.app.route("/integrations", methods=["POST"])
        def create_integration():
            data = request.get_json()
            system_name = data.get("system_name")
            integration_type = data.get("integration_type")
            config = data.get("config", {})
            if not system_name or not integration_type:
                return (
                    jsonify({"error": "Missing system_name or integration_type"}),
                    400,
                )
            success = self.create_integration(system_name, integration_type, config)
            if success:
                return jsonify(
                    {"message": f"Integration {system_name} created successfully"}
                )
            else:
                return (
                    jsonify({"error": f"Failed to create integration {system_name}"}),
                    500,
                )

        @self.app.route("/integrations/<system_name>", methods=["DELETE"])
        def delete_integration(system_name):
            success = self.remove_integration(system_name)
            if success:
                return jsonify(
                    {"message": f"Integration {system_name} removed successfully"}
                )
            else:
                return (
                    jsonify({"error": f"Failed to remove integration {system_name}"}),
                    500,
                )

        @self.app.route("/sync", methods=["POST"])
        def sync():
            data = request.get_json()
            system_name = data.get("system_name")
            entity_type = data.get("entity_type", "default")
            kwargs = data.get("parameters", {})
            if system_name:
                result = self.sync_integration(system_name, entity_type, **kwargs)
                if result:
                    return jsonify(asdict(result))
                else:
                    return (jsonify({"error": "Sync failed"}), 500)
            else:
                results = self.sync_all(entity_type)
                return jsonify(
                    {name: asdict(result) for name, result in results.items()}
                )

        @self.app.route("/webhook/<system_name>", methods=["POST"])
        def webhook(system_name):
            if system_name not in self.integrations:
                return (
                    jsonify({"error": f"Integration not found: {system_name}"}),
                    404,
                )
            integration = self.integrations[system_name]
            payload = request.get_json()
            signature = request.headers.get("X-Signature")
            try:
                success = integration.process_webhook(payload, signature)
                if success:
                    return jsonify({"message": "Webhook processed successfully"})
                else:
                    return (jsonify({"error": "Webhook processing failed"}), 500)
            except Exception as e:
                self.logger.error(f"Webhook processing error: {str(e)}")
                return (jsonify({"error": str(e)}), 500)

        @self.app.route("/metrics", methods=["GET"])
        def metrics():
            return (
                generate_latest(),
                200,
                {"Content-Type": "text/plain; charset=utf-8"},
            )

    def run_api_server(
        self, host: str = "0.0.0.0", port: int = 5000, debug: bool = False
    ) -> Any:
        """Run the Flask API server"""
        self.logger.info(f"Starting API server on {host}:{port}")
        self.app.run(host=host, port=port, debug=debug)

    def load_integrations_from_config(self) -> Any:
        """Load integrations from configuration file"""
        if not self.config.get("integrations"):
            return
        for integration_config in self.config["integrations"]:
            system_name = integration_config["system_name"]
            integration_type = integration_config["type"]
            config = integration_config["config"]
            self.create_integration(system_name, integration_type, config)
            if "schedules" in integration_config:
                for schedule_config in integration_config["schedules"]:
                    self.schedule_sync(
                        system_name,
                        schedule_config["entity_type"],
                        schedule_config["interval_minutes"],
                        **schedule_config.get("parameters", {}),
                    )

    def export_configuration(self) -> Dict[str, Any]:
        """Export current configuration"""
        config = {
            "integrations": [],
            "metadata": {
                "exported_at": datetime.utcnow().isoformat(),
                "total_integrations": len(self.integrations),
            },
        }
        for system_name, integration in self.integrations.items():
            status = integration.get_integration_status()
            config["integrations"].append(
                {
                    "system_name": system_name,
                    "type": status.get("configuration", {}).get(
                        "auth_method", "unknown"
                    ),
                    "status": status.get("status"),
                    "last_sync": status.get("last_sync"),
                }
            )
        return config

    def backup_integration_data(self, backup_path: str) -> Any:
        """Backup integration data and configuration"""
        try:
            backup_data = {
                "configuration": self.export_configuration(),
                "health_status": self.health_check(),
                "backup_timestamp": datetime.utcnow().isoformat(),
            }
            with open(backup_path, "w") as f:
                json.dump(backup_data, f, indent=2)
            self.logger.info(f"Integration data backed up to {backup_path}")
        except Exception as e:
            self.logger.error(f"Backup failed: {str(e)}")

    def restore_integration_data(self, backup_path: str) -> Any:
        """Restore integration data from backup"""
        try:
            with open(backup_path, "r") as f:
                backup_data = json.load(f)
            self.config = backup_data.get("configuration", {})
            self.load_integrations_from_config()
            self.logger.info(f"Integration data restored from {backup_path}")
        except Exception as e:
            self.logger.error(f"Restore failed: {str(e)}")


def create_enterprise_integration_manager(
    config_file: Optional[str] = None,
) -> EnterpriseIntegrationManager:
    """Factory function to create enterprise integration manager"""
    database_url = os.getenv("INTEGRATION_DATABASE_URL", "sqlite:///integrations.db")
    redis_url = os.getenv("INTEGRATION_REDIS_URL", "redis://localhost:6379/0")
    manager = EnterpriseIntegrationManager(
        config_file=config_file, database_url=database_url, redis_url=redis_url
    )
    manager.load_integrations_from_config()
    return manager


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    manager = create_enterprise_integration_manager("integration_config.json")
    manager.start_scheduler()
    manager.run_api_server(port=5000, debug=True)
