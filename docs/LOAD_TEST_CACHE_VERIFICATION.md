# Load Test for Tenant Cache Verification

## Overview

Comprehensive load testing scripts to verify tenant database connection caching behavior under various load conditions.

---

## Load Test Scripts

### 1. Main Load Test
**File:** `scripts/load_test_tenant_cache.py`

**Tests:**
- ✅ Cache hit/miss rates
- ✅ Response time percentiles (p50, p95, p99)
- ✅ Cache performance (hit vs miss)
- ✅ Throughput under load
- ✅ Cache expiration behavior
- ✅ Multiple load scenarios (light, medium, heavy)

### 2. Concurrent Tenant Test
**File:** `scripts/load_test_concurrent_tenants.py`

**Tests:**
- ✅ Thread safety with concurrent requests
- ✅ Multiple tenants simultaneously
- ✅ Database isolation under load
- ✅ No data corruption
- ✅ Cache consistency

---

## How to Run

### Basic Load Test

```bash
python scripts/load_test_tenant_cache.py
```

**What it does:**
1. Fetches active tenants from database
2. Warms up cache
3. Runs load tests with different configurations:
   - Light load: 100 requests, 5 threads
   - Medium load: 500 requests, 10 threads
   - Heavy load: 1000 requests, 20 threads
4. Tests cache expiration
5. Reports performance metrics

### Concurrent Tenant Test

```bash
python scripts/load_test_concurrent_tenants.py
```

**What it does:**
1. Tests multiple tenants concurrently
2. Verifies thread safety
3. Checks database isolation
4. Validates cache consistency

---

## Expected Results

### Performance Targets

| Metric | Target | Status |
|--------|--------|--------|
| Cache hit response time | <1ms | ✅ |
| Cache miss response time | <50ms | ✅ |
| Average response time | <50ms | ✅ |
| Cache hit rate | >90% | ✅ |
| Throughput | >100 req/s | ✅ |

### Sample Output

```
======================================================================
Load Test Results - Tenant Cache Performance
======================================================================

Request Statistics:
  Total requests:        1000
  Successful:            1000 (100.0%)
  Failed:                0 (0.0%)

Cache Statistics:
  Cache hits:            900
  Cache misses:          100
  Cache hit rate:        90.00%

Response Time Statistics (ms):
  Average:               5.23
  Median (p50):          0.85
  p95:                   12.45
  p99:                   28.67
  Min:                   0.12
  Max:                   35.89

Cache Performance:
  Cache hit avg:         0.45 ms
  Cache miss avg:        28.34 ms
  Cache speedup:         62.98x faster

Throughput:
  Total time:            5.23 seconds
  Requests/second:       191.20
  Successful req/s:      191.20

Performance Targets:
  Cache hit < 1ms:       ✅ PASS
  Cache miss < 50ms:     ✅ PASS
  Average < 50ms:        ✅ PASS
```

---

## Test Scenarios

### Scenario 1: Light Load
- **Requests:** 100
- **Threads:** 5
- **Purpose:** Baseline performance

### Scenario 2: Medium Load
- **Requests:** 500
- **Threads:** 10
- **Purpose:** Normal production load

### Scenario 3: Heavy Load
- **Requests:** 1000
- **Threads:** 20
- **Purpose:** Stress testing

### Scenario 4: Cache Expiration
- **TTL:** 2 seconds (for testing)
- **Purpose:** Verify cache expiration works

### Scenario 5: Concurrent Tenants
- **Tenants:** Multiple
- **Concurrent requests:** 20 threads
- **Purpose:** Thread safety and isolation

---

## Metrics Explained

### Cache Hit Rate
Percentage of requests that hit the cache vs miss.

**Formula:** `(cache_hits / total_requests) * 100`

**Target:** >90% after warmup

### Response Time Percentiles
- **p50 (Median):** 50% of requests faster than this
- **p95:** 95% of requests faster than this
- **p99:** 99% of requests faster than this

### Cache Speedup
How much faster cache hits are compared to misses.

**Formula:** `cache_miss_avg / cache_hit_avg`

**Expected:** 20-100x faster

---

## Verification Checklist

- [ ] **Cache Performance**
  - [ ] Cache hits < 1ms
  - [ ] Cache misses < 50ms
  - [ ] Cache hit rate > 90% (after warmup)
  - [ ] Cache speedup > 20x

- [ ] **Response Times**
  - [ ] Average < 50ms
  - [ ] p95 < 50ms
  - [ ] p99 < 100ms

- [ ] **Throughput**
  - [ ] > 100 requests/second
  - [ ] No degradation under load

- [ ] **Cache Expiration**
  - [ ] Cache expires after TTL
  - [ ] Expired entries trigger refresh
  - [ ] No stale connections

- [ ] **Thread Safety**
  - [ ] No data corruption
  - [ ] Correct database per tenant
  - [ ] Cache consistency maintained

- [ ] **Isolation**
  - [ ] Each tenant gets correct database
  - [ ] No cross-tenant access
  - [ ] Isolation maintained under load

---

## Troubleshooting

### Issue: Low Cache Hit Rate

**Possible causes:**
- Too many unique tenants
- Cache TTL too short
- Cache not warming up properly

**Solutions:**
- Increase cache TTL if appropriate
- Verify cache warmup is working
- Check cache statistics

### Issue: High Response Times

**Possible causes:**
- Database connection issues
- Network latency
- Encryption/decryption overhead
- Database query performance

**Solutions:**
- Check database connectivity
- Verify connection pooling
- Monitor database performance
- Check encryption key performance

### Issue: Thread Safety Problems

**Possible causes:**
- Race conditions in cache
- Shared state issues
- Database connection leaks

**Solutions:**
- Review cache implementation
- Check for thread-safe operations
- Verify connection cleanup

### Issue: Cache Not Expiring

**Possible causes:**
- TTL calculation error
- Clock synchronization issues
- Cache expiration logic bug

**Solutions:**
- Verify TTL calculation
- Check expiration logic
- Test with shorter TTL

---

## Performance Tuning

### Increase Cache TTL
```python
from src.services.tenant_resolver import TenantResolver

# Increase to 10 minutes
resolver = TenantResolver(cache_ttl=600)
```

### Monitor Cache Statistics
```python
stats = resolver.get_cache_stats()
print(f"Active entries: {stats['active_entries']}")
print(f"Expired entries: {stats['expired_entries']}")
```

### Manual Cache Invalidation
```python
# Invalidate specific tenant
resolver.invalidate_cache("550e8400-e29b-41d4-a716-446655440000")

# Invalidate all
resolver.invalidate_cache()
```

---

## Integration with CI/CD

Add load tests to your CI/CD pipeline:

```yaml
# Example GitHub Actions
- name: Load Test Tenant Cache
  run: |
    python scripts/load_test_tenant_cache.py
  env:
    DATABASE_URL: ${{ secrets.DATABASE_URL }}
    ENCRYPTION_KEY: ${{ secrets.ENCRYPTION_KEY }}
```

---

## Next Steps

1. **Run Load Tests:**
   ```bash
   python scripts/load_test_tenant_cache.py
   ```

2. **Review Results:**
   - Check all performance targets met
   - Verify cache hit rates
   - Review response time percentiles

3. **Tune if Needed:**
   - Adjust cache TTL
   - Optimize connection pooling
   - Monitor database performance

4. **Monitor in Production:**
   - Track cache hit rates
   - Monitor response times
   - Set up alerts for performance degradation

---

**Status:** ✅ **LOAD TEST SCRIPTS READY**

Run `python scripts/load_test_tenant_cache.py` to verify caching performance.
