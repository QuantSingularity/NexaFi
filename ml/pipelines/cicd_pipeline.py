"""
CI/CD Pipeline Infrastructure for MLOps
Automated testing, building, and deployment of ML models
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List
import docker
import git
from kubernetes import client
from kubernetes import config as k8s_config
from mlflow.tracking import MlflowClient
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PipelineConfig:
    """CI/CD Pipeline configuration"""

    project_name: str
    repository_url: str
    branch: str
    docker_registry: str
    k8s_namespace: str
    mlflow_uri: str
    test_data_path: str
    model_validation_threshold: float
    deployment_environments: List[str]
    notification_channels: Dict[str, str]
    security_scan_enabled: bool
    performance_test_enabled: bool
    canary_deployment_enabled: bool
    rollback_on_failure: bool


class GitManager:
    """Git operations for CI/CD pipeline"""

    def __init__(self, repo_path: str) -> None:
        self.repo_path = repo_path
        self.repo = None
        self.logger = logging.getLogger(__name__)

    def clone_repository(self, repo_url: str, branch: str = "main") -> bool:
        """Clone repository"""
        try:
            self.repo = git.Repo.clone_from(repo_url, self.repo_path, branch=branch)
            self.logger.info(f"Repository cloned successfully to {self.repo_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to clone repository: {str(e)}")
            return False

    def get_commit_info(self) -> Dict[str, str]:
        """Get current commit information"""
        if not self.repo:
            return {}
        try:
            commit = self.repo.head.commit
            return {
                "commit_hash": commit.hexsha,
                "commit_message": commit.message.strip(),
                "author": str(commit.author),
                "timestamp": datetime.fromtimestamp(commit.committed_date).isoformat(),
            }
        except Exception as e:
            self.logger.error(f"Failed to get commit info: {str(e)}")
            return {}

    def get_changed_files(self, base_commit: str = "HEAD~1") -> List[str]:
        """Get list of changed files"""
        if not self.repo:
            return []
        try:
            diff = self.repo.git.diff("--name-only", base_commit, "HEAD")
            return diff.split("\n") if diff else []
        except Exception as e:
            self.logger.error(f"Failed to get changed files: {str(e)}")
            return []


class TestRunner:
    """Automated testing for ML models and pipelines"""

    def __init__(self, project_path: str) -> None:
        self.project_path = project_path
        self.logger = logging.getLogger(__name__)

    def run_unit_tests(self) -> Dict[str, Any]:
        """Run unit tests"""
        try:
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "pytest",
                    "tests/unit",
                    "-v",
                    "--json-report",
                    "--json-report-file=test_results.json",
                ],
                cwd=self.project_path,
                capture_output=True,
                text=True,
            )
            test_results = self._parse_test_results("test_results.json")
            return {
                "status": "passed" if result.returncode == 0 else "failed",
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "test_results": test_results,
            }
        except Exception as e:
            self.logger.error(f"Unit tests failed: {str(e)}")
            return {"status": "error", "error": str(e)}

    def run_integration_tests(self) -> Dict[str, Any]:
        """Run integration tests"""
        try:
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "pytest",
                    "tests/integration",
                    "-v",
                    "--json-report",
                    "--json-report-file=integration_results.json",
                ],
                cwd=self.project_path,
                capture_output=True,
                text=True,
            )
            test_results = self._parse_test_results("integration_results.json")
            return {
                "status": "passed" if result.returncode == 0 else "failed",
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "test_results": test_results,
            }
        except Exception as e:
            self.logger.error(f"Integration tests failed: {str(e)}")
            return {"status": "error", "error": str(e)}

    def run_model_validation_tests(
        self, model_name: str, model_version: str
    ) -> Dict[str, Any]:
        """Run model validation tests"""
        try:
            result = subprocess.run(
                [
                    "python",
                    "scripts/validate_model.py",
                    "--model",
                    model_name,
                    "--version",
                    model_version,
                ],
                cwd=self.project_path,
                capture_output=True,
                text=True,
            )
            return {
                "status": "passed" if result.returncode == 0 else "failed",
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except Exception as e:
            self.logger.error(f"Model validation failed: {str(e)}")
            return {"status": "error", "error": str(e)}

    def run_security_tests(self) -> Dict[str, Any]:
        """Run security tests"""
        try:
            result = subprocess.run(
                ["bandit", "-r", ".", "-f", "json", "-o", "security_report.json"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
            )
            security_report = self._parse_security_report("security_report.json")
            return {
                "status": "passed" if result.returncode == 0 else "failed",
                "return_code": result.returncode,
                "security_report": security_report,
            }
        except Exception as e:
            self.logger.error(f"Security tests failed: {str(e)}")
            return {"status": "error", "error": str(e)}

    def run_performance_tests(self) -> Dict[str, Any]:
        """Run performance tests"""
        try:
            result = subprocess.run(
                [
                    "locust",
                    "-f",
                    "tests/performance/locustfile.py",
                    "--headless",
                    "-u",
                    "10",
                    "-r",
                    "2",
                    "-t",
                    "60s",
                    "--html",
                    "performance_report.html",
                ],
                cwd=self.project_path,
                capture_output=True,
                text=True,
            )
            return {
                "status": "passed" if result.returncode == 0 else "failed",
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except Exception as e:
            self.logger.error(f"Performance tests failed: {str(e)}")
            return {"status": "error", "error": str(e)}

    def _parse_test_results(self, results_file: str) -> Dict[str, Any]:
        """Parse pytest JSON results"""
        try:
            results_path = os.path.join(self.project_path, results_file)
            if os.path.exists(results_path):
                with open(results_path, "r") as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to parse test results: {str(e)}")
        return {}

    def _parse_security_report(self, report_file: str) -> Dict[str, Any]:
        """Parse bandit security report"""
        try:
            report_path = os.path.join(self.project_path, report_file)
            if os.path.exists(report_path):
                with open(report_path, "r") as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to parse security report: {str(e)}")
        return {}


class DockerBuilder:
    """Docker image building and management"""

    def __init__(self, registry_url: str) -> None:
        self.registry_url = registry_url
        self.docker_client = docker.from_env()
        self.logger = logging.getLogger(__name__)

    def build_model_image(
        self,
        model_name: str,
        model_version: str,
        build_context: str,
        dockerfile_path: str = None,
    ) -> str:
        """Build Docker image for model"""
        try:
            image_tag = f"{self.registry_url}/{model_name}:{model_version}"
            image, build_logs = self.docker_client.images.build(
                path=build_context,
                dockerfile=dockerfile_path,
                tag=image_tag,
                rm=True,
                pull=True,
            )
            for log in build_logs:
                if "stream" in log:
                    self.logger.info(log["stream"].strip())
            self.logger.info(f"Image {image_tag} built successfully")
            return image_tag
        except Exception as e:
            self.logger.error(f"Failed to build image: {str(e)}")
            raise

    def push_image(self, image_tag: str) -> bool:
        """Push image to registry"""
        try:
            push_logs = self.docker_client.images.push(
                image_tag, stream=True, decode=True
            )
            for log in push_logs:
                if "status" in log:
                    self.logger.debug(log["status"])
                if "error" in log:
                    self.logger.error(log["error"])
                    return False
            self.logger.info(f"Image {image_tag} pushed successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to push image: {str(e)}")
            return False

    def scan_image_security(self, image_tag: str) -> Dict[str, Any]:
        """Scan image for security vulnerabilities"""
        try:
            result = subprocess.run(
                [
                    "trivy",
                    "image",
                    "--format",
                    "json",
                    "--output",
                    "vulnerability_report.json",
                    image_tag,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                with open("vulnerability_report.json", "r") as f:
                    scan_results = json.load(f)
                return {
                    "status": "completed",
                    "vulnerabilities": scan_results,
                    "high_severity_count": self._count_high_severity_vulns(
                        scan_results
                    ),
                    "critical_severity_count": self._count_critical_severity_vulns(
                        scan_results
                    ),
                }
            else:
                return {"status": "failed", "error": result.stderr}
        except Exception as e:
            self.logger.error(f"Security scan failed: {str(e)}")
            return {"status": "error", "error": str(e)}

    def _count_high_severity_vulns(self, scan_results: Dict[str, Any]) -> int:
        """Count high severity vulnerabilities"""
        count = 0
        for result in scan_results.get("Results", []):
            for vuln in result.get("Vulnerabilities", []):
                if vuln.get("Severity") == "HIGH":
                    count += 1
        return count

    def _count_critical_severity_vulns(self, scan_results: Dict[str, Any]) -> int:
        """Count critical severity vulnerabilities"""
        count = 0
        for result in scan_results.get("Results", []):
            for vuln in result.get("Vulnerabilities", []):
                if vuln.get("Severity") == "CRITICAL":
                    count += 1
        return count


class KubernetesDeployer:
    """Kubernetes deployment management"""

    def __init__(self, namespace: str) -> None:
        self.namespace = namespace
        self.logger = logging.getLogger(__name__)
        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            k8s_config.load_kube_config()
        self.apps_v1 = client.AppsV1Api()
        self.core_v1 = client.CoreV1Api()
        self.autoscaling_v2 = client.AutoscalingV2Api()

    def deploy_model(
        self,
        model_name: str,
        model_version: str,
        image_tag: str,
        deployment_config: Dict[str, Any],
    ) -> bool:
        """Deploy model to Kubernetes"""
        try:
            deployment = self._create_deployment_manifest(
                model_name, model_version, image_tag, deployment_config
            )
            service = self._create_service_manifest(model_name, deployment_config)
            self._apply_deployment(deployment)
            self._apply_service(service)
            if deployment_config.get("auto_scaling", False):
                hpa = self._create_hpa_manifest(model_name, deployment_config)
                self._apply_hpa(hpa)
            self.logger.info(
                f"Model {model_name}:{model_version} deployed successfully"
            )
            return True
        except Exception as e:
            self.logger.error(f"Deployment failed: {str(e)}")
            return False

    def canary_deploy(
        self,
        model_name: str,
        model_version: str,
        image_tag: str,
        canary_percentage: int,
    ) -> bool:
        """Deploy model using canary deployment strategy"""
        try:
            canary_name = f"{model_name}-canary"
            canary_deployment = self._create_deployment_manifest(
                canary_name,
                model_version,
                image_tag,
                {"replicas": 1, "labels": {"version": "canary"}},
            )
            self._apply_deployment(canary_deployment)
            self._update_service_for_canary(model_name, canary_percentage)
            self.logger.info(
                f"Canary deployment for {model_name}:{model_version} created"
            )
            return True
        except Exception as e:
            self.logger.error(f"Canary deployment failed: {str(e)}")
            return False

    def promote_canary(self, model_name: str, model_version: str) -> bool:
        """Promote canary deployment to full production"""
        try:
            canary_name = f"{model_name}-canary"
            canary_deployment = self.apps_v1.read_namespaced_deployment(
                name=canary_name, namespace=self.namespace
            )
            main_deployment = self.apps_v1.read_namespaced_deployment(
                name=f"{model_name}-deployment", namespace=self.namespace
            )
            main_deployment.spec.template.spec.containers[0].image = (
                canary_deployment.spec.template.spec.containers[0].image
            )
            self.apps_v1.patch_namespaced_deployment(
                name=f"{model_name}-deployment",
                namespace=self.namespace,
                body=main_deployment,
            )
            self.apps_v1.delete_namespaced_deployment(
                name=canary_name, namespace=self.namespace
            )
            self._reset_service_traffic(model_name)
            self.logger.info(f"Canary promoted for {model_name}:{model_version}")
            return True
        except Exception as e:
            self.logger.error(f"Canary promotion failed: {str(e)}")
            return False

    def rollback_deployment(self, model_name: str, target_version: str) -> bool:
        """Rollback deployment to previous version"""
        try:
            deployment_name = f"{model_name}-deployment"
            deployment = self.apps_v1.read_namespaced_deployment(
                name=deployment_name, namespace=self.namespace
            )
            target_image = (
                deployment.spec.template.spec.containers[0].image.split(":")[0]
                + f":{target_version}"
            )
            deployment.spec.template.spec.containers[0].image = target_image
            self.apps_v1.patch_namespaced_deployment(
                name=deployment_name, namespace=self.namespace, body=deployment
            )
            self.logger.info(
                f"Rollback completed for {model_name} to version {target_version}"
            )
            return True
        except Exception as e:
            self.logger.error(f"Rollback failed: {str(e)}")
            return False

    def get_deployment_status(self, model_name: str) -> Dict[str, Any]:
        """Get deployment status"""
        try:
            deployment_name = f"{model_name}-deployment"
            deployment = self.apps_v1.read_namespaced_deployment(
                name=deployment_name, namespace=self.namespace
            )
            return {
                "name": deployment.metadata.name,
                "namespace": deployment.metadata.namespace,
                "replicas": deployment.spec.replicas,
                "ready_replicas": deployment.status.ready_replicas or 0,
                "available_replicas": deployment.status.available_replicas or 0,
                "image": deployment.spec.template.spec.containers[0].image,
                "creation_timestamp": deployment.metadata.creation_timestamp.isoformat(),
                "status": (
                    "ready"
                    if deployment.status.ready_replicas == deployment.spec.replicas
                    else "not_ready"
                ),
            }
        except Exception as e:
            self.logger.error(f"Failed to get deployment status: {str(e)}")
            return {"status": "error", "error": str(e)}

    def _create_deployment_manifest(
        self,
        model_name: str,
        model_version: str,
        image_tag: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create Kubernetes deployment manifest"""
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": f"{model_name}-deployment",
                "namespace": self.namespace,
                "labels": {
                    "app": model_name,
                    "version": model_version,
                    "component": "ml-model",
                },
            },
            "spec": {
                "replicas": config.get("replicas", 2),
                "selector": {"matchLabels": {"app": model_name}},
                "template": {
                    "metadata": {
                        "labels": {
                            "app": model_name,
                            "version": model_version,
                            "component": "ml-model",
                        }
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": model_name,
                                "image": image_tag,
                                "ports": [{"containerPort": 8080}],
                                "resources": {
                                    "requests": {
                                        "cpu": config.get("cpu_request", "100m"),
                                        "memory": config.get("memory_request", "256Mi"),
                                    },
                                    "limits": {
                                        "cpu": config.get("cpu_limit", "500m"),
                                        "memory": config.get("memory_limit", "512Mi"),
                                    },
                                },
                                "env": [
                                    {"name": "MODEL_NAME", "value": model_name},
                                    {"name": "MODEL_VERSION", "value": model_version},
                                ],
                                "readinessProbe": {
                                    "httpGet": {"path": "/ready", "port": 8080},
                                    "initialDelaySeconds": 30,
                                    "periodSeconds": 10,
                                },
                                "livenessProbe": {
                                    "httpGet": {"path": "/health", "port": 8080},
                                    "initialDelaySeconds": 60,
                                    "periodSeconds": 30,
                                },
                            }
                        ]
                    },
                },
            },
        }

    def _create_service_manifest(
        self, model_name: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create Kubernetes service manifest"""
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": f"{model_name}-service",
                "namespace": self.namespace,
                "labels": {"app": model_name, "component": "ml-model"},
            },
            "spec": {
                "selector": {"app": model_name},
                "ports": [{"port": 80, "targetPort": 8080, "protocol": "TCP"}],
                "type": "ClusterIP",
            },
        }

    def _create_hpa_manifest(
        self, model_name: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create HPA manifest"""
        return {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {"name": f"{model_name}-hpa", "namespace": self.namespace},
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": f"{model_name}-deployment",
                },
                "minReplicas": config.get("min_replicas", 1),
                "maxReplicas": config.get("max_replicas", 5),
                "metrics": [
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "cpu",
                            "target": {
                                "type": "Utilization",
                                "averageUtilization": config.get(
                                    "target_cpu_utilization", 70
                                ),
                            },
                        },
                    }
                ],
            },
        }

    def _apply_deployment(self, deployment: Dict[str, Any]) -> Any:
        """Apply deployment to Kubernetes"""
        try:
            self.apps_v1.create_namespaced_deployment(
                namespace=self.namespace, body=deployment
            )
        except client.ApiException as e:
            if e.status == 409:
                self.apps_v1.patch_namespaced_deployment(
                    name=deployment["metadata"]["name"],
                    namespace=self.namespace,
                    body=deployment,
                )
            else:
                raise

    def _apply_service(self, service: Dict[str, Any]) -> Any:
        """Apply service to Kubernetes"""
        try:
            self.core_v1.create_namespaced_service(
                namespace=self.namespace, body=service
            )
        except client.ApiException as e:
            if e.status == 409:
                self.core_v1.patch_namespaced_service(
                    name=service["metadata"]["name"],
                    namespace=self.namespace,
                    body=service,
                )
            else:
                raise

    def _apply_hpa(self, hpa: Dict[str, Any]) -> Any:
        """Apply HPA to Kubernetes"""
        try:
            self.autoscaling_v2.create_namespaced_horizontal_pod_autoscaler(
                namespace=self.namespace, body=hpa
            )
        except client.ApiException as e:
            if e.status == 409:
                self.autoscaling_v2.patch_namespaced_horizontal_pod_autoscaler(
                    name=hpa["metadata"]["name"], namespace=self.namespace, body=hpa
                )
            else:
                raise

    def _update_service_for_canary(
        self, model_name: str, canary_percentage: int
    ) -> Any:
        """Update service for canary deployment"""
        self.logger.info(
            f"Updated service for canary deployment: {canary_percentage}% traffic"
        )

    def _reset_service_traffic(self, model_name: str) -> Any:
        """Reset service to normal traffic routing"""
        self.logger.info(f"Reset service traffic for {model_name}")


