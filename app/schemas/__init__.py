"""
Pydantic schemas for the HCS ManageOne metrics API response.

These models represent the raw CDR (Call Detail Record) data returned
by POST /rest/metering/v3.0/query-metrics-data.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HCSMetricRecord(BaseModel):
    """
    A single metering record from the HCS ManageOne metrics API.

    Field names match the JSON keys returned by the SC Northbound Interface.
    """

    id: str = Field(..., description="Unique metric record ID")
    record_type: str = Field(default="", description="Record type code")
    user_id: str = Field(default="", description="Project / resource owner ID")
    region_code: str = Field(default="", description="Region identifier")
    cloud_infra_id: str = Field(
        default="", description="Cloud infrastructure ID")
    az_code: str = Field(
        default="", description="Availability zone code (e.g. az5.dc5)")
    cloud_service_type_code: str = Field(
        default="", description="Cloud service type (e.g. hws.service.type.evs)"
    )
    resource_type_code: str = Field(
        default="", description="Resource type (e.g. hws.resource.type.volume)"
    )
    resource_spec_code: str = Field(
        default="", description="Resource spec (e.g. IPSAN)")
    resource_id: str = Field(
        default="", description="Unique resource identifier")
    resource_display_name: str = Field(
        default="", description="Human-readable resource name")
    bss_params: str = Field(default="", description="BSS parameter string")
    start_time: str = Field(...,
                            description="Usage period start (YYYY-MM-DD HH:MM:SS)")
    end_time: str = Field(...,
                          description="Usage period end (YYYY-MM-DD HH:MM:SS)")
    tag: str = Field(default="", description="Resource tags (raw string)")
    upper_vdc_id: str = Field(default="", description="Parent VDC ID")
    vdc_id: str = Field(
        default="", description="VDC ID the resource belongs to")
    enterprise_project_id: str = Field(
        default="", description="Enterprise project ID")
    meter_unit_id: str = Field(default="", description="Metering unit ID")
    meter_unit_name: str = Field(default="", description="Metering unit name")
    extend_params: str = Field(default="", description="Extended parameters")
    meter_ways: str = Field(
        default="", description="Metering method (e.g. hour)")
    spec_define_name: str = Field(
        default="", description="Billing item / spec name")
    price: str = Field(default="0", description="Unit price as string")
    usage_duration: int = Field(
        default=0, description="Usage duration in seconds")
    accumulate_mode: str = Field(
        default="", description="DURATION (time-based) or USAGE (count-based)"
    )
    spec_define_id: str = Field(default="", description="Spec definition ID")
    price_unit: str = Field(default="", description="Price unit (e.g. GB)")
    usage_value: float = Field(
        default=0.0, description="Cumulative usage value")

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
    """
    A single region entry from GET /silvan/rest/v1.0/regions.
    """

    seq_id: int = Field(default=0, alias="seqId")
    id: str = Field(..., description="Region identifier (e.g. whdevp-env-5)")
    name: str = Field(default="", description="Human-readable region name")
    active: bool = Field(default=True)
    domain_type: str = Field(default="", alias="domainType")
    type: str = Field(default="")
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
