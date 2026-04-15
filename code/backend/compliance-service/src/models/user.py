from typing import Optional

from database.manager import BaseModel


class KYCVerification(BaseModel):
    table_name: Optional[str] = "kyc_verifications"


class AMLCheck(BaseModel):
    table_name: Optional[str] = "aml_checks"


class SanctionsScreening(BaseModel):
    table_name: Optional[str] = "sanctions_screening"


class ComplianceReport(BaseModel):
    table_name: Optional[str] = "compliance_reports"
