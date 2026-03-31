"""
SAP Enterprise Integration for NexaFi
Comprehensive integration with SAP ERP, S/4HANA, SuccessFactors, and other SAP systems
"""

import base64
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
from nexafi_logging.logger import get_logger
from oauthlib.oauth2 import WebApplicationClient
from pyrfc import Connection
from requests.auth import HTTPBasicAuth

from ..shared.base_integration import (
    AuthMethod,
    BaseIntegration,
    DataTransformer,
    IntegrationConfig,
    SyncResult,
)

logger = get_logger(__name__)


@dataclass
class SAPConfig:
    """SAP-specific configuration"""

    sap_system: str
    sap_client: str = "100"
    sap_language: str = "EN"
    rfc_destination: Optional[str] = None
    odata_service_url: Optional[str] = None
    soap_service_url: Optional[str] = None
    idoc_port: Optional[str] = None
    enable_rfc: bool = True
    enable_odata: bool = True
    enable_soap: bool = False
    enable_idoc: bool = False
    custom_fields: Optional[Dict[str, str]] = None
    business_partner_config: Optional[Dict[str, Any]] = None
    financial_config: Optional[Dict[str, Any]] = None


class SAPAuthenticator:
    """SAP authentication handler"""

    def __init__(self, config: IntegrationConfig, sap_config: SAPConfig) -> None:
        self.config = config
        self.sap_config = sap_config
        self.logger = logging.getLogger(__name__)
        self.access_token = None
        self.token_expires_at = None
        self.csrf_token = None

    def authenticate(self) -> bool:
        """Authenticate with SAP system"""
        try:
            if self.config.auth_method == AuthMethod.OAUTH2:
                return self._oauth2_authenticate()
            elif self.config.auth_method == AuthMethod.BASIC:
                return self._basic_authenticate()
            elif self.config.auth_method == AuthMethod.SAML:
                return self._saml_authenticate()
            elif self.config.auth_method == AuthMethod.CERTIFICATE:
                return self._certificate_authenticate()
            else:
                self.logger.error(f"Unsupported auth method: {self.config.auth_method}")
                return False
        except Exception as e:
            self.logger.error(f"SAP authentication failed: {str(e)}")
            return False

    def _oauth2_authenticate(self) -> bool:
        """OAuth2 authentication for SAP systems"""
        try:
            if self.sap_config.sap_system == "SUCCESSFACTORS":
                return self._successfactors_oauth2()
            elif self.sap_config.sap_system == "S4HANA":
                return self._s4hana_oauth2()
            else:
                return self._generic_oauth2()
        except Exception as e:
            self.logger.error(f"OAuth2 authentication failed: {str(e)}")
            return False

    def _successfactors_oauth2(self) -> bool:
        """SuccessFactors OAuth2 authentication"""
        token_url = f"{self.config.base_url}/oauth/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.config.credentials["client_id"],
            "client_secret": self.config.credentials["client_secret"],
            "company_id": self.config.credentials.get("company_id"),
            "user_type": "user",
        }
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        token_data = response.json()
        self.access_token = token_data["access_token"]
        self.token_expires_at = datetime.utcnow() + timedelta(
            seconds=token_data["expires_in"]
        )
        return True

    def _s4hana_oauth2(self) -> bool:
        """S/4HANA OAuth2 authentication"""
        token_url = f"{self.config.base_url}/sap/bc/sec/oauth2/token"
        auth = HTTPBasicAuth(
            self.config.credentials["client_id"],
            self.config.credentials["client_secret"],
        )
        data = {
            "grant_type": "client_credentials",
            "scope": "UIWC:CC_VIEW UIWC:CC_MAINTAIN",
        }
        response = requests.post(token_url, data=data, auth=auth)
        response.raise_for_status()
        token_data = response.json()
        self.access_token = token_data["access_token"]
        self.token_expires_at = datetime.utcnow() + timedelta(
            seconds=token_data["expires_in"]
        )
        return True

    def _generic_oauth2(self) -> bool:
        """Generic OAuth2 authentication"""
        client = WebApplicationClient(self.config.credentials["client_id"])
        token_url = f"{self.config.base_url}/oauth2/token"
        token = client.prepare_request_body(
            grant_type="client_credentials",
            scope=self.config.credentials.get("scope", ""),
        )
        auth = HTTPBasicAuth(
            self.config.credentials["client_id"],
            self.config.credentials["client_secret"],
        )
        response = requests.post(token_url, data=token, auth=auth)
        response.raise_for_status()
        token_data = response.json()
        self.access_token = token_data["access_token"]
        self.token_expires_at = datetime.utcnow() + timedelta(
            seconds=token_data["expires_in"]
        )
        return True

    def _basic_authenticate(self) -> bool:
        """Basic authentication for SAP systems"""
        test_url = (
            f"{self.config.base_url}/sap/opu/odata/sap/API_BUSINESS_PARTNER/$metadata"
        )
        auth = HTTPBasicAuth(
            self.config.credentials["username"], self.config.credentials["password"]
        )
        response = requests.get(test_url, auth=auth, timeout=self.config.timeout)
        return response.status_code == 200

    def _saml_authenticate(self) -> bool:
        """SAML authentication for SAP systems"""
        saml_endpoint = f"{self.config.base_url}/sap/bc/sec/saml2/idp/sso"
        assertion = self._create_saml_assertion()
        response = requests.post(
            saml_endpoint, data={"SAMLResponse": assertion}, timeout=self.config.timeout
        )
        return response.status_code == 200

    def _certificate_authenticate(self) -> bool:
        """Certificate-based authentication"""
        cert_file = self.config.credentials.get("cert_file")
        key_file = self.config.credentials.get("key_file")
        if not cert_file or not key_file:
            return False
        test_url = (
            f"{self.config.base_url}/sap/opu/odata/sap/API_BUSINESS_PARTNER/$metadata"
        )
        response = requests.get(
            test_url, cert=(cert_file, key_file), timeout=self.config.timeout
        )
        return response.status_code == 200

    def _create_saml_assertion(self) -> str:
        """Create SAML assertion (simplified)"""
        assertion_template = '\n        <saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">\n            <saml:Subject>\n                <saml:NameID>{username}</saml:NameID>\n            </saml:Subject>\n            <saml:AttributeStatement>\n                <saml:Attribute Name="company">\n                    <saml:AttributeValue>{company}</saml:AttributeValue>\n                </saml:Attribute>\n            </saml:AttributeStatement>\n        </saml:Assertion>\n        '
        assertion = assertion_template.format(
            username=self.config.credentials["username"],
            company=self.config.credentials.get("company", ""),
        )
        return base64.b64encode(assertion.encode()).decode()

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
        elif self.config.auth_method == AuthMethod.API_KEY:
            headers["X-API-Key"] = self.config.credentials["api_key"]
        if self.csrf_token:
            headers["X-CSRF-Token"] = self.csrf_token
        return headers

    def get_csrf_token(self) -> str:
        """Get CSRF token for SAP OData services"""
        if self.csrf_token:
            return self.csrf_token
        try:
            csrf_url = f"{self.config.base_url}/sap/opu/odata/sap/API_BUSINESS_PARTNER/"
            headers = self.get_auth_headers()
            headers["X-CSRF-Token"] = "Fetch"
            response = requests.get(csrf_url, headers=headers)
            if "X-CSRF-Token" in response.headers:
                self.csrf_token = response.headers["X-CSRF-Token"]
                return self.csrf_token
        except Exception as e:
            self.logger.error(f"Failed to get CSRF token: {str(e)}")
        return ""

    def is_token_valid(self) -> bool:
        """Check if current token is valid"""
        if not self.access_token:
            return False
        if self.token_expires_at and datetime.utcnow() >= self.token_expires_at:
            return False
        return True


