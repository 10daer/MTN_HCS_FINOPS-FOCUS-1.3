"""
Concrete mapper: HCS ManageOne metric record → FOCUS format.

Contains the field-by-field transformation logic following the
column mapping defined in format.md.
"""

from datetime import datetime, timezone

from app.core.exceptions import MappingFieldException, TransformationException
from app.core.logging import get_logger
from app.mappers.base_mapper import BaseMapper
from app.schemas import HCSMetricRecord
from app.schemas.focus_schema import FocusRecord

logger = get_logger(__name__)

# Default billing currency for MTN Nigeria HCS
_DEFAULT_CURRENCY = "NGN"


class FocusMapper(BaseMapper[HCSMetricRecord, FocusRecord]):
    """Map HCS ManageOne metering records into the FOCUS specification."""

    def __init__(
        self,
        billing_currency: str = _DEFAULT_CURRENCY,
        tenant_name: str = "",
        tenant_id: str = "",
        vdc_name: str = "",
        vdc_id: str = "",
    ) -> None:
        self._billing_currency = billing_currency
        self._tenant_name = tenant_name
        self._tenant_id = tenant_id
        self._vdc_name = vdc_name
        self._vdc_id = vdc_id

    def map_record(self, source: HCSMetricRecord) -> FocusRecord:
        """
        Transform one HCSMetricRecord → FocusRecord.

        Mapping follows format.md column definitions.

        Raises:
            MappingFieldException:    If a required field cannot be mapped.
            TransformationException:  For any other transformation failure.
        """
        try:
            # Parse HCS time strings into datetime objects
            charge_start = self._parse_hcs_datetime(source.start_time)
            charge_end = self._parse_hcs_datetime(source.end_time)

            # Compute billed cost: price * usage_value
            price = self._safe_float(source.price)
            billed_cost = round(price * source.usage_value, 6)

            # Parse tags from raw string to key-value dict
            tags = self._parse_tags(source.tag)

            return FocusRecord(
                # ── Account (Tenant → BillingAccount) ─────────────────
                billing_account_name=self._tenant_name,
                billing_account_id=self._tenant_id,

                # ── Sub Account (VDC → SubAccount) ────────────────────
                sub_account_name=self._vdc_name,
                sub_account_id=source.vdc_id or self._vdc_id,

                # ── Sub Child Account (VDC hierarchy) ─────────────────
                sub_child_account_id=source.upper_vdc_id,
                sub_child_account_name="",

                # ── Resource ──────────────────────────────────────────
                availability_zone=source.az_code,
                region=source.region_code,
                resource_space_name="",
                resource_space_id=source.enterprise_project_id,
                resource_type=source.resource_type_code,
                resource_name=source.resource_display_name,
                resource_id=source.resource_id,
                enterprise_project_id=source.enterprise_project_id,

                # ── Tags ──────────────────────────────────────────────
                tags=tags,

                # ── Application ───────────────────────────────────────
                application_id="",
                application_name="",

                # ── Charge Period (Metering Started/Ended) ────────────
                charge_period_start=charge_start,
                charge_period_end=charge_end,

                # ── Metering Details ──────────────────────────────────
                metering_metric=source.accumulate_mode,
                metering_value=source.usage_value,
                metering_unit_name=source.meter_unit_name,
                unit=source.price_unit,
                usage=source.usage_value,

                # ── Pricing ───────────────────────────────────────────
                unit_price=price,
                unit_price_unit=source.price_unit,
                pricing_unit=source.price_unit,
                pricing_currency=self._billing_currency,
                pricing_currency_list_unit_price=price,

                # ── Cost ──────────────────────────────────────────────
                billed_cost=billed_cost,
                billing_currency=self._billing_currency,

                # ── Consumed ──────────────────────────────────────────
                consumed_unit=source.price_unit,

                # ── Provider ──────────────────────────────────────────
                provider="Huawei",
                publisher="MTN",
                invoice_issuer="MTN",
            )
        except MappingFieldException:
            raise
        except Exception as exc:
            logger.error(
                "Transformation failed for HCS metric record",
                extra={"source_id": source.id, "error": str(exc)},
                exc_info=True,
            )
            raise TransformationException(
                message=f"Failed to transform HCS record '{source.id}'.",
                details={"source_id": source.id, "reason": str(exc)},
            ) from exc

    # ── Private helpers ───────────────────────────────────────────────

    @staticmethod
    def _parse_hcs_datetime(value: str) -> datetime:
        """
        Parse HCS datetime string 'YYYY-MM-DD HH:MM:SS' into a
        timezone-aware datetime (UTC).
        """
        if not value:
            raise MappingFieldException(
                field_name="start_time/end_time",
                reason="Empty datetime value.",
            )
        try:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise MappingFieldException(
                field_name="start_time/end_time",
                reason=f"Invalid datetime format: '{value}'",
            ) from exc

    @staticmethod
    def _safe_float(value: str) -> float:
        """Convert a string price to float, defaulting to 0.0."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _parse_tags(raw_tag: str) -> dict[str, str]:
        """
        Parse HCS tag string into key-value pairs.

        Handles common formats:
          - Empty string → {}
          - 'key1=value1,key2=value2' → {key1: value1, key2: value2}
          - Plain string → {tag: <raw_string>}
        """
        if not raw_tag or not raw_tag.strip():
            return {}

        tags: dict[str, str] = {}
        for pair in raw_tag.split(","):
            pair = pair.strip()
            if "=" in pair:
                key, _, val = pair.partition("=")
                tags[key.strip()] = val.strip()
            elif pair:
                tags["tag"] = pair

        return tags
