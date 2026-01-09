"""
Calibration utilities for OM extraction vs actual closing data.
"""

import logging
from numbers import Real
from typing import Awaitable, Callable, Dict, Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CalibrationRecord(BaseModel):
    extraction_id: UUID
    field_variances: Dict[str, float]
    extraction_confidence: float = Field(..., ge=0.0, le=1.0)


def _safe_relative_variance(
    field_name: str,
    actual: Real,
    baseline: Optional[Real],
    extraction_id: UUID,
) -> Optional[float]:
    """
    Compute relative variance while guarding against missing/zero baselines.
    """
    if baseline is None:
        logger.warning(
            "Calibration baseline missing",
            extra={"field": field_name, "extraction_id": str(extraction_id)},
        )
        return None
    if not isinstance(baseline, Real):
        logger.warning(
            "Calibration baseline not numeric",
            extra={"field": field_name, "extraction_id": str(extraction_id)},
        )
        return None
    if baseline == 0:
        logger.warning(
            "Calibration baseline is zero; skipping variance computation",
            extra={"field": field_name, "extraction_id": str(extraction_id)},
        )
        return None
    return float((actual - baseline) / baseline)


def _safe_difference(
    field_name: str,
    actual: Real,
    baseline: Optional[Real],
    extraction_id: UUID,
) -> Optional[float]:
    """
    Compute difference while guarding against missing baselines.
    """
    if baseline is None or not isinstance(baseline, Real):
        logger.warning(
            "Calibration baseline missing or not numeric",
            extra={"field": field_name, "extraction_id": str(extraction_id)},
        )
        return None
    return float(actual - baseline)


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

        field_variances: Dict[str, float] = {}

        price_var = _safe_relative_variance(
            "asking_price",
            actual_price,
            getattr(extraction, "asking_price", None),
            om_extraction_id,
        )
        if price_var is not None:
            field_variances["asking_price"] = price_var

        noi_var = _safe_relative_variance(
            "noi_in_place",
            actual_noi,
            getattr(extraction, "noi_in_place", None),
            om_extraction_id,
        )
        if noi_var is not None:
            field_variances["noi_in_place"] = noi_var

        cap_var = _safe_difference(
            "cap_rate_in_place",
            actual_cap_rate,
            getattr(extraction, "cap_rate_in_place", None),
            om_extraction_id,
        )
        if cap_var is not None:
            field_variances["cap_rate_in_place"] = cap_var

        record = CalibrationRecord(
            extraction_id=om_extraction_id,
            field_variances=field_variances,
            extraction_confidence=getattr(extraction, "overall_confidence", 0.0),
        )

        await self.store_calibration_fn(record)
