"""
Transform service — orchestrates authenticate → fetch → map → return.

This is the primary business-logic layer, composing the HCS client
and the FOCUS mapper into a single operation.
"""

from app.core.logging import get_logger
from app.mappers.focus_mapper import FocusMapper
from app.schemas.focus_schema import FocusRecord, FocusResponse
from app.services.source_client import HCSClient

logger = get_logger(__name__)


class TransformService:
    """Fetch HCS metering data, transform it to FOCUS, and return."""

    def __init__(self, hcs_client: HCSClient) -> None:
        self._hcs_client = hcs_client
        self._mapper = FocusMapper()

    async def transform(
        self,
        region_code: str,
        domain_id: str,
        start_time: str,
        end_time: str,
        resource_type_code: str,
        period: str = "daily",
        time_zone: str = "Africa/Lagos",
        locale: str = "en_US",
        limit: int = 1000,
        tenant_name: str = "",
        tenant_id: str = "",
        vdc_name: str = "",
        vdc_id: str = "",
    ) -> FocusResponse:
        """
        End-to-end: authenticate → fetch from HCS → map to FOCUS → return.

        Args:
            region_code:        HCS region ID.
            domain_id:          Tenant / VDC domain ID.
            start_time:         Period start (YYYY-MM-DD HH:MM:SS).
            end_time:           Period end (YYYY-MM-DD HH:MM:SS).
            resource_type_code: HCS resource type code.
            period:             hourly | daily | monthly.
            time_zone:          Timezone string.
            locale:             en_US | zh_CN.
            limit:              Page size.
            tenant_name:        HCS tenant name for FOCUS BillingAccountName.
            tenant_id:          HCS tenant id for FOCUS BillingAccountId.
            vdc_name:           VDC name for FOCUS SubAccountName.
            vdc_id:             VDC id for FOCUS SubAccountId.

        Returns:
            FocusResponse with the transformed records.
        """
        logger.info(
            "Transform pipeline started",
            extra={
                "region": region_code,
                "resource_type": resource_type_code,
                "period": period,
            },
        )

        # 1. Fetch HCS metrics
        hcs_records = await self._hcs_client.fetch_metrics(
            region_code=region_code,
            domain_id=domain_id,
            start_time=start_time,
            end_time=end_time,
            resource_type_code=resource_type_code,
            period=period,
            time_zone=time_zone,
            locale=locale,
            limit=limit,
        )

        # 2. Configure mapper with tenant/VDC context
        self._mapper = FocusMapper(
            tenant_name=tenant_name,
            tenant_id=tenant_id,
            vdc_name=vdc_name,
            vdc_id=vdc_id,
        )

        # 3. Map to FOCUS
        focus_records: list[FocusRecord] = self._mapper.map_many(hcs_records)

        logger.info(
            "Transform pipeline complete",
            extra={
                "source_count": len(hcs_records),
                "focus_count": len(focus_records),
            },
        )

        # 4. Return
        return FocusResponse(
            status="ok",
            total_count=len(focus_records),
            records=focus_records,
            metadata={
                "region_code": region_code,
                "domain_id": domain_id,
                "resource_type_code": resource_type_code,
                "period": period,
                "start_time": start_time,
                "end_time": end_time,
            },
        )
