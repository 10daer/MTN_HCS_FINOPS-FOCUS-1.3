"""
FOCUS (FinOps Open Cost & Usage Specification) output schema.

Derived from the HCS → FOCUS column mapping in format.md.
Every field here represents a column in the final FOCUS-compliant output.
Fields are grouped by: direct HCS mappings, derived fields, and metadata.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FocusRecord(BaseModel):
    """
    A single row in FOCUS format, mapped from an HCS metering record.

    Sections follow the mapping table in format.md:
      - Direct HCS → FOCUS renames
      - Derived / computed FOCUS fields
      - Passthrough columns (unchanged)
    """

    # ── Account Identifiers (HCS Tenant → FOCUS Billing Account) ─────
    billing_account_name: str = Field(
        ..., description="FOCUS: BillingAccountName ← HCS Tenant Name"
    )
    billing_account_id: str = Field(
        ..., description="FOCUS: BillingAccountId ← HCS Tenant ID (Non-Nullable)"
    )

    # ── Sub Account (HCS VDC → FOCUS SubAccount) ─────────────────────
    sub_account_name: str = Field(
        default="", description="FOCUS: SubAccountName ← HCS VDC Name"
    )
    sub_account_id: str = Field(
        default="", description="FOCUS: SubAccountId ← HCS VDC ID (Non-Nullable)"
    )

    # ── Sub Child Account (derived from VDC hierarchy) ───────────────
    sub_child_account_id: str = Field(
        default="", description="FOCUS: SubChildAccountId (derived)"
    )
    sub_child_account_name: str = Field(
        default="", description="FOCUS: SubChildAccountName (derived)"
    )

    # ── Resource Identification ──────────────────────────────────────
    availability_zone: str = Field(
        default="", description="FOCUS: AvailabilityZone ← HCS Availability Zone"
    )
    region: str = Field(
        default="", description="FOCUS: Region ← HCS Region"
    )
    resource_space_name: str = Field(
        default="", description="FOCUS: ResourceSpaceName ← HCS Resource Space Name"
    )
    resource_space_id: str = Field(
        default="", description="FOCUS: ResourceSpaceId ← HCS Resource Space ID"
    )
    resource_type: str = Field(
        default="", description="FOCUS: ResourceType ← HCS Resource Type"
    )
    resource_name: str = Field(
        default="", description="FOCUS: ResourceName ← HCS Resource Name"
    )
    resource_id: str = Field(
        default="", description="FOCUS: ResourceId ← HCS Resource ID"
    )
    enterprise_project_id: str = Field(
        default="", description="FOCUS: EnterpriseProjectId ← HCS Enterprise Project ID"
    )

    # ── Tags ─────────────────────────────────────────────────────────
    tags: dict[str, str] = Field(
        default_factory=dict,
        description="FOCUS: Tags ← HCS Tag (converted to key-value pairs)",
    )

    # ── Application ──────────────────────────────────────────────────
    application_id: str = Field(
        default="", description="FOCUS: ApplicationId ← HCS Application ID"
    )
    application_name: str = Field(
        default="", description="FOCUS: ApplicationName ← HCS Application Name"
    )

    # ── Metering / Charge Period ─────────────────────────────────────
    charge_period_start: datetime = Field(
        ..., description="FOCUS: ChargePeriodStart ← HCS Metering Started (UTC-normalised)"
    )
    charge_period_end: datetime = Field(
        ..., description="FOCUS: ChargePeriodEnd ← HCS Metering Ended (UTC-normalised)"
    )

    # ── Metering Details ─────────────────────────────────────────────
    metering_metric: str = Field(
        default="", description="FOCUS: MeteringMetric ← HCS Metering Metric"
    )
    metering_value: float = Field(
        default=0.0, description="FOCUS: MeteringValue ← HCS Metering Value (unchanged)"
    )
    metering_unit_name: str = Field(
        default="",
        description="FOCUS: MeteringUnitName ← HCS Metering Unit Name (needs clarification)",
    )
    unit: str = Field(
        default="", description="FOCUS: Unit ← HCS Unit (unchanged)"
    )
    usage: float = Field(
        default=0.0, description="FOCUS: Usage ← HCS Usage (requires clarification)"
    )

    # ── Pricing ──────────────────────────────────────────────────────
    unit_price: float = Field(
        default=0.0, description="FOCUS: UnitPrice ← HCS Unit Price (currency label stripped)"
    )
    unit_price_unit: str = Field(
        default="", description="FOCUS: UnitPriceUnit ← HCS Unit Price Unit"
    )
    pricing_unit: str = Field(
        default="", description="FOCUS: PricingUnit (derived)"
    )
    pricing_currency: str = Field(
        default="", description="FOCUS: PricingCurrency (derived from BillingCurrency)"
    )
    pricing_currency_list_unit_price: float = Field(
        default=0.0, description="FOCUS: PricingCurrencyListUnitPrice (derived)"
    )

    # ── Cost ─────────────────────────────────────────────────────────
    billed_cost: float = Field(
        ..., description="FOCUS: BilledCost ← HCS Fee (currency suffix stripped, Non-Nullable)"
    )
    billing_currency: str = Field(
        default="NGN",
        description="FOCUS: BillingCurrency (derived, ISO code, Non-Nullable)",
    )

    # ── Consumed ─────────────────────────────────────────────────────
    consumed_unit: str = Field(
        default="", description="FOCUS: ConsumedUnit (derived from HCS Unit)"
    )

    # ── Provider ─────────────────────────────────────────────────────
    provider: str = Field(
        default="Huawei", description="FOCUS: Provider"
    )
    publisher: str = Field(
        default="MTN", description="FOCUS: Publisher"
    )
    invoice_issuer: str = Field(
        default="MTN", description="FOCUS: InvoiceIssuer"
    )


class FocusResponse(BaseModel):
    """API response envelope containing FOCUS records."""

    status: str = Field(default="ok")
    total_count: int = Field(default=0)
    records: list[FocusRecord] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
