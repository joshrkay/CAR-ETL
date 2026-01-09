# Complex Leases Test Suite - All Asset Classes

## Overview

This test suite validates CRE lease extraction across **all 5 asset classes** with **15 complex lease scenarios** (3 per asset class).

## Test Coverage

### 🏢 OFFICE LEASES (3 tests)

#### 1. Class A Premium Office Lease
**Complexity:** Very High  
**Fields Tested:** 30+ fields  
**Key Features:**
- Premium building with certifications (LEED Platinum, WELL, EnergyStar)
- Corporate tenant with parent company
- Full service gross lease
- High-end amenities (conference rooms, after-hours HVAC)
- Strong tenant quality metrics (A- credit rating, public company)
- Letter of credit and corporate guarantee

**Validates:**
- `office_class` = "A"
- `building_certifications` = "LEED"
- `tenant_credit_rating` = "A-"
- `tenant_is_public_company` = True
- `after_hours_hvac`, `core_factor`, `floor_plate_size`
- `guarantee_type` = "corporate"

#### 2. Class B Standard Office Lease
**Complexity:** Medium  
**Fields Tested:** 13+ fields  
**Key Features:**
- Standard office building
- Modified gross lease structure
- CAM and tax reimbursements
- Personal guarantee

**Validates:**
- `office_class` = "B"
- `lease_type` = "modified_gross"
- `cam_charges`, `tax_reimbursement`
- `personal_guarantee` = True

#### 3. Class C Value Office Lease
**Complexity:** Medium  
**Fields Tested:** 12+ fields  
**Key Features:**
- Value office space
- Triple net lease (NNN)
- Lower rent rates
- 2 months security deposit

**Validates:**
- `office_class` = "C"
- `lease_type` = "nnn"
- `security_deposit_months` = 2.0

---

### 🛍️ RETAIL LEASES (3 tests)

#### 4. Anchor Tenant Retail Lease
**Complexity:** Very High  
**Fields Tested:** 18+ fields  
**Key Features:**
- Large anchor tenant (100,000 sq ft)
- Co-tenancy clause
- Percentage rent structure
- Sales reporting requirements
- Multiple signage types
- Marketing fees

**Validates:**
- `retail_type` = "anchor"
- `co_tenancy_clause` = True
- `co_tenancy` = True
- `anchor_dependency` = True
- `percentage_rent`, `sales_reporting_required`
- `signage_type` = "pylon"
- `common_area_marketing_fee`

#### 5. Inline Retail Lease
**Complexity:** High  
**Fields Tested:** 13+ fields  
**Key Features:**
- Standard inline store
- Percentage rent (8% over breakpoint)
- Façade signage
- No drive-thru

**Validates:**
- `retail_type` = "inline"
- `percentage_rent` = "8%"
- `signage_type` = "façade"
- `drive_thru` = False

#### 6. Pad Site Retail Lease
**Complexity:** Medium-High  
**Fields Tested:** 13+ fields  
**Key Features:**
- Standalone pad site
- Drive-thru facility
- Monument signage
- Triple net lease
- Exclusive use provisions

**Validates:**
- `retail_type` = "pad"
- `drive_thru` = True
- `signage_type` = "monument"
- `exclusive_retail_use`

---

### 🏭 INDUSTRIAL LEASES (3 tests)

#### 7. Warehouse/Distribution Lease
**Complexity:** Very High  
**Fields Tested:** 22+ fields  
**Key Features:**
- Large distribution facility (75,000 sq ft)
- High clear height (32 feet)
- Multiple loading docks (12)
- Rail access and cross-dock
- ESFR sprinkler system
- Heavy power capacity

**Validates:**
- `building_type` = "industrial"
- `clear_height` = 32
- `loading_docks` = 12
- `rail_access` = True
- `cross_dock` = True
- `sprinkler_type` = "ESFR"
- `truck_court_depth` = 100

#### 8. Manufacturing Facility Lease
**Complexity:** High  
**Fields Tested:** 16+ fields  
**Key Features:**
- Manufacturing operations
- Heavy power requirements (5000A)
- Wet sprinkler system
- High floor load (300 psf)
- Specialized improvements (cranes, compressed air)

**Validates:**
- `sprinkler_type` = "wet"
- `floor_load_capacity` = "300 psf"
- `power_capacity` = "480V, 5000A"
- `specialized_improvements` (crane systems, heavy power)

#### 9. Cold Storage Facility Lease
**Complexity:** High  
**Fields Tested:** 16+ fields  
**Key Features:**
- Specialized cold storage
- Dry sprinkler system
- Temperature control systems
- Freezer infrastructure

**Validates:**
- `sprinkler_type` = "dry"
- `specialized_improvements` (cold storage, freezer systems)

---

### 🏘️ MULTI-FAMILY LEASES (3 tests)

#### 10. Luxury Multi-Family Lease
**Complexity:** Very High  
**Fields Tested:** 24+ fields  
**Key Features:**
- High-end apartment (2BR/2BA)
- Premium amenities (pool, gym, concierge, rooftop)
- High occupancy (98%)
- Comprehensive screening (income verification, background check)
- Pet-friendly with fees
- Multiple lease term options

**Validates:**
- `unit_type` = "2BR/2BA"
- `occupancy_rate` = 98.0
- `income_verification` = True
- `background_check` = True
- `rent_to_income_ratio` = 0.33
- `amenities` (pool, gym, concierge)
- `parking_ratio` = 1.5

#### 11. Mid-Market Multi-Family Lease
**Complexity:** Medium-High  
**Fields Tested:** 17+ fields  
**Key Features:**
- Standard apartment (3BR/2BA)
- Basic amenities
- Standard screening
- Pet restrictions (cats only)

