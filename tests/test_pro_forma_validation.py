from src.extraction.pro_forma_validator import ProFormaValidator


def test_validator_flags_aggressive_rent_growth() -> None:
    validator = ProFormaValidator()
    warnings = validator.validate({"rent_growth_assumption": 0.08})
    assert any(w.field == "rent_growth_assumption" and w.issue == "aggressive" for w in warnings)


def test_validator_flags_high_noi_growth() -> None:
    validator = ProFormaValidator()
    warnings = validator.validate({"noi_in_place": 1_000_000, "noi_pro_forma": 1_400_000})
    assert any(w.field == "noi_pro_forma" for w in warnings)


def test_validator_flags_aggressive_stabilized_occupancy() -> None:
    validator = ProFormaValidator()
    warnings = validator.validate({"occupancy_pro_forma": 0.99})
    assert any(w.field == "occupancy_pro_forma" for w in warnings)
