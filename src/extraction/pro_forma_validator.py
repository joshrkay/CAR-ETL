"""
Pro forma validation for OM assumptions.
"""

from typing import List, Dict, Any

from pydantic import BaseModel


class ValidationWarning(BaseModel):
    field: str
    issue: str
    message: str
    severity: str  # e.g., low/medium/high


class ProFormaValidator:
    """Validate reasonableness of pro forma assumptions."""

    MARKET_BENCHMARKS: Dict[str, Dict[str, Any]] = {
        "rent_growth_annual": {"min": 0.0, "max": 0.05, "typical": 0.03},
        "expense_growth_annual": {"min": 0.02, "max": 0.04, "typical": 0.025},
        "cap_rate_compression": {"min": 0, "max": 0.0075, "typical": 0.0025},
        "occupancy_stabilized": {"min": 0.90, "max": 0.97, "typical": 0.94},
        "lease_up_months": {"min": 6, "max": 36, "typical": 18},
    }

    def validate(self, om_data: Dict[str, Any]) -> List[ValidationWarning]:
        warnings: List[ValidationWarning] = []

        rent_growth = om_data.get("rent_growth_assumption")
        if rent_growth is not None and rent_growth > self.MARKET_BENCHMARKS["rent_growth_annual"]["max"]:
            warnings.append(
                ValidationWarning(
                    field="rent_growth_assumption",
                    issue="aggressive",
                    message=f"Rent growth of {rent_growth:.1%} exceeds typical max of 5%",
                    severity="high",
                )
            )

        if all(k in om_data for k in ["noi_in_place", "noi_pro_forma"]):
            in_place = om_data.get("noi_in_place")
            pro_forma = om_data.get("noi_pro_forma")
            if in_place and pro_forma:
                noi_growth = pro_forma / in_place - 1
                if noi_growth > 0.30:
                    warnings.append(
                        ValidationWarning(
                            field="noi_pro_forma",
                            issue="aggressive",
                            message=f"Pro forma NOI {noi_growth:.0%} above in-place requires scrutiny",
                            severity="high",
                        )
                    )

        stab_occ = om_data.get("occupancy_pro_forma")
        if stab_occ is not None and stab_occ > self.MARKET_BENCHMARKS["occupancy_stabilized"]["max"]:
            warnings.append(
                ValidationWarning(
                    field="occupancy_pro_forma",
                    issue="optimistic",
                    message=f"Stabilized occupancy of {stab_occ:.1%} is aggressive",
                    severity="medium",
                )
            )

        return warnings
