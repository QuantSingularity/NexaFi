"""
Oracle Enterprise Integration for NexaFi
Comprehensive integration with Oracle ERP Cloud, Oracle Database, Oracle HCM, and other Oracle systems
"""

import base64
import csv
import io
import logging
import os
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import cx_Oracle
import jwt
import pandas as pd
import requests
from nexafi_logging.logger import get_logger
from requests.auth import HTTPBasicAuth
from sqlalchemy import create_engine

from ..shared.base_integration import (
    AuthMethod,
    BaseIntegration,
    DataTransformer,
    IntegrationConfig,
    SyncResult,
)

logger = get_logger(__name__)


@dataclass
class OracleConfig:
    """Oracle-specific configuration"""

    oracle_system: str
    database_service: Optional[str] = None
    database_host: Optional[str] = None
    database_port: int = 1521
    database_sid: Optional[str] = None
    database_service_name: Optional[str] = None
    rest_api_version: str = "v1"
    soap_api_version: str = "v1"
    enable_database: bool = False
    enable_rest_api: bool = True
    enable_soap_api: bool = False
    enable_bulk_import: bool = True
    enable_bi_publisher: bool = False
    custom_objects: Optional[Dict[str, str]] = None
    fusion_apps_config: Optional[Dict[str, Any]] = None
    security_config: Optional[Dict[str, Any]] = None


