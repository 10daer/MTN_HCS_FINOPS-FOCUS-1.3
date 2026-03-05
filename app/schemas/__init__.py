"""
Pydantic schemas for the HCS ManageOne metrics API response.

These models represent the raw CDR (Call Detail Record) data returned
by POST /rest/metering/v3.0/query-metrics-data.
"""

from datetime import datetime
from typing import Any
from typing import Optional

from pydantic import BaseModel, Field

class HCSMetricRecord(BaseModel):
    id: str = Field(...)
    record_type: Optional[str] = Field(default=None)
    user_id: Optional[str] = Field(default=None)
    region_code: Optional[str] = Field(default=None)
    cloud_infra_id: Optional[str] = Field(default=None)
    az_code: Optional[str] = Field(default=None)
    cloud_service_type_code: Optional[str] = Field(default=None)
    resource_type_code: Optional[str] = Field(default=None)
    resource_spec_code: Optional[str] = Field(default=None)
    resource_id: Optional[str] = Field(default=None)
    resource_display_name: Optional[str] = Field(default=None)
    bss_params: Optional[str] = Field(default=None)
    start_time: str = Field(...)
    end_time: str = Field(...)
    tag: Optional[str] = Field(default=None)
    upper_vdc_id: Optional[str] = Field(default=None)
    vdc_id: Optional[str] = Field(default=None)
    enterprise_project_id: Optional[str] = Field(default=None)
    meter_unit_id: Optional[str] = Field(default=None)
    meter_unit_name: Optional[str] = Field(default=None)
    extend_params: Optional[str] = Field(default=None)
    meter_ways: Optional[str] = Field(default=None)
    spec_define_name: Optional[str] = Field(default=None)
    price: Optional[str] = Field(default=None)
    usage_duration: Optional[int] = Field(default=None)
    accumulate_mode: Optional[str] = Field(default=None)
    spec_define_id: Optional[str] = Field(default=None)
    price_unit: Optional[str] = Field(default=None)
    usage_value: Optional[float] = Field(default=None)

    model_config = {"extra": "allow"}


class HCSMetricsResponse(BaseModel):
    """
    Envelope returned by POST /rest/metering/v3.0/query-metrics-data.
    """

    metrics: list[HCSMetricRecord] = Field(default_factory=list)
    time_zone: str = Field(default="")
    start_time: str = Field(default="")
    end_time: str = Field(default="")
    total: int = Field(default=0)
    marker: str = Field(default="")


# ── Regions ────────────────────────────────────────────────────────────

class HCSRegion(BaseModel):
    seq_id: int = Field(default=0, alias="seqId")
    id: str = Field(..., description="Region identifier (e.g. whdevp-env-5)")
    name: str = Field(default="", description="Human-readable region name")
    active: bool = Field(default=True)
    domain_type: str = Field(default="", alias="domainType")
    type: Optional[str] = Field(default=None)  # <-- make this optional/nullable
    global_id: str = Field(default="", alias="globalId")

    model_config = {"extra": "allow", "populate_by_name": True}

class HCSRegionsResponse(BaseModel):
    """
    Envelope returned by GET /silvan/rest/v1.0/regions.
    """

    regions: list[HCSRegion] = Field(default_factory=list)
    total: int = Field(default=0)


# ── VDCs ───────────────────────────────────────────────────────────────


class HCSVDC(BaseModel):
    """
    A single VDC entry from GET /rest/vdc/v3.0/vdcs.
    """

    id: str = Field(..., description="VDC ID")
    name: str = Field(default="", description="VDC / tenant name")
    domain_id: str = Field(
        default="", description="Tenant / project ID used in metrics queries")
    domain_name: str = Field(default="", description="Tenant domain name")
    level: int = Field(default=1, description="VDC hierarchy level (1 = top)")
    upper_vdc_id: str = Field(default="0", description="Parent VDC ID")
    upper_vdc_name: str | None = Field(default=None)
    enabled: bool = Field(default=True)

    model_config = {"extra": "allow"}


class HCSVDCsResponse(BaseModel):
    """
    Envelope returned by GET /rest/vdc/v3.0/vdcs.
    """

    total: int = Field(default=0)
    vdcs: list[HCSVDC] = Field(default_factory=list)
