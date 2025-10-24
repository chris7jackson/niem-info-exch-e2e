---
name: Performance Optimization
about: Improve system performance, reduce latency, or increase throughput
title: '[PERFORMANCE] '
labels: performance, needs-triage
assignees: ''
---

## Performance Issue

**Type of performance issue:**
- [ ] Slow response time / High latency
- [ ] Low throughput / Poor scalability
- [ ] High resource usage (CPU, memory, disk, network)
- [ ] Inefficient algorithm or query
- [ ] Memory leak
- [ ] N+1 query problem
- [ ] Excessive I/O operations
- [ ] Poor caching strategy
- [ ] Database bottleneck
- [ ] Network bottleneck

## Current Performance

**Observed Behavior:**
<!-- Describe the performance problem -->

**Metrics:**
<!-- Provide measurable data -->
- **Response time:** <!-- e.g., 2.5s average, 5s p95, 8s p99 -->
- **Throughput:** <!-- e.g., 100 requests/second -->
- **CPU usage:** <!-- e.g., 80% average, spikes to 100% -->
- **Memory usage:** <!-- e.g., 2GB steady state, leaks 100MB/hour -->
- **Database query time:** <!-- e.g., 500ms average -->
- **Error rate:** <!-- e.g., 2% timeout errors -->

**Measurement Method:**
<!-- How were these metrics collected? -->
- Tool: <!-- e.g., New Relic, DataDog, custom logging, profiler -->
- Environment: <!-- e.g., production, staging, local -->
- Load: <!-- e.g., 1000 concurrent users, batch of 10k records -->
- Date/Time: <!-- When was this measured? -->

**Affected Endpoints/Components:**
<!-- Which parts of the system are slow? -->
-

## Target Performance

**Performance Goals:**
<!-- What are the target metrics? -->
- **Response time:** <!-- e.g., <500ms average, <1s p95, <2s p99 -->
- **Throughput:** <!-- e.g., 500 requests/second -->
- **CPU usage:** <!-- e.g., <50% average -->
- **Memory usage:** <!-- e.g., <1GB steady state, no leaks -->
- **Database query time:** <!-- e.g., <100ms average -->
- **Error rate:** <!-- e.g., <0.1% -->

**Success Criteria:**
<!-- How much improvement is needed? -->
- [ ] 2x faster
- [ ] 5x faster
- [ ] 10x faster
- [ ] Reduce resource usage by 50%
- [ ] Support 10x more concurrent users
- [ ] Other: ___________

## User Impact

**Who is affected?**
- [ ] All users
- [ ] High-volume users
- [ ] Specific feature users
- [ ] Background jobs/workers
- [ ] API consumers
- [ ] Internal operations

**Business Impact:**
<!-- How does poor performance affect the business? -->
- User frustration / abandonment
- Lost revenue
- Increased infrastructure costs
- SLA violations
- Competitive disadvantage
- Poor user reviews

**Frequency:**
<!-- How often is this performance issue experienced? -->
- [ ] Always / Constant
- [ ] During peak hours
- [ ] With large datasets
- [ ] Intermittent spikes
- [ ] Growing over time

## Root Cause Analysis

**Suspected Bottleneck:**
<!-- What do you think is causing the performance issue? -->

**Profiling Data:**
<!-- If available, include profiler output, flame graphs, or query execution plans -->
```
# Profiler output, slow query logs, etc.
```

**Contributing Factors:**
- [ ] Inefficient algorithm (O(n²) instead of O(n log n))
- [ ] Missing database indexes
- [ ] Lack of caching
- [ ] Too many database queries (N+1 problem)
- [ ] Large payload sizes
- [ ] Synchronous operations that could be async
- [ ] Memory allocation/garbage collection
- [ ] Network latency
- [ ] Third-party service delays
- [ ] Resource contention
- [ ] Other: ___________

## Proposed Optimization

**Optimization Strategy:**
<!-- High-level approach to improving performance -->

**Specific Changes:**
1. <!-- e.g., Add database index on user_id column -->
2. <!-- e.g., Implement Redis caching for frequently accessed data -->
3. <!-- e.g., Replace nested loops with hash map lookup -->

**Alternatives Considered:**
<!-- What other approaches were evaluated? Trade-offs? -->

**Trade-offs:**
<!-- Any downsides? Increased complexity, storage, etc.? -->

## Technical Context

**Affected Components:**
<!-- List files, modules, queries, or services to optimize -->
-

**Dependencies:**
<!-- Any dependencies on infrastructure, external services, or other issues? -->

**Backward Compatibility:**
<!-- Will optimization break existing functionality? -->
- [ ] Fully compatible
- [ ] Minor breaking changes
- [ ] Major breaking changes

## Benchmarking Plan

**How will performance be measured?**
- [ ] Load testing (e.g., JMeter, Locust, k6)
- [ ] Profiling (e.g., py-spy, perf, Chrome DevTools)
- [ ] APM tools (e.g., New Relic, DataDog, Dynatrace)
- [ ] Custom metrics and logging
- [ ] Database query analysis (EXPLAIN plans)

**Test Scenarios:**
<!-- Define test cases to validate improvement -->
1. Baseline test: <!-- Current performance -->
2. Optimized test: <!-- Expected performance after changes -->
3. Stress test: <!-- Performance under extreme load -->

**Before/After Comparison:**
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Response time | | | |
| Throughput | | | |
| CPU usage | | | |
| Memory usage | | | |

## Acceptance Criteria

- [ ] Performance goals met or exceeded
- [ ] Benchmarking completed with before/after metrics
- [ ] No regressions in other areas (functionality, correctness)
- [ ] Code profiled and hot paths optimized
- [ ] Monitoring/alerting configured for key metrics
- [ ] Documentation updated with performance characteristics
- [ ] Load testing passed at expected scale
- [ ] Deployed to staging and validated
- [ ] Production performance verified

## Additional Context

**Related Issues:**
<!-- Links to related performance issues or features -->
-

**Infrastructure:**
<!-- Details about infrastructure that might affect performance -->
- Hosting: <!-- e.g., AWS EC2, Kubernetes, serverless -->
- Database: <!-- e.g., PostgreSQL, MySQL, MongoDB -->
- Cache: <!-- e.g., Redis, Memcached -->
- CDN: <!-- e.g., CloudFront, Cloudflare -->

**Monitoring:**
<!-- Existing monitoring and alerting setup -->

**Historical Context:**
<!-- Has performance degraded over time? Recent changes? -->

## Priority

**Priority:** <!-- Critical | High | Medium | Low -->

**Justification:**
<!-- Why this priority? Consider: user impact, cost, competitive pressure -->

## Estimated Effort

**Effort:** <!-- XS (<2h) | S (2-4h) | M (4-8h) | L (8-16h) | XL (16-32h) | XXL (>32h) -->

**Breakdown:**
- Profiling/analysis: <!-- estimate -->
- Implementation: <!-- estimate -->
- Testing/benchmarking: <!-- estimate -->
- Monitoring setup: <!-- estimate -->

**Complexity:**
- [ ] Simple - Config change, add index, adjust caching
- [ ] Moderate - Algorithm improvement, query optimization
- [ ] Complex - Architecture change, distributed caching, sharding

---

**Additional Notes:**
<!-- Any other information, references to research, or performance tips -->
