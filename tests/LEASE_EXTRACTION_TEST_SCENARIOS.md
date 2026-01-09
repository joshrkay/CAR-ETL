# CRE Lease Extraction Test Scenarios

This document describes 10 comprehensive test scenarios for CRE lease extraction, covering different complexities, lengths, and property types.

## Test Scenarios

### 1. Simple Short Lease (1-2 pages)
**Complexity:** Low  
**Length:** ~200 words  
**Fields:** 9 basic fields  
**Characteristics:**
- Basic tenant/landlord information
- Simple rent structure
- Minimal clauses
- Single page document

**Key Fields Tested:**
- tenant_name, landlord_name, property_address
- lease_start_date, lease_end_date
- base_rent, rent_frequency
- square_footage, security_deposit

---

### 2. Medium Complexity Office Lease (5-10 pages)
**Complexity:** Medium  
**Length:** ~800 words  
**Fields:** 20+ fields  
**Characteristics:**
- Corporate tenant with entity type
- Multi-year lease term
- Rent escalations
- CAM and expense reimbursements
- Renewal options
- TI allowance

**Key Fields Tested:**
- tenant_entity_type, landlord_entity_type
- initial_term_months
- escalation_rate_percent, escalation_frequency
- lease_type (modified_gross)
- cam_charges, tax_reimbursement, insurance_reimbursement
- renewal_options, right_of_first_refusal
- tenant_improvement_allowance, buildout_period_days

---

### 3. Complex Retail Lease with Percentage Rent
**Complexity:** High  
**Length:** ~600 words  
**Fields:** 18+ fields  
**Characteristics:**
- Retail-specific terms
- Percentage rent structure
- Co-tenancy clauses
- Marketing fees
- Signage rights
- Exclusive use provisions

**Key Fields Tested:**
- retail_type (inline, endcap, pad, anchor, outparcel)
- percentage_rent
- sales_reporting_required
- co_tenancy_clause
- common_area_marketing_fee
- signage_type
- exclusive_retail_use
- drive_thru

---

### 4. Industrial Warehouse Lease
**Complexity:** High  
**Length:** ~500 words  
**Fields:** 20+ fields  
**Characteristics:**
- Industrial property specifications
- Triple net lease structure
- Loading dock details
- Power capacity
- Sprinkler systems
- Rail access

**Key Fields Tested:**
- building_type (industrial)
- clear_height
- column_spacing
- loading_docks
- drive_in_doors
- trailer_parking_spaces
- power_capacity
- sprinkler_type (ESFR, wet, dry)
- floor_load_capacity
- rail_access, cross_dock

---

### 5. Class A Office Lease with Certifications
**Complexity:** Medium-High  
**Length:** ~600 words  
**Fields:** 20+ fields  
**Characteristics:**
- Premium office building
- Building certifications (LEED, WELL, EnergyStar)
- Office-specific features
- After-hours HVAC
- Core factor calculations

**Key Fields Tested:**
- office_class (A, B, C)
- floor_plate_size
- core_factor
- conference_room_access
- after_hours_hvac
- elevator_ratio
- building_certifications
- spec_suite
- open_plan_ratio

---

### 6. Mixed-Use Property Lease
**Complexity:** Medium  
**Length:** ~400 words  
**Fields:** 15+ fields  
**Characteristics:**
- Multiple use types in one property
- Component breakdown
- Shared facilities
- Operating restrictions
- Zoning requirements

**Key Fields Tested:**
- component_breakdown
- retail_percentage
- office_percentage
- residential_percentage
- shared_parking
- separate_entrances
- operating_hours_restrictions
- noise_restrictions
- zoning_classification

---

### 7. Long Complex Lease (20+ pages equivalent)
**Complexity:** Very High  
**Length:** ~2000 words  
**Fields:** 70+ fields  
**Characteristics:**
- Comprehensive lease agreement
- All major sections covered
- Multiple escalations
- Extensive options and rights
- Detailed legal clauses
- Property financial metrics

