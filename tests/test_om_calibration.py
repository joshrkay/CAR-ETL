import pytest
from uuid import uuid4

from src.extraction.om_calibration import OMCalibrationTracker
from typing import Any


class _ExtractionStub:
    def __init__(self, asking_price: Any, noi_in_place: Any, cap_rate_in_place: Any, overall_confidence: Any = 0.0) -> None:
        self.asking_price = asking_price
        self.noi_in_place = noi_in_place
        self.cap_rate_in_place = cap_rate_in_place
        self.overall_confidence = overall_confidence


@pytest.mark.asyncio
async def test_record_closing_skips_missing_or_zero_baselines() -> None:
    extraction = _ExtractionStub(asking_price=None, noi_in_place=0.0, cap_rate_in_place=0.05, overall_confidence=0.8)
    recorded = []

    async def get_extraction_fn(_):
        return extraction

    async def store_calibration_fn(record):
        recorded.append(record)

    tracker = OMCalibrationTracker(get_extraction_fn, store_calibration_fn)

    await tracker.record_closing(
        om_extraction_id=uuid4(),
        actual_price=1_000_000.0,
        actual_noi=50_000.0,
        actual_cap_rate=0.06,
    )

    assert recorded, "Calibration record should be stored even when baselines are missing"
    variances = recorded[0].field_variances
    assert "cap_rate_in_place" in variances
    assert "asking_price" not in variances
    assert "noi_in_place" not in variances


@pytest.mark.asyncio
async def test_record_closing_computes_variances_with_valid_baselines() -> None:
    extraction = _ExtractionStub(asking_price=1_000_000.0, noi_in_place=500_000.0, cap_rate_in_place=0.06, overall_confidence=0.75)
    recorded = []

    async def get_extraction_fn(_):
        return extraction

    async def store_calibration_fn(record):
        recorded.append(record)

    tracker = OMCalibrationTracker(get_extraction_fn, store_calibration_fn)

    await tracker.record_closing(
        om_extraction_id=uuid4(),
        actual_price=1_100_000.0,
        actual_noi=550_000.0,
        actual_cap_rate=0.065,
    )

    variances = recorded[0].field_variances
    assert variances["asking_price"] == pytest.approx(0.1)
    assert variances["noi_in_place"] == pytest.approx(0.1)
    assert variances["cap_rate_in_place"] == pytest.approx(0.005)