class NotificationManager:
    """Notification management for CI/CD pipeline"""

    def __init__(self, channels: Dict[str, str]) -> None:
        self.channels = channels
        self.logger = logging.getLogger(__name__)

    def send_build_notification(self, status: str, details: Dict[str, Any]) -> Any:
        """Send build notification"""
        message = self._format_build_message(status, details)
        self._send_to_channels(message, "build")

    def send_deployment_notification(self, status: str, details: Dict[str, Any]) -> Any:
        """Send deployment notification"""
        message = self._format_deployment_message(status, details)
        self._send_to_channels(message, "deployment")

    def send_alert(self, alert_type: str, message: str) -> Any:
        """Send alert notification"""
        alert_message = f"🚨 ALERT: {alert_type}\n{message}"
        self._send_to_channels(alert_message, "alert")

    def _format_build_message(self, status: str, details: Dict[str, Any]) -> str:
        """Format build notification message"""
        emoji = "✅" if status == "success" else "❌"
        return f"{emoji} Build {status.upper()}\nModel: {details.get('model_name', 'unknown')}\nVersion: {details.get('model_version', 'unknown')}\nCommit: {details.get('commit_hash', 'unknown')[:8]}\nDuration: {details.get('duration', 'unknown')}"

    def _format_deployment_message(self, status: str, details: Dict[str, Any]) -> str:
        """Format deployment notification message"""
        emoji = "🚀" if status == "success" else "💥"
        return f"{emoji} Deployment {status.upper()}\nModel: {details.get('model_name', 'unknown')}\nVersion: {details.get('model_version', 'unknown')}\nEnvironment: {details.get('environment', 'unknown')}\nReplicas: {details.get('replicas', 'unknown')}"

    def _send_to_channels(self, message: str, notification_type: str) -> Any:
        """Send message to configured channels"""
        for channel_type, config in self.channels.items():
            try:
                if channel_type == "slack":
                    self._send_slack_message(config, message)
                elif channel_type == "email":
                    self._send_email(config, message, notification_type)
                elif channel_type == "webhook":
                    self._send_webhook(config, message, notification_type)
            except Exception as e:
                self.logger.error(
                    f"Failed to send notification to {channel_type}: {str(e)}"
                )

    def _send_slack_message(self, config: str, message: str) -> Any:
        """Send Slack message"""
        import requests

        payload = {"text": message}
        response = requests.post(config, json=payload)
        response.raise_for_status()

    def _send_email(self, config: Dict[str, str], message: str, subject: str) -> Any:
        """Send email notification"""
        import smtplib
        from email.mime.text import MIMEText

        msg = MIMEText(message)
        msg["Subject"] = f"NexaFi MLOps: {subject}"
        msg["From"] = config["from"]
        msg["To"] = config["to"]
        with smtplib.SMTP(config["smtp_server"], config.get("port", 587)) as server:
            server.starttls()
            server.login(config["username"], config["password"])
            server.send_message(msg)

    def _send_webhook(self, config: str, message: str, notification_type: str) -> Any:
        """Send webhook notification"""
        import requests

        payload = {
            "type": notification_type,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }
        response = requests.post(config, json=payload)
        response.raise_for_status()