**Key Fields Tested:**
- All major field categories
- Financial metrics (cap_rate, NOI, GRM)
- Property characteristics (year_built, renovation_year, flood_zone)
- Complex escalation structures
- Multiple guarantee types
- Extensive use restrictions
- Maintenance responsibilities
- Insurance requirements
- Legal and default provisions

---

### 8. Minimal Lease with Missing Fields
**Complexity:** Low  
**Length:** ~100 words  
**Fields:** 7 basic fields  
**Characteristics:**
- Very short document
- Many optional fields missing
- Only essential information
- Tests graceful degradation

**Key Fields Tested:**
- Only required fields extracted
- Optional fields properly handled as null
- System doesn't fail on incomplete data

---

### 9. Lease with Abbreviations
**Complexity:** Medium  
**Length:** ~200 words  
**Fields:** 10+ fields  
**Characteristics:**
- Heavy use of abbreviations
- Industry jargon
- Shortened field names
- Tests alias recognition

**Key Fields Tested:**
- Abbreviation handling (T=Tenant, L=Landlord, Prem=Premises)
- Industry terms (SF=Square Feet, TI=Tenant Improvement, NNN=Triple Net)
- Currency abbreviations ($10K = $10,000)
- Date formats (3/1/24 = 2024-03-01)

---

### 10. Multi-Family Lease
**Complexity:** Medium  
**Length:** ~500 words  
**Fields:** 16+ fields  
**Characteristics:**
- Residential property lease
- Unit mix and occupancy
- Amenities
- Pet policies
- Concessions
- Parking ratios

**Key Fields Tested:**
- unit_count
- unit_mix
- average_rent_per_unit (ARPU)
- occupancy_rate
- concessions
- pet_policy
- amenities
- lease_term_options
- rent_control
- parking_ratio

---

## Running the Tests

### Prerequisites
```bash
pip install pytest pytest-asyncio openai
export OPENAI_API_KEY=your_api_key_here
```

### Run All Tests
```bash
pytest tests/test_lease_extraction_integration.py -v
```

### Run Specific Test
```bash
pytest tests/test_lease_extraction_integration.py::TestLeaseExtractionIntegration::test_simple_short_lease -v
```

### Run with Coverage
```bash
pytest tests/test_lease_extraction_integration.py --cov=src.extraction --cov-report=html
```

## Test Coverage Summary

| Scenario | Complexity | Length | Fields | Property Type |
|----------|-----------|--------|--------|---------------|
| 1. Simple Short | Low | 1-2 pages | 9 | Generic |
| 2. Medium Office | Medium | 5-10 pages | 20+ | Office |
| 3. Complex Retail | High | 5-8 pages | 18+ | Retail |
| 4. Industrial | High | 5-8 pages | 20+ | Industrial |
| 5. Class A Office | Medium-High | 6-10 pages | 20+ | Office |
| 6. Mixed-Use | Medium | 4-6 pages | 15+ | Mixed-Use |
| 7. Long Complex | Very High | 20+ pages | 70+ | Office |
| 8. Minimal | Low | 1 page | 7 | Generic |
| 9. Abbreviations | Medium | 2-3 pages | 10+ | Generic |
| 10. Multi-Family | Medium | 5-7 pages | 16+ | Multi-Family |

## Expected Results

Each test validates:
1. ✅ Field extraction accuracy
2. ✅ Value normalization (dates, currency, enums, booleans)
3. ✅ Confidence scoring (never exceeds 0.99)
4. ✅ Handling of missing optional fields
5. ✅ Property-type-specific fields
6. ✅ Alias recognition
7. ✅ Complex lease structures

## Notes

- Tests use mocked LLM responses to ensure deterministic results
- Real-world testing would require actual OpenAI API calls
- Tests validate the extraction pipeline, not LLM accuracy
- All tests follow .cursorrules compliance (complexity < 10, proper typing, etc.)
