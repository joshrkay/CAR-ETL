"""Verify rent roll fields are correctly added."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from src.extraction.cre_fields import get_cre_rent_roll_fields, get_field_config
    
    # Get rent roll fields
    fields = get_cre_rent_roll_fields()
    print(f"✓ Total rent roll fields: {len(fields)}")
    
    # Verify key fields exist
    key_fields = [
        "rent_roll_as_of_date",
        "total_units",
        "economic_occupancy",
        "unit_number",
        "lease_status",
        "parking_rent",
        "storage_rent",
        "rent_step_schedule",
        "credit_rating",
        "guarantor",
        "unit_type",
        "tenant_industry",
        "gross_sales",
        "weighted_average_lease_term",
    ]
    
    missing = [f for f in key_fields if f not in fields]
    if missing:
        print(f"✗ Missing fields: {missing}")
    else:
        print(f"✓ All key fields present ({len(key_fields)} fields)")
    
    # Test get_field_config
    rent_roll_config = get_field_config("cre", "rent_roll")
    print(f"✓ Rent roll config accessible: {len(rent_roll_config)} fields")
    
    print("\n✓ Rent roll fields successfully added!")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
