from pydantic import BaseModel, Field


class MetricsTransformRequest(BaseModel):
    """Request body for the transform endpoint."""

    region_code: str = Field(...,
                             description="HCS region ID (e.g. 'whdevp-env-5')")
    domain_id: str = Field(..., description="Tenant / VDC domain ID")
    start_time: str = Field(...,
                            description="Period start (YYYY-MM-DD HH:MM:SS)")
    end_time: str = Field(..., description="Period end (YYYY-MM-DD HH:MM:SS)")
    resource_type_code: str = Field(
        ..., description="HCS resource type (e.g. 'hws.resource.type.volume')"
    )
    period: str = Field(
        default="daily", description="hourly | daily | monthly")
    time_zone: str = Field(default="Africa/Lagos", description="Timezone")
    locale: str = Field(default="en_US", description="en_US | zh_CN")
    limit: int = Field(default=1000, ge=1, le=1000, description="Page size")

    # Optional context for FOCUS account fields
    tenant_name: str = Field(
        default="", description="HCS Tenant Name → FOCUS BillingAccountName")
    tenant_id: str = Field(
        default="", description="HCS Tenant ID → FOCUS BillingAccountId")
    vdc_name: str = Field(
        default="", description="VDC Name → FOCUS SubAccountName")
    vdc_id: str = Field(default="", description="VDC ID → FOCUS SubAccountId")
