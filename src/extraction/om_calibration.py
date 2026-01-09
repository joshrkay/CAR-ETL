"""
Calibration utilities for OM extraction vs actual closing data.
"""

from typing import Awaitable, Callable, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


class CalibrationRecord(BaseModel):
    extraction_id: UUID
    field_variances: Dict[str, float]
    extraction_confidence: float = Field(..., ge=0.0, le=1.0)


class OMCalibrationTracker:
    """Compare extracted values to actual closing data."""

    def __init__(
        self,
        get_extraction_fn: Callable[[UUID], Awaitable[Any]],
        store_calibration_fn: Callable[[CalibrationRecord], Awaitable[None]],
    ):
        if not get_extraction_fn or not store_calibration_fn:
            raise ValueError("Calibration tracker requires both retrieval and storage functions.")
        self.get_extraction_fn = get_extraction_fn
        self.store_calibration_fn = store_calibration_fn

    async def record_closing(
        self,
        om_extraction_id: UUID,
        actual_price: float,
        actual_noi: float,
        actual_cap_rate: float,
    ) -> None:
        """
        When a deal closes, compare to OM predictions.
        """
        extraction = await self.get_extraction_fn(om_extraction_id)

        price_var = (actual_price - extraction.asking_price) / extraction.asking_price
        noi_var = (actual_noi - extraction.noi_in_place) / extraction.noi_in_place
        cap_var = actual_cap_rate - extraction.cap_rate_in_place

        record = CalibrationRecord(
            extraction_id=om_extraction_id,
            field_variances={
                "asking_price": price_var,
                "noi_in_place": noi_var,
                "cap_rate_in_place": cap_var,
            },
            extraction_confidence=getattr(extraction, "overall_confidence", 0.0),
        )

        await self.store_calibration_fn(record)