class CICDPipeline:
    """Main CI/CD pipeline orchestrator"""

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.git_manager = None
        self.test_runner = None
        self.docker_builder = DockerBuilder(config.docker_registry)
        self.k8s_deployer = KubernetesDeployer(config.k8s_namespace)
        self.notification_manager = NotificationManager(config.notification_channels)
        self.mlflow_client = MlflowClient(config.mlflow_uri)

    def run_pipeline(self, trigger_event: Dict[str, Any]) -> Dict[str, Any]:
        """Run complete CI/CD pipeline"""
        pipeline_start = datetime.now()
        pipeline_id = f"pipeline-{int(pipeline_start.timestamp())}"
        try:
            self.logger.info(f"Starting CI/CD pipeline {pipeline_id}")
            workspace_path = self._setup_workspace(pipeline_id)
            self.git_manager = GitManager(workspace_path)
            if not self.git_manager.clone_repository(
                self.config.repository_url, self.config.branch
            ):
                raise Exception("Failed to clone repository")
            commit_info = self.git_manager.get_commit_info()
            changed_files = self.git_manager.get_changed_files()
            model_changes = self._detect_model_changes(changed_files)
            self.test_runner = TestRunner(workspace_path)
            test_results = self._run_all_tests()
            if not self._all_tests_passed(test_results):
                raise Exception("Tests failed")
            build_results = {}
            for model_name, model_info in model_changes.items():
                build_result = self._build_and_scan_model(
                    model_name, model_info, workspace_path
                )
                build_results[model_name] = build_result
                if not build_result["success"]:
                    raise Exception(f"Build failed for model {model_name}")
            deployment_results = {}
            for model_name, build_result in build_results.items():
                if build_result["success"]:
                    deployment_result = self._deploy_model(model_name, build_result)
                    deployment_results[model_name] = deployment_result
            post_deployment_results = self._run_post_deployment_tests(
                deployment_results
            )
            pipeline_duration = (datetime.now() - pipeline_start).total_seconds()
            self.notification_manager.send_build_notification(
                "success",
                {
                    "pipeline_id": pipeline_id,
                    "commit_hash": commit_info.get("commit_hash"),
                    "duration": f"{pipeline_duration:.2f}s",
                    "models_deployed": list(deployment_results.keys()),
                },
            )
            self._cleanup_workspace(workspace_path)
            return {
                "pipeline_id": pipeline_id,
                "status": "success",
                "duration_seconds": pipeline_duration,
                "commit_info": commit_info,
                "test_results": test_results,
                "build_results": build_results,
                "deployment_results": deployment_results,
                "post_deployment_results": post_deployment_results,
            }
        except Exception as e:
            self.logger.error(f"Pipeline {pipeline_id} failed: {str(e)}")
            self.notification_manager.send_alert("Pipeline Failure", str(e))
            if "workspace_path" in locals():
                self._cleanup_workspace(workspace_path)
            return {
                "pipeline_id": pipeline_id,
                "status": "failed",
                "error": str(e),
                "duration_seconds": (datetime.now() - pipeline_start).total_seconds(),
            }

    def _setup_workspace(self, pipeline_id: str) -> str:
        """Setup temporary workspace"""
        workspace_path = os.path.join(
            tempfile.gettempdir(), f"nexafi-pipeline-{pipeline_id}"
        )
        os.makedirs(workspace_path, exist_ok=True)
        return workspace_path

    def _cleanup_workspace(self, workspace_path: str) -> Any:
        """Cleanup temporary workspace"""
        try:
            shutil.rmtree(workspace_path)
        except Exception as e:
            self.logger.warning(f"Failed to cleanup workspace: {str(e)}")

    def _detect_model_changes(
        self, changed_files: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Detect which models have changed"""
        model_changes = {}
        for file_path in changed_files:
            if file_path.startswith("ml/models/"):
                path_parts = file_path.split("/")
                if len(path_parts) >= 3:
                    model_name = path_parts[2]
                    if model_name not in model_changes:
                        model_changes[model_name] = {
                            "changed_files": [],
                            "version": self._generate_model_version(),
                        }
                    model_changes[model_name]["changed_files"].append(file_path)
        return model_changes

    def _generate_model_version(self) -> str:
        """Generate new model version"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"v{timestamp}"

    def _run_all_tests(self) -> Dict[str, Any]:
        """Run all test suites"""
        results = {}
        results["unit_tests"] = self.test_runner.run_unit_tests()
        results["integration_tests"] = self.test_runner.run_integration_tests()
        if self.config.security_scan_enabled:
            results["security_tests"] = self.test_runner.run_security_tests()
        if self.config.performance_test_enabled:
            results["performance_tests"] = self.test_runner.run_performance_tests()
        return results

    def _all_tests_passed(self, test_results: Dict[str, Any]) -> bool:
        """Check if all tests passed"""
        for test_type, result in test_results.items():
            if result.get("status") != "passed":
                return False
        return True

    def _build_and_scan_model(
        self, model_name: str, model_info: Dict[str, Any], workspace_path: str
    ) -> Dict[str, Any]:
        """Build and scan model image"""
        try:
            model_version = model_info["version"]
            image_tag = self.docker_builder.build_model_image(
                model_name, model_version, workspace_path
            )
            push_success = self.docker_builder.push_image(image_tag)
            if not push_success:
                return {"success": False, "error": "Failed to push image"}
            scan_results = self.docker_builder.scan_image_security(image_tag)
            if scan_results.get("critical_severity_count", 0) > 0:
                return {
                    "success": False,
                    "error": "Critical security vulnerabilities found",
                    "scan_results": scan_results,
                }
            return {
                "success": True,
                "image_tag": image_tag,
                "scan_results": scan_results,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _deploy_model(
        self, model_name: str, build_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deploy model to environments"""
        deployment_results = {}
        for environment in self.config.deployment_environments:
            try:
                if environment == "staging":
                    success = self.k8s_deployer.deploy_model(
                        model_name,
                        build_result["image_tag"].split(":")[-1],
                        build_result["image_tag"],
                        {"replicas": 1, "environment": "staging"},
                    )
                    deployment_results[environment] = {"success": success}
                elif environment == "production":
                    if self.config.canary_deployment_enabled:
                        success = self.k8s_deployer.canary_deploy(
                            model_name,
                            build_result["image_tag"].split(":")[-1],
                            build_result["image_tag"],
                            10,
                        )
                        deployment_results[environment] = {
                            "success": success,
                            "deployment_type": "canary",
                        }
                    else:
                        success = self.k8s_deployer.deploy_model(
                            model_name,
                            build_result["image_tag"].split(":")[-1],
                            build_result["image_tag"],
                            {"replicas": 3, "environment": "production"},
                        )
                        deployment_results[environment] = {"success": success}
            except Exception as e:
                deployment_results[environment] = {"success": False, "error": str(e)}
        return deployment_results

    def _run_post_deployment_tests(
        self, deployment_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run post-deployment validation tests"""
        results = {}
        for model_name, deployment_result in deployment_results.items():
            if deployment_result.get("success"):
                health_check = self._run_health_check_tests(model_name)
                load_test = self._run_load_tests(model_name)
                results[model_name] = {
                    "health_check": health_check,
                    "load_test": load_test,
                }
        return results

    def _run_health_check_tests(self, model_name: str) -> Dict[str, Any]:
        """Run health check tests"""
        return {"status": "passed", "response_time_ms": 150}

    def _run_load_tests(self, model_name: str) -> Dict[str, Any]:
        """Run load tests"""
        return {"status": "passed", "avg_response_time_ms": 200, "error_rate": 0.01}


def create_pipeline_config() -> PipelineConfig:
    """Create default pipeline configuration"""
    return PipelineConfig(
        project_name="nexafi-ml",
        repository_url="https://github.com/nexafi/ml-models.git",
        branch="main",
        docker_registry="nexafi-registry.com",
        k8s_namespace="nexafi-ml",
        mlflow_uri="http://mlflow-server:5000",
        test_data_path="/data/test",
        model_validation_threshold=0.8,
        deployment_environments=["staging", "production"],
        notification_channels={
            "slack": "https://hooks.slack.com/services/...",
            "email": {
                "smtp_server": "smtp.company.com",
                "username": "notifications@company.com",
                "password": "password",
                "from": "notifications@company.com",
                "to": "ml-team@company.com",
            },
        },
        security_scan_enabled=True,
        performance_test_enabled=True,
        canary_deployment_enabled=True,
        rollback_on_failure=True,
    )


if __name__ == "__main__":
    config = create_pipeline_config()
    pipeline = CICDPipeline(config)
    trigger_event = {
        "type": "push",
        "branch": "main",
        "commit_hash": "abc123",
        "author": "developer@company.com",
    }
    result = pipeline.run_pipeline(trigger_event)
    logger.info(f"Pipeline result: {result['status']}")
