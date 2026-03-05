"""
Tests for FocusMapper (HCS → FOCUS).
"""

from datetime import datetime, timezone

import pytest

from app.core.exceptions import TransformationException, MappingFieldException
from app.mappers.focus_mapper import FocusMapper
from app.schemas import HCSMetricRecord


@pytest.fixture
def mapper() -> FocusMapper:
    return FocusMapper(
        billing_currency="NGN",
        tenant_name="yiwa",
        tenant_id="293e0d295e0f4110abf1697da9c68787",
        vdc_name="yiwa-vdc",
        vdc_id="eba900c3-1386-422e-a68d-da4f1f0aef18",
    )


@pytest.fixture
def sample_hcs_record() -> HCSMetricRecord:
    return HCSMetricRecord(
        id="c9e7dd89-70b1-46a0-8851-f519c07610c4",
        record_type="20",
        user_id="2e1ffdb5060b493d94583ff4bfa8f3b6",
        region_code="whdevp-env-5",
        az_code="az5.dc5",
        cloud_service_type_code="hws.service.type.evs",
        resource_type_code="hws.resource.type.volume",
        resource_spec_code="IPSAN",
        resource_id="4dcfaecc-ec31-424f-9811-32f33c811ce1",
        resource_display_name="xp02-volume-0000",
        start_time="2025-04-01 00:00:00",
        end_time="2025-04-02 00:00:00",
        tag="env=production,team=finops",
        upper_vdc_id="eba900c3-1386-422e-a68d-da4f1f0aef18",
        vdc_id="eba900c3-1386-422e-a68d-da4f1f0aef18",
        enterprise_project_id="0",
        meter_unit_name="",
        meter_ways="hour",
        spec_define_name="IPSAN",
        price="4",
        usage_duration=86400,
        accumulate_mode="DURATION",
        price_unit="GB",
        usage_value=8.0,
    )


def test_map_record_success(
    mapper: FocusMapper, sample_hcs_record: HCSMetricRecord
) -> None:
    """Should map an HCS metric record to a FocusRecord correctly."""
    result = mapper.map_record(sample_hcs_record)

    assert result.billing_account_name == "yiwa"
    assert result.billing_account_id == "293e0d295e0f4110abf1697da9c68787"
    assert result.sub_account_id == "eba900c3-1386-422e-a68d-da4f1f0aef18"
    assert result.resource_name == "xp02-volume-0000"
    assert result.resource_type == "hws.resource.type.volume"
    assert result.resource_id == "4dcfaecc-ec31-424f-9811-32f33c811ce1"
    assert result.availability_zone == "az5.dc5"
    assert result.region == "whdevp-env-5"
    assert result.billed_cost == 32.0  # price(4) * usage_value(8)
    assert result.billing_currency == "NGN"
    assert result.unit_price == 4.0
    assert result.usage == 8.0
    assert result.tags == {"env": "production", "team": "finops"}
    assert result.provider == "Huawei"
    assert result.publisher == "MTN"
    assert result.charge_period_start == datetime(
        2025, 4, 1, tzinfo=timezone.utc)


def test_map_many(
    mapper: FocusMapper, sample_hcs_record: HCSMetricRecord
) -> None:
    """map_many should transform a list of records."""
    results = mapper.map_many([sample_hcs_record, sample_hcs_record])
    assert len(results) == 2


def test_parse_tags(mapper: FocusMapper) -> None:
    """Verify tag parsing logic."""
    assert mapper._parse_tags("") == {}
    assert mapper._parse_tags("env=prod,team=finops") == {
        "env": "prod", "team": "finops"}
    assert mapper._parse_tags("simple-tag") == {"tag": "simple-tag"}


def test_parse_hcs_datetime(mapper: FocusMapper) -> None:
    """Verify HCS datetime parsing."""
    dt = mapper._parse_hcs_datetime("2025-04-01 00:00:00")
    assert dt == datetime(2025, 4, 1, tzinfo=timezone.utc)


def test_parse_hcs_datetime_empty_raises(mapper: FocusMapper) -> None:
    """Empty datetime should raise MappingFieldException."""
    with pytest.raises(MappingFieldException):
        mapper._parse_hcs_datetime("")


def test_safe_float(mapper: FocusMapper) -> None:
    """Verify safe float parsing."""
    assert mapper._safe_float("4.5") == 4.5
    assert mapper._safe_float("invalid") == 0.0
    assert mapper._safe_float("") == 0.0