class OracleAuthenticator:
    """Oracle authentication handler"""

    def __init__(self, config: IntegrationConfig, oracle_config: OracleConfig) -> None:
        self.config = config
        self.oracle_config = oracle_config
        self.logger = logging.getLogger(__name__)
        self.access_token = None
        self.token_expires_at = None
        self.session_id = None

    def authenticate(self) -> bool:
        """Authenticate with Oracle system"""
        try:
            if self.config.auth_method == AuthMethod.OAUTH2:
                return self._oauth2_authenticate()
            elif self.config.auth_method == AuthMethod.BASIC:
                return self._basic_authenticate()
            elif self.config.auth_method == AuthMethod.JWT:
                return self._jwt_authenticate()
            elif self.config.auth_method == AuthMethod.CERTIFICATE:
                return self._certificate_authenticate()
            else:
                self.logger.error(f"Unsupported auth method: {self.config.auth_method}")
                return False
        except Exception as e:
            self.logger.error(f"Oracle authentication failed: {str(e)}")
            return False

    def _oauth2_authenticate(self) -> bool:
        """OAuth2 authentication for Oracle Cloud"""
        try:
            token_url = f"{self.config.base_url}/oauth2/v1/token"
            client_credentials = base64.b64encode(
                f"{self.config.credentials['client_id']}:{self.config.credentials['client_secret']}".encode()
            ).decode()
            headers = {
                "Authorization": f"Basic {client_credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            data = {
                "grant_type": "client_credentials",
                "scope": self.config.credentials.get(
                    "scope", "urn:opc:resource:fa:instanceid"
                ),
            }
            response = requests.post(token_url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data["access_token"]
            self.token_expires_at = datetime.utcnow() + timedelta(
                seconds=token_data["expires_in"]
            )
            return True
        except Exception as e:
            self.logger.error(f"OAuth2 authentication failed: {str(e)}")
            return False

    def _basic_authenticate(self) -> bool:
        """Basic authentication for Oracle systems"""
        try:
            test_url = f"{self.config.base_url}/fscmRestApi/resources/latest/users"
            auth = HTTPBasicAuth(
                self.config.credentials["username"], self.config.credentials["password"]
            )
            response = requests.get(test_url, auth=auth, timeout=self.config.timeout)
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Basic authentication failed: {str(e)}")
            return False

    def _jwt_authenticate(self) -> bool:
        """JWT authentication for Oracle Cloud"""
        try:
            now = datetime.utcnow()
            payload = {
                "iss": self.config.credentials["client_id"],
                "sub": self.config.credentials["username"],
                "aud": f"{self.config.base_url}/oauth2/v1/token",
                "exp": int((now + timedelta(minutes=5)).timestamp()),
                "iat": int(now.timestamp()),
            }
            private_key = self.config.credentials["private_key"]
            token = jwt.encode(payload, private_key, algorithm="RS256")
            token_url = f"{self.config.base_url}/oauth2/v1/token"
            data = {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": token,
                "scope": self.config.credentials.get(
                    "scope", "urn:opc:resource:fa:instanceid"
                ),
            }
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data["access_token"]
            self.token_expires_at = datetime.utcnow() + timedelta(
                seconds=token_data["expires_in"]
            )
            return True
        except Exception as e:
            self.logger.error(f"JWT authentication failed: {str(e)}")
            return False

    def _certificate_authenticate(self) -> bool:
        """Certificate-based authentication"""
        try:
            cert_file = self.config.credentials.get("cert_file")
            key_file = self.config.credentials.get("key_file")
            if not cert_file or not key_file:
                return False
            test_url = f"{self.config.base_url}/fscmRestApi/resources/latest/users"
            response = requests.get(
                test_url, cert=(cert_file, key_file), timeout=self.config.timeout
            )
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Certificate authentication failed: {str(e)}")
            return False

    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        headers: Dict[str, Any] = {}
        if self.config.auth_method == AuthMethod.OAUTH2:
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"
        elif self.config.auth_method == AuthMethod.BASIC:
            credentials = base64.b64encode(
                f"{self.config.credentials['username']}:{self.config.credentials['password']}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {credentials}"
        elif self.config.auth_method == AuthMethod.JWT:
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def is_token_valid(self) -> bool:
        """Check if current token is valid"""
        if not self.access_token:
            return False
        if self.token_expires_at and datetime.utcnow() >= self.token_expires_at:
            return False
        return True


class OracleDatabaseConnector:
    """Oracle Database connector"""

    def __init__(self, config: IntegrationConfig, oracle_config: OracleConfig) -> None:
        self.config = config
        self.oracle_config = oracle_config
        self.logger = logging.getLogger(__name__)
        self.connection = None
        self.engine = None

    def connect(self) -> bool:
        """Connect to Oracle Database"""
        try:
            if self.oracle_config.database_service_name:
                dsn = cx_Oracle.makedsn(
                    self.oracle_config.database_host,
                    self.oracle_config.database_port,
                    service_name=self.oracle_config.database_service_name,
                )
            else:
                dsn = cx_Oracle.makedsn(
                    self.oracle_config.database_host,
                    self.oracle_config.database_port,
                    sid=self.oracle_config.database_sid,
                )
            self.connection = cx_Oracle.connect(
                user=self.config.credentials["username"],
                password=self.config.credentials["password"],
                dsn=dsn,
                encoding="UTF-8",
            )
            connection_string = f"oracle+cx_oracle://{self.config.credentials['username']}:{self.config.credentials['password']}@{dsn}"
            self.engine = create_engine(connection_string)
            return True
        except Exception as e:
            self.logger.error(f"Database connection failed: {str(e)}")
            return False

    def disconnect(self) -> Any:
        """Disconnect from Oracle Database"""
        if self.connection:
            self.connection.close()
            self.connection = None
        if self.engine:
            self.engine.dispose()
            self.engine = None

    def execute_query(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute SQL query"""
        if not self.connection:
            raise Exception("Not connected to Oracle Database")
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            results: List[Any] = []
            for row in rows:
                results.append(dict(zip(columns, row)))
            cursor.close()
            return results
        except Exception as e:
            self.logger.error(f"Query execution failed: {str(e)}")
            raise

    def execute_query_pandas(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """Execute SQL query and return pandas DataFrame"""
        if not self.engine:
            raise Exception("SQLAlchemy engine not available")
        try:
            if params:
                return pd.read_sql(query, self.engine, params=params)
            else:
                return pd.read_sql(query, self.engine)
        except Exception as e:
            self.logger.error(f"Pandas query execution failed: {str(e)}")
            raise

    def execute_procedure(
        self, procedure_name: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Execute stored procedure"""
        if not self.connection:
            raise Exception("Not connected to Oracle Database")
        try:
            cursor = self.connection.cursor()
            if params:
                result = cursor.callproc(procedure_name, list(params.values()))
            else:
                result = cursor.callproc(procedure_name)
            cursor.close()
            return result
        except Exception as e:
            self.logger.error(f"Procedure execution failed: {str(e)}")
            raise


class OracleRestAPIConnector:
    """Oracle REST API connector"""

    def __init__(
        self,
        config: IntegrationConfig,
        oracle_config: OracleConfig,
        authenticator: OracleAuthenticator,
    ) -> None:
        self.config = config
        self.oracle_config = oracle_config
        self.authenticator = authenticator
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()

    def get_resource(
        self,
        resource_path: str,
        params: Optional[Dict[str, Any]] = None,
        expand: Optional[List[str]] = None,
        fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get resource from Oracle REST API"""
        try:
            url = f"{self.config.base_url}/fscmRestApi/resources/{self.oracle_config.rest_api_version}/{resource_path}"
            query_params = params or {}
            if expand:
                query_params["expand"] = ",".join(expand)
            if fields:
                query_params["fields"] = ",".join(fields)
            headers = self.authenticator.get_auth_headers()
            headers["Accept"] = "application/json"
            response = self.session.get(url, params=query_params, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"REST API GET failed: {str(e)}")
            raise

    def create_resource(
        self, resource_path: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create resource via Oracle REST API"""
        try:
            url = f"{self.config.base_url}/fscmRestApi/resources/{self.oracle_config.rest_api_version}/{resource_path}"
            headers = self.authenticator.get_auth_headers()
            headers["Content-Type"] = "application/json"
            headers["Accept"] = "application/json"
            response = self.session.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"REST API POST failed: {str(e)}")
            raise

    def update_resource(
        self, resource_path: str, resource_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update resource via Oracle REST API"""
        try:
            url = f"{self.config.base_url}/fscmRestApi/resources/{self.oracle_config.rest_api_version}/{resource_path}/{resource_id}"
            headers = self.authenticator.get_auth_headers()
            headers["Content-Type"] = "application/json"
            headers["Accept"] = "application/json"
            response = self.session.patch(url, json=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"REST API PATCH failed: {str(e)}")
            raise

    def delete_resource(self, resource_path: str, resource_id: str) -> bool:
        """Delete resource via Oracle REST API"""
        try:
            url = f"{self.config.base_url}/fscmRestApi/resources/{self.oracle_config.rest_api_version}/{resource_path}/{resource_id}"
            headers = self.authenticator.get_auth_headers()
            response = self.session.delete(url, headers=headers)
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.error(f"REST API DELETE failed: {str(e)}")
            return False

    def bulk_import(self, import_type: str, data: List[Dict[str, Any]]) -> str:
        """Perform bulk import operation"""
        try:
            csv_buffer = io.StringIO()
            if data:
                writer = csv.DictWriter(csv_buffer, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            csv_content = csv_buffer.getvalue()
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.writestr(f"{import_type}.csv", csv_content)
            zip_content = zip_buffer.getvalue()
            upload_url = f"{self.config.base_url}/fscmRestApi/resources/{self.oracle_config.rest_api_version}/importBulkData"
            headers = self.authenticator.get_auth_headers()
            files = {"file": (f"{import_type}.zip", zip_content, "application/zip")}
            data = {"ImportType": import_type, "FileType": "ZIP"}
            response = self.session.post(
                upload_url, headers=headers, files=files, data=data
            )
            response.raise_for_status()
            result = response.json()
            return result.get("ImportId")
        except Exception as e:
            self.logger.error(f"Bulk import failed: {str(e)}")
            raise

    def get_import_status(self, import_id: str) -> Dict[str, Any]:
        """Get bulk import status"""
        try:
            url = f"{self.config.base_url}/fscmRestApi/resources/{self.oracle_config.rest_api_version}/importBulkData/{import_id}"
            headers = self.authenticator.get_auth_headers()
            headers["Accept"] = "application/json"
            response = self.session.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Import status check failed: {str(e)}")
            raise


class OracleSupplierSync:
    """Oracle Supplier synchronization"""

    def __init__(
        self, rest_connector: OracleRestAPIConnector, data_transformer: DataTransformer
    ) -> None:
        self.rest_connector = rest_connector
        self.data_transformer = data_transformer
        self.logger = logging.getLogger(__name__)

    def sync_suppliers(self, filters: Optional[Dict[str, Any]] = None) -> SyncResult:
        """Sync suppliers from Oracle"""
        start_time = datetime.utcnow()
        records_processed = 0
        records_failed = 0
        errors: List[Any] = []
        try:
            suppliers_data = self.rest_connector.get_resource(
                "suppliers",
                params=filters,
                fields=[
                    "SupplierId",
                    "Supplier",
                    "SupplierNumber",
                    "SupplierType",
                    "CreationDate",
                    "LastUpdateDate",
                ],
            )
            suppliers = suppliers_data.get("items", [])
            for supplier in suppliers:
                try:
                    transformed_supplier = self._transform_supplier(supplier)
                    self._process_supplier(transformed_supplier)
                    records_processed += 1
                except Exception as e:
                    self.logger.error(
                        f"Failed to process supplier {supplier.get('SupplierId')}: {str(e)}"
                    )
                    records_failed += 1
                    errors.append(str(e))
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            return SyncResult(
                system_name="Oracle",
                entity_type="Supplier",
                operation="sync",
                success=records_failed == 0,
                records_processed=records_processed,
                records_failed=records_failed,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                error_message="; ".join(errors) if errors else None,
            )
        except Exception as e:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            return SyncResult(
                system_name="Oracle",
                entity_type="Supplier",
                operation="sync",
                success=False,
                records_processed=records_processed,
                records_failed=records_failed,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                error_message=str(e),
            )

    def _transform_supplier(self, supplier: Dict[str, Any]) -> Dict[str, Any]:
        """Transform Oracle supplier data"""
        return {
            "external_id": supplier["SupplierId"],
            "supplier_name": supplier["Supplier"],
            "supplier_number": supplier["SupplierNumber"],
            "supplier_type": supplier["SupplierType"],
            "created_date": supplier["CreationDate"],
            "modified_date": supplier["LastUpdateDate"],
            "source_system": "Oracle",
        }

    def _process_supplier(self, supplier: Dict[str, Any]) -> Any:
        """Process supplier (implement based on your system)"""
        self.logger.info(f"Processing supplier: {supplier['external_id']}")


class OracleFinancialSync:
    """Oracle Financial data synchronization"""

    def __init__(
        self,
        rest_connector: OracleRestAPIConnector,
        db_connector: OracleDatabaseConnector,
        data_transformer: DataTransformer,
    ) -> None:
        self.rest_connector = rest_connector
        self.db_connector = db_connector
        self.data_transformer = data_transformer
        self.logger = logging.getLogger(__name__)

    def sync_invoices(
        self, date_from: Optional[str] = None, date_to: Optional[str] = None
    ) -> SyncResult:
        """Sync invoices from Oracle"""
        start_time = datetime.utcnow()
        records_processed = 0
        records_failed = 0
        try:
            filters: Dict[str, Any] = {}
            if date_from:
                filters["q"] = f"InvoiceDate >= '{date_from}'"
            if date_to:
                if "q" in filters:
                    filters["q"] += f" and InvoiceDate <= '{date_to}'"
                else:
                    filters["q"] = f"InvoiceDate <= '{date_to}'"
            invoices_data = self.rest_connector.get_resource(
                "invoices",
                params=filters,
                fields=[
                    "InvoiceId",
                    "InvoiceNumber",
                    "InvoiceAmount",
                    "InvoiceDate",
                    "SupplierId",
                    "InvoiceCurrency",
                    "CreationDate",
                ],
            )
            invoices = invoices_data.get("items", [])
            for invoice in invoices:
                try:
                    transformed_invoice = self._transform_invoice(invoice)
                    self._process_invoice(transformed_invoice)
                    records_processed += 1
                except Exception as e:
                    self.logger.error(
                        f"Failed to process invoice {invoice.get('InvoiceId')}: {str(e)}"
                    )
                    records_failed += 1
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            return SyncResult(
                system_name="Oracle",
                entity_type="Invoice",
                operation="sync",
                success=records_failed == 0,
                records_processed=records_processed,
                records_failed=records_failed,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
            )
        except Exception as e:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            return SyncResult(
                system_name="Oracle",
                entity_type="Invoice",
                operation="sync",
                success=False,
                records_processed=records_processed,
                records_failed=records_failed,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                error_message=str(e),
            )

    def sync_general_ledger(self, ledger_id: str, period_name: str) -> SyncResult:
        """Sync General Ledger data from Oracle Database"""
        start_time = datetime.utcnow()
        records_processed = 0
        records_failed = 0
        try:
            query = "\n            SELECT\n                je_header_id,\n                je_line_num,\n                ledger_id,\n                period_name,\n                code_combination_id,\n                entered_dr,\n                entered_cr,\n                accounted_dr,\n                accounted_cr,\n                creation_date,\n                last_update_date\n            FROM gl_je_lines\n            WHERE ledger_id = :ledger_id\n            AND period_name = :period_name\n            "
            params = {"ledger_id": ledger_id, "period_name": period_name}
            gl_data = self.db_connector.execute_query(query, params)
            for gl_entry in gl_data:
                try:
                    transformed_entry = self._transform_gl_entry(gl_entry)
                    self._process_gl_entry(transformed_entry)
                    records_processed += 1
                except Exception as e:
                    self.logger.error(f"Failed to process GL entry: {str(e)}")
                    records_failed += 1
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            return SyncResult(
                system_name="Oracle",
                entity_type="GeneralLedger",
                operation="sync",
                success=records_failed == 0,
                records_processed=records_processed,
                records_failed=records_failed,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
            )
        except Exception as e:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            return SyncResult(
                system_name="Oracle",
                entity_type="GeneralLedger",
                operation="sync",
                success=False,
                records_processed=records_processed,
                records_failed=records_failed,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                error_message=str(e),
            )

    def _transform_invoice(self, invoice: Dict[str, Any]) -> Dict[str, Any]:
        """Transform Oracle invoice data"""
        return {
            "external_id": invoice["InvoiceId"],
            "invoice_number": invoice["InvoiceNumber"],
            "amount": (
                float(invoice["InvoiceAmount"]) if invoice["InvoiceAmount"] else 0.0
            ),
            "invoice_date": invoice["InvoiceDate"],
            "supplier_id": invoice["SupplierId"],
            "currency": invoice["InvoiceCurrency"],
            "created_date": invoice["CreationDate"],
            "source_system": "Oracle",
        }

    def _transform_gl_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Transform Oracle GL entry"""
        return {
            "journal_entry_id": entry["JE_HEADER_ID"],
            "line_number": entry["JE_LINE_NUM"],
            "ledger_id": entry["LEDGER_ID"],
            "period_name": entry["PERIOD_NAME"],
            "account_id": entry["CODE_COMBINATION_ID"],
            "debit_amount": float(entry["ENTERED_DR"]) if entry["ENTERED_DR"] else 0.0,
            "credit_amount": float(entry["ENTERED_CR"]) if entry["ENTERED_CR"] else 0.0,
            "accounted_debit": (
                float(entry["ACCOUNTED_DR"]) if entry["ACCOUNTED_DR"] else 0.0
            ),
            "accounted_credit": (
                float(entry["ACCOUNTED_CR"]) if entry["ACCOUNTED_CR"] else 0.0
            ),
            "created_date": entry["CREATION_DATE"],
            "modified_date": entry["LAST_UPDATE_DATE"],
            "source_system": "Oracle",
        }

    def _process_invoice(self, invoice: Dict[str, Any]) -> Any:
        """Process invoice (implement based on your system)"""
        self.logger.info(f"Processing invoice: {invoice['external_id']}")

    def _process_gl_entry(self, entry: Dict[str, Any]) -> Any:
        """Process GL entry (implement based on your system)"""
        self.logger.info(f"Processing GL entry: {entry['journal_entry_id']}")


class OracleIntegration(BaseIntegration):
    """Main Oracle integration class"""

    def __init__(
        self,
        config: IntegrationConfig,
        oracle_config: OracleConfig,
        db_session: Any = None,
        redis_client: Any = None,
    ) -> None:
        super().__init__(config, db_session, redis_client)
        self.oracle_config = oracle_config
        self.authenticator = OracleAuthenticator(config, oracle_config)
        if oracle_config.enable_database:
            self.db_connector = OracleDatabaseConnector(config, oracle_config)
        else:
            self.db_connector = None
        if oracle_config.enable_rest_api:
            self.rest_connector = OracleRestAPIConnector(
                config, oracle_config, self.authenticator
            )
        else:
            self.rest_connector = None
        if self.rest_connector:
            self.supplier_sync = OracleSupplierSync(
                self.rest_connector, self.data_transformer
            )
            self.financial_sync = OracleFinancialSync(
                self.rest_connector, self.db_connector, self.data_transformer
            )

    def authenticate(self) -> bool:
        """Authenticate with Oracle system"""
        return self.authenticator.authenticate()

    def test_connection(self) -> bool:
        """Test connection to Oracle system"""
        try:
            if self.rest_connector:
                self.rest_connector.get_resource("users", params={"limit": 1})
                return True
            elif self.db_connector:
                return self.db_connector.connect()
            else:
                return False
        except Exception as e:
            self.logger.error(f"Oracle connection test failed: {str(e)}")
            return False

    def sync_data(self, entity_type: str, **kwargs) -> SyncResult:
        """Sync data with Oracle system"""
        try:
            if entity_type == "suppliers":
                return self.supplier_sync.sync_suppliers(kwargs.get("filters"))
            elif entity_type == "invoices":
                return self.financial_sync.sync_invoices(
                    kwargs.get("date_from"), kwargs.get("date_to")
                )
            elif entity_type == "general_ledger":
                return self.financial_sync.sync_general_ledger(
                    kwargs.get("ledger_id", "1"),
                    kwargs.get(
                        "period_name",
                        f"{datetime.now().year}-{datetime.now().month:02d}",
                    ),
                )
            else:
                raise ValueError(f"Unsupported entity type: {entity_type}")
        except Exception as e:
            return SyncResult(
                system_name="Oracle",
                entity_type=entity_type,
                operation="sync",
                success=False,
                records_processed=0,
                records_failed=0,
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow(),
                duration_seconds=0,
                error_message=str(e),
            )

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        return self.authenticator.get_auth_headers()

    def _process_webhook_data(self, payload: Dict[str, Any]) -> Any:
        """Process Oracle webhook data"""
        try:
            event_type = payload.get("eventType")
            if event_type == "Supplier.Created":
                self._handle_supplier_created(payload)
            elif event_type == "Supplier.Updated":
                self._handle_supplier_updated(payload)
            elif event_type == "Invoice.Created":
                self._handle_invoice_created(payload)
            else:
                self.logger.warning(f"Unknown Oracle event type: {event_type}")
        except Exception as e:
            self.logger.error(f"Oracle webhook processing failed: {str(e)}")

    def _handle_supplier_created(self, payload: Dict[str, Any]) -> Any:
        """Handle supplier created event"""
        supplier_id = payload.get("supplierId")
        self.logger.info(f"Supplier created: {supplier_id}")
        if self.supplier_sync:
            self.supplier_sync.sync_suppliers({"SupplierId": supplier_id})

    def _handle_supplier_updated(self, payload: Dict[str, Any]) -> Any:
        """Handle supplier updated event"""
        supplier_id = payload.get("supplierId")
        self.logger.info(f"Supplier updated: {supplier_id}")
        if self.supplier_sync:
            self.supplier_sync.sync_suppliers({"SupplierId": supplier_id})

    def _handle_invoice_created(self, payload: Dict[str, Any]) -> Any:
        """Handle invoice created event"""
        invoice_id = payload.get("invoiceId")
        self.logger.info(f"Invoice created: {invoice_id}")
        if self.financial_sync:
            self.financial_sync.sync_invoices(
                date_from=datetime.now().strftime("%Y-%m-%d"),
                date_to=datetime.now().strftime("%Y-%m-%d"),
            )

    def get_supplier(self, supplier_id: str) -> Optional[Dict[str, Any]]:
        """Get specific supplier"""
        if not self.rest_connector:
            return None
        try:
            suppliers_data = self.rest_connector.get_resource(
                "suppliers", params={"q": f"SupplierId = {supplier_id}"}
            )
            suppliers = suppliers_data.get("items", [])
            return suppliers[0] if suppliers else None
        except Exception as e:
            self.logger.error(f"Failed to get supplier {supplier_id}: {str(e)}")
            return None

    def create_supplier(self, supplier_data: Dict[str, Any]) -> Optional[str]:
        """Create new supplier in Oracle"""
        if not self.rest_connector:
            return None
        try:
            result = self.rest_connector.create_resource("suppliers", supplier_data)
            return result.get("SupplierId")
        except Exception as e:
            self.logger.error(f"Failed to create supplier: {str(e)}")
            return None

    def bulk_import_suppliers(self, suppliers: List[Dict[str, Any]]) -> Optional[str]:
        """Bulk import suppliers"""
        if not self.rest_connector:
            return None
        try:
            import_id = self.rest_connector.bulk_import("Supplier", suppliers)
            return import_id
        except Exception as e:
            self.logger.error(f"Failed to bulk import suppliers: {str(e)}")
            return None

    def get_financial_data(self, ledger_id: str, period_name: str) -> pd.DataFrame:
        """Get financial data as pandas DataFrame"""
        if not self.db_connector:
            return pd.DataFrame()
        try:
            query = "\n            SELECT\n                gl.je_header_id,\n                gl.je_line_num,\n                gl.ledger_id,\n                gl.period_name,\n                gcc.segment1 as company,\n                gcc.segment2 as account,\n                gcc.segment3 as cost_center,\n                gl.entered_dr,\n                gl.entered_cr,\n                gl.description,\n                gl.creation_date\n            FROM gl_je_lines gl\n            JOIN gl_code_combinations gcc ON gl.code_combination_id = gcc.code_combination_id\n            WHERE gl.ledger_id = :ledger_id\n            AND gl.period_name = :period_name\n            "
            params = {"ledger_id": ledger_id, "period_name": period_name}
            return self.db_connector.execute_query_pandas(query, params)
        except Exception as e:
            self.logger.error(f"Failed to get financial data: {str(e)}")
            return pd.DataFrame()


def create_oracle_integration(system_type: str = "ERP_CLOUD") -> OracleIntegration:
    """Factory function to create Oracle integration"""
    config = IntegrationConfig(
        system_name="Oracle",
        base_url=os.getenv("ORACLE_BASE_URL"),
        auth_method=AuthMethod(os.getenv("ORACLE_AUTH_METHOD", "basic")),
        credentials={
            "username": os.getenv("ORACLE_USERNAME"),
            "password": os.getenv("ORACLE_PASSWORD"),
            "client_id": os.getenv("ORACLE_CLIENT_ID"),
            "client_secret": os.getenv("ORACLE_CLIENT_SECRET"),
            "private_key": os.getenv("ORACLE_PRIVATE_KEY"),
            "scope": os.getenv("ORACLE_SCOPE"),
        },
        timeout=int(os.getenv("ORACLE_TIMEOUT", "30")),
        rate_limit=int(os.getenv("ORACLE_RATE_LIMIT", "100")),
        enable_caching=True,
        enable_circuit_breaker=True,
        enable_monitoring=True,
    )
    oracle_config = OracleConfig(
        oracle_system=system_type,
        database_host=os.getenv("ORACLE_DB_HOST"),
        database_port=int(os.getenv("ORACLE_DB_PORT", "1521")),
        database_service_name=os.getenv("ORACLE_DB_SERVICE_NAME"),
        database_sid=os.getenv("ORACLE_DB_SID"),
        enable_database=os.getenv("ORACLE_ENABLE_DATABASE", "false").lower() == "true",
        enable_rest_api=os.getenv("ORACLE_ENABLE_REST_API", "true").lower() == "true",
        enable_soap_api=os.getenv("ORACLE_ENABLE_SOAP_API", "false").lower() == "true",
        enable_bulk_import=os.getenv("ORACLE_ENABLE_BULK_IMPORT", "true").lower()
        == "true",
    )
    return OracleIntegration(config, oracle_config)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    oracle_integration = create_oracle_integration("ERP_CLOUD")
    if oracle_integration.test_connection():
        logger.info("Oracle connection successful")
        result = oracle_integration.sync_data("suppliers")
        logger.info(f"Supplier sync result: {result}")
        result = oracle_integration.sync_data(
            "invoices", date_from="2024-01-01", date_to="2024-12-31"
        )
        logger.info(f"Invoice sync result: {result}")
    else:
        logger.info("Oracle connection failed")