**Validates:**
- `unit_type` = "3BR/2BA"
- `occupancy_rate` = 95.0
- `pet_policy` (cats only)
- `concessions` (move-in credit)

#### 12. Affordable Housing Lease
**Complexity:** Medium  
**Fields Tested:** 17+ fields  
**Key Features:**
- Affordable housing unit (2BR/1BA)
- Rent control
- 100% occupancy
- Income limits
- No pets
- Minimal amenities

**Validates:**
- `rent_control` = True
- `occupancy_rate` = 100.0
- `unit_type` = "2BR/1BA"
- `pet_policy` = "No pets"

---

### 🏙️ MIXED-USE LEASES (3 tests)

#### 13. Mixed-Use Retail + Office
**Complexity:** High  
**Fields Tested:** 17+ fields  
**Key Features:**
- Retail (40%) + Office (35%) + Residential (25%)
- Shared parking
- Separate entrances
- Operating hours restrictions
- Noise restrictions
- Cross-default clause

**Validates:**
- `component_breakdown`
- `retail_percentage` = 40.0
- `office_percentage` = 35.0
- `residential_percentage` = 25.0
- `shared_parking` = True
- `cross_default_clause` = True
- `operating_hours_restrictions`
- `noise_restrictions`

#### 14. Mixed-Use Retail + Residential
**Complexity:** High  
**Fields Tested:** 17+ fields  
**Key Features:**
- Restaurant in mixed-use building
- Retail (50%) + Residential (50%)
- Percentage rent
- Quiet hours restrictions
- Cross-default provisions

**Validates:**
- `retail_percentage` = 50.0
- `residential_percentage` = 50.0
- `percentage_rent` = "5%"
- `noise_restrictions` (quiet hours)

#### 15. Mixed-Use Office + Residential
**Complexity:** High  
**Fields Tested:** 18+ fields  
**Key Features:**
- Office (60%) + Residential (40%)
- Full service gross lease
- Shared valet parking
- Weekday operating hours
- Corporate guarantee

**Validates:**
- `office_percentage` = 60.0
- `residential_percentage` = 40.0
- `lease_type` = "gross"
- `corporate_guarantee` = True

---

## Test Statistics

| Asset Class | Tests | Total Fields Tested | Avg Complexity |
|------------|-------|---------------------|----------------|
| Office | 3 | 55+ | High |
| Retail | 3 | 44+ | High |
| Industrial | 3 | 54+ | Very High |
| Multi-Family | 3 | 58+ | High |
| Mixed-Use | 3 | 52+ | High |
| **TOTAL** | **15** | **263+** | **High** |

## Field Categories Validated

✅ **Property Type Specific Fields:**
- Office: `office_class`, `floor_plate_size`, `core_factor`, `building_certifications`
- Retail: `retail_type`, `percentage_rent`, `co_tenancy_clause`, `signage_type`
- Industrial: `clear_height`, `loading_docks`, `sprinkler_type`, `rail_access`
- Multi-Family: `unit_type`, `unit_mix`, `occupancy_rate`, `amenities`
- Mixed-Use: `component_breakdown`, `retail_percentage`, `cross_default_clause`

✅ **Tenant Quality Fields:**
- Credit metrics: `tenant_credit_rating`, `tenant_credit_score`
- Business strength: `tenant_is_public_company`, `tenant_years_in_business`
- Guarantees: `guarantee_type`, `corporate_guarantee`, `personal_guarantee`

✅ **Lease Structure Fields:**
- Rent: `base_rent`, `percentage_rent`, `rent_frequency`
- Lease type: `lease_type`, `expense_reimbursement_type`
- Security: `security_deposit`, `security_deposit_months`, `letter_of_credit_amount`

✅ **Risk & Performance Fields:**
- Payment: `payment_history_status`, `current_arrears_amount`
- Expiration: `lease_expiration_risk_bucket`
- Concentration: `tenant_rent_concentration_percent`

## Running the Tests

### Prerequisites
```bash
pip install pytest pytest-asyncio openai
export OPENAI_API_KEY=your_api_key_here
```

### Run All Tests
```bash
pytest tests/test_complex_leases_all_asset_classes.py -v
```

### Run by Asset Class
```bash
# Office only
pytest tests/test_complex_leases_all_asset_classes.py::TestComplexLeasesAllAssetClasses::test_office_class_a_premium_lease -v

# Retail only
pytest tests/test_complex_leases_all_asset_classes.py -k "retail" -v

# Industrial only
pytest tests/test_complex_leases_all_asset_classes.py -k "industrial" -v
```

### Run with Coverage
```bash
pytest tests/test_complex_leases_all_asset_classes.py --cov=src.extraction --cov-report=html
```

## Expected Results

Each test validates:
1. ✅ Correct field extraction for property type
2. ✅ Property-type-specific fields recognized
3. ✅ Tenant quality metrics extracted
4. ✅ Risk flags and security measures
5. ✅ Complex lease structures (NNN, gross, modified gross)
6. ✅ Value normalization (dates, currency, enums, booleans)
7. ✅ Confidence scoring (never exceeds 0.99)
8. ✅ Alias recognition (e.g., "NNN" → "nnn", "GPR" → "gross_potential_rent")

## Notes

- Tests use mocked LLM responses for deterministic results
- Real-world testing requires actual OpenAI API calls
- Tests validate extraction pipeline, not LLM accuracy
- All tests follow .cursorrules compliance
- Tests cover edge cases and property-type variations