class SAPRFCConnector:
    """SAP RFC connector for direct system access"""

    def __init__(self, config: IntegrationConfig, sap_config: SAPConfig) -> None:
        self.config = config
        self.sap_config = sap_config
        self.logger = logging.getLogger(__name__)
        self.connection = None

    def connect(self) -> bool:
        """Connect to SAP system via RFC"""
        try:
            connection_params = {
                "ashost": self.config.base_url.replace("http://", "").replace(
                    "https://", ""
                ),
                "sysnr": self.config.credentials.get("system_number", "00"),
                "client": self.sap_config.sap_client,
                "user": self.config.credentials["username"],
                "passwd": self.config.credentials["password"],
                "lang": self.sap_config.sap_language,
            }
            self.connection = Connection(**connection_params)
            return True
        except Exception as e:
            self.logger.error(f"RFC connection failed: {str(e)}")
            return False

    def disconnect(self) -> Any:
        """Disconnect from SAP system"""
        if self.connection:
            self.connection.close()
            self.connection = None

    def call_function(self, function_name: str, **kwargs) -> Dict[str, Any]:
        """Call SAP function module"""
        if not self.connection:
            raise Exception("Not connected to SAP system")
        try:
            result = self.connection.call(function_name, **kwargs)
            return result
        except Exception as e:
            self.logger.error(f"RFC function call failed: {str(e)}")
            raise

    def read_table(
        self,
        table_name: str,
        fields: Optional[List[str]] = None,
        where_clause: Optional[str] = None,
        max_rows: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Read data from SAP table"""
        try:
            options: List[Any] = []
            if where_clause:
                options.append({"TEXT": where_clause})
            fields_param: List[Any] = []
            if fields:
                fields_param = [{"FIELDNAME": field} for field in fields]
            result = self.call_function(
                "RFC_READ_TABLE",
                QUERY_TABLE=table_name,
                DELIMITER="|",
                FIELDS=fields_param,
                OPTIONS=options,
                ROWCOUNT=max_rows,
            )
            data: List[Any] = []
            field_names = [field["FIELDNAME"] for field in result["FIELDS"]]
            for row in result["DATA"]:
                row_data = row["WA"].split("|")
                record = dict(zip(field_names, row_data))
                data.append(record)
            return data
        except Exception as e:
            self.logger.error(f"Table read failed: {str(e)}")
            raise


class SAPODataConnector:
    """SAP OData connector for modern API access"""

    def __init__(
        self,
        config: IntegrationConfig,
        sap_config: SAPConfig,
        authenticator: SAPAuthenticator,
    ) -> None:
        self.config = config
        self.sap_config = sap_config
        self.authenticator = authenticator
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()

    def get_entity_set(
        self,
        service_name: str,
        entity_set: str,
        filters: Optional[Dict[str, Any]] = None,
        select: Optional[List[str]] = None,
        top: Optional[int] = None,
        skip: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get data from OData entity set"""
        try:
            url = (
                f"{self.config.base_url}/sap/opu/odata/sap/{service_name}/{entity_set}"
            )
            params: Dict[str, Any] = {}
            if filters:
                filter_parts: List[Any] = []
                for field, value in filters.items():
                    if isinstance(value, str):
                        filter_parts.append(f"{field} eq '{value}'")
                    else:
                        filter_parts.append(f"{field} eq {value}")
                params["$filter"] = " and ".join(filter_parts)
            if select:
                params["$select"] = ",".join(select)
            if top:
                params["$top"] = top
            if skip:
                params["$skip"] = skip
            headers = self.authenticator.get_auth_headers()
            headers["Accept"] = "application/json"
            response = self.session.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("d", {}).get("results", [])
        except Exception as e:
            self.logger.error(f"OData query failed: {str(e)}")
            raise

    def create_entity(
        self, service_name: str, entity_set: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create new entity via OData"""
        try:
            url = (
                f"{self.config.base_url}/sap/opu/odata/sap/{service_name}/{entity_set}"
            )
            headers = self.authenticator.get_auth_headers()
            headers["Content-Type"] = "application/json"
            headers["Accept"] = "application/json"
            csrf_token = self.authenticator.get_csrf_token()
            if csrf_token:
                headers["X-CSRF-Token"] = csrf_token
            response = self.session.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response.json().get("d", {})
        except Exception as e:
            self.logger.error(f"OData create failed: {str(e)}")
            raise

    def update_entity(
        self, service_name: str, entity_set: str, key: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update entity via OData"""
        try:
            url = f"{self.config.base_url}/sap/opu/odata/sap/{service_name}/{entity_set}('{key}')"
            headers = self.authenticator.get_auth_headers()
            headers["Content-Type"] = "application/json"
            headers["Accept"] = "application/json"
            csrf_token = self.authenticator.get_csrf_token()
            if csrf_token:
                headers["X-CSRF-Token"] = csrf_token
            response = self.session.patch(url, json=data, headers=headers)
            response.raise_for_status()
            return response.json().get("d", {})
        except Exception as e:
            self.logger.error(f"OData update failed: {str(e)}")
            raise

    def delete_entity(self, service_name: str, entity_set: str, key: str) -> bool:
        """Delete entity via OData"""
        try:
            url = f"{self.config.base_url}/sap/opu/odata/sap/{service_name}/{entity_set}('{key}')"
            headers = self.authenticator.get_auth_headers()
            csrf_token = self.authenticator.get_csrf_token()
            if csrf_token:
                headers["X-CSRF-Token"] = csrf_token
            response = self.session.delete(url, headers=headers)
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.error(f"OData delete failed: {str(e)}")
            return False


class SAPBusinessPartnerSync:
    """SAP Business Partner synchronization"""

    def __init__(
        self, odata_connector: SAPODataConnector, data_transformer: DataTransformer
    ) -> None:
        self.odata_connector = odata_connector
        self.data_transformer = data_transformer
        self.logger = logging.getLogger(__name__)

    def sync_business_partners(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """Sync business partners from SAP"""
        start_time = datetime.utcnow()
        records_processed = 0
        records_failed = 0
        errors: List[Any] = []
        try:
            business_partners = self.odata_connector.get_entity_set(
                "API_BUSINESS_PARTNER",
                "A_BusinessPartner",
                filters=filters,
                select=[
                    "BusinessPartner",
                    "BusinessPartnerCategory",
                    "BusinessPartnerFullName",
                    "CreationDate",
                    "CreatedByUser",
                    "LastChangeDate",
                    "LastChangedByUser",
                ],
            )
            for bp in business_partners:
                try:
                    transformed_bp = self._transform_business_partner(bp)
                    self._process_business_partner(transformed_bp)
                    records_processed += 1
                except Exception as e:
                    self.logger.error(
                        f"Failed to process business partner {bp.get('BusinessPartner')}: {str(e)}"
                    )
                    records_failed += 1
                    errors.append(str(e))
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            return SyncResult(
                system_name="SAP",
                entity_type="BusinessPartner",
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
                system_name="SAP",
                entity_type="BusinessPartner",
                operation="sync",
                success=False,
                records_processed=records_processed,
                records_failed=records_failed,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                error_message=str(e),
            )

    def _transform_business_partner(self, bp: Dict[str, Any]) -> Dict[str, Any]:
        """Transform SAP business partner data"""
        return {
            "external_id": bp["BusinessPartner"],
            "category": bp["BusinessPartnerCategory"],
            "name": bp["BusinessPartnerFullName"],
            "created_date": bp["CreationDate"],
            "created_by": bp["CreatedByUser"],
            "modified_date": bp["LastChangeDate"],
            "modified_by": bp["LastChangedByUser"],
            "source_system": "SAP",
        }

    def _process_business_partner(self, bp: Dict[str, Any]) -> Any:
        """Process business partner (implement based on your system)"""
        self.logger.info(f"Processing business partner: {bp['external_id']}")


class SAPFinancialSync:
    """SAP Financial data synchronization"""

    def __init__(
        self,
        odata_connector: SAPODataConnector,
        rfc_connector: SAPRFCConnector,
        data_transformer: DataTransformer,
    ) -> None:
        self.odata_connector = odata_connector
        self.rfc_connector = rfc_connector
        self.data_transformer = data_transformer
        self.logger = logging.getLogger(__name__)

    def sync_general_ledger(
        self,
        company_code: str,
        fiscal_year: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> SyncResult:
        """Sync General Ledger data from SAP"""
        start_time = datetime.utcnow()
        records_processed = 0
        records_failed = 0
        try:
            where_conditions = [f"BUKRS = '{company_code}'", f"GJAHR = '{fiscal_year}'"]
            if date_from:
                where_conditions.append(f"BUDAT >= '{date_from}'")
            if date_to:
                where_conditions.append(f"BUDAT <= '{date_to}'")
            where_clause = " AND ".join(where_conditions)
            gl_data = self.rfc_connector.read_table(
                "BSEG",
                fields=[
                    "BUKRS",
                    "BELNR",
                    "GJAHR",
                    "BUZEI",
                    "HKONT",
                    "DMBTR",
                    "WRBTR",
                    "BUDAT",
                ],
                where_clause=where_clause,
                max_rows=10000,
            )
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
                system_name="SAP",
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
                system_name="SAP",
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

    def _transform_gl_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Transform SAP GL entry"""
        return {
            "company_code": entry["BUKRS"],
            "document_number": entry["BELNR"],
            "fiscal_year": entry["GJAHR"],
            "line_item": entry["BUZEI"],
            "account": entry["HKONT"],
            "amount_local": float(entry["DMBTR"]) if entry["DMBTR"] else 0.0,
            "amount_document": float(entry["WRBTR"]) if entry["WRBTR"] else 0.0,
            "posting_date": entry["BUDAT"],
            "source_system": "SAP",
        }

    def _process_gl_entry(self, entry: Dict[str, Any]) -> Any:
        """Process GL entry (implement based on your system)"""
        self.logger.info(f"Processing GL entry: {entry['document_number']}")


class SAPIntegration(BaseIntegration):
    """Main SAP integration class"""

    def __init__(
        self,
        config: IntegrationConfig,
        sap_config: SAPConfig,
        db_session: Any = None,
        redis_client: Any = None,
    ) -> None:
        super().__init__(config, db_session, redis_client)
        self.sap_config = sap_config
        self.authenticator = SAPAuthenticator(config, sap_config)
        if sap_config.enable_rfc:
            self.rfc_connector = SAPRFCConnector(config, sap_config)
        else:
            self.rfc_connector = None
        if sap_config.enable_odata:
            self.odata_connector = SAPODataConnector(
                config, sap_config, self.authenticator
            )
        else:
            self.odata_connector = None
        if self.odata_connector:
            self.bp_sync = SAPBusinessPartnerSync(
                self.odata_connector, self.data_transformer
            )
            self.financial_sync = SAPFinancialSync(
                self.odata_connector, self.rfc_connector, self.data_transformer
            )

    def authenticate(self) -> bool:
        """Authenticate with SAP system"""
        return self.authenticator.authenticate()

    def test_connection(self) -> bool:
        """Test connection to SAP system"""
        try:
            if self.odata_connector:
                self.odata_connector.get_entity_set(
                    "API_BUSINESS_PARTNER", "A_BusinessPartner", top=1
                )
                return True
            elif self.rfc_connector:
                return self.rfc_connector.connect()
            else:
                return False
        except Exception as e:
            self.logger.error(f"SAP connection test failed: {str(e)}")
            return False

    def sync_data(self, entity_type: str, **kwargs) -> SyncResult:
        """Sync data with SAP system"""
        try:
            if entity_type == "business_partners":
                return self.bp_sync.sync_business_partners(kwargs.get("filters"))
            elif entity_type == "general_ledger":
                return self.financial_sync.sync_general_ledger(
                    kwargs.get("company_code", "1000"),
                    kwargs.get("fiscal_year", str(datetime.now().year)),
                    kwargs.get("date_from"),
                    kwargs.get("date_to"),
                )
            else:
                raise ValueError(f"Unsupported entity type: {entity_type}")
        except Exception as e:
            return SyncResult(
                system_name="SAP",
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
        """Process SAP webhook data"""
        try:
            event_type = payload.get("eventType")
            if event_type == "BusinessPartner.Created":
                self._handle_bp_created(payload)
            elif event_type == "BusinessPartner.Updated":
                self._handle_bp_updated(payload)
            elif event_type == "Document.Posted":
                self._handle_document_posted(payload)
            else:
                self.logger.warning(f"Unknown SAP event type: {event_type}")
        except Exception as e:
            self.logger.error(f"SAP webhook processing failed: {str(e)}")

    def _handle_bp_created(self, payload: Dict[str, Any]) -> Any:
        """Handle business partner created event"""
        bp_id = payload.get("businessPartner")
        self.logger.info(f"Business partner created: {bp_id}")
        if self.bp_sync:
            self.bp_sync.sync_business_partners({"BusinessPartner": bp_id})

    def _handle_bp_updated(self, payload: Dict[str, Any]) -> Any:
        """Handle business partner updated event"""
        bp_id = payload.get("businessPartner")
        self.logger.info(f"Business partner updated: {bp_id}")
        if self.bp_sync:
            self.bp_sync.sync_business_partners({"BusinessPartner": bp_id})

    def _handle_document_posted(self, payload: Dict[str, Any]) -> Any:
        """Handle document posted event"""
        doc_number = payload.get("documentNumber")
        company_code = payload.get("companyCode")
        fiscal_year = payload.get("fiscalYear")
        self.logger.info(f"Document posted: {doc_number}")
        if self.financial_sync:
            self.financial_sync.sync_general_ledger(
                company_code,
                fiscal_year,
                date_from=datetime.now().strftime("%Y%m%d"),
                date_to=datetime.now().strftime("%Y%m%d"),
            )

    def get_business_partner(self, bp_id: str) -> Optional[Dict[str, Any]]:
        """Get specific business partner"""
        if not self.odata_connector:
            return None
        try:
            partners = self.odata_connector.get_entity_set(
                "API_BUSINESS_PARTNER",
                "A_BusinessPartner",
                filters={"BusinessPartner": bp_id},
            )
            return partners[0] if partners else None
        except Exception as e:
            self.logger.error(f"Failed to get business partner {bp_id}: {str(e)}")
            return None

    def create_business_partner(self, bp_data: Dict[str, Any]) -> Optional[str]:
        """Create new business partner in SAP"""
        if not self.odata_connector:
            return None
        try:
            result = self.odata_connector.create_entity(
                "API_BUSINESS_PARTNER", "A_BusinessPartner", bp_data
            )
            return result.get("BusinessPartner")
        except Exception as e:
            self.logger.error(f"Failed to create business partner: {str(e)}")
            return None

    def get_financial_documents(
        self, company_code: str, fiscal_year: str, document_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get financial documents from SAP"""
        if not self.rfc_connector:
            return []
        try:
            where_conditions = [f"BUKRS = '{company_code}'", f"GJAHR = '{fiscal_year}'"]
            if document_type:
                where_conditions.append(f"BLART = '{document_type}'")
            where_clause = " AND ".join(where_conditions)
            documents = self.rfc_connector.read_table(
                "BKPF",
                fields=["BUKRS", "BELNR", "GJAHR", "BLART", "BLDAT", "BUDAT", "WAERS"],
                where_clause=where_clause,
                max_rows=1000,
            )
            return documents
        except Exception as e:
            self.logger.error(f"Failed to get financial documents: {str(e)}")
            return []


def create_sap_integration(system_type: str = "S4HANA") -> SAPIntegration:
    """Factory function to create SAP integration"""
    config = IntegrationConfig(
        system_name="SAP",
        base_url=os.getenv("SAP_BASE_URL"),
        auth_method=AuthMethod(os.getenv("SAP_AUTH_METHOD", "basic")),
        credentials={
            "username": os.getenv("SAP_USERNAME"),
            "password": os.getenv("SAP_PASSWORD"),
            "client_id": os.getenv("SAP_CLIENT_ID"),
            "client_secret": os.getenv("SAP_CLIENT_SECRET"),
            "system_number": os.getenv("SAP_SYSTEM_NUMBER", "00"),
        },
        timeout=int(os.getenv("SAP_TIMEOUT", "30")),
        rate_limit=int(os.getenv("SAP_RATE_LIMIT", "100")),
        enable_caching=True,
        enable_circuit_breaker=True,
        enable_monitoring=True,
    )
    sap_config = SAPConfig(
        sap_system=system_type,
        sap_client=os.getenv("SAP_CLIENT", "100"),
        sap_language=os.getenv("SAP_LANGUAGE", "EN"),
        enable_rfc=os.getenv("SAP_ENABLE_RFC", "true").lower() == "true",
        enable_odata=os.getenv("SAP_ENABLE_ODATA", "true").lower() == "true",
        enable_soap=os.getenv("SAP_ENABLE_SOAP", "false").lower() == "true",
        enable_idoc=os.getenv("SAP_ENABLE_IDOC", "false").lower() == "true",
    )
    return SAPIntegration(config, sap_config)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sap_integration = create_sap_integration("S4HANA")
    if sap_integration.test_connection():
        logger.info("SAP connection successful")
        result = sap_integration.sync_data("business_partners")
        logger.info(f"Business partner sync result: {result}")
        result = sap_integration.sync_data(
            "general_ledger", company_code="1000", fiscal_year="2024"
        )
        logger.info(f"Financial sync result: {result}")
    else:
        logger.info("SAP connection failed")
