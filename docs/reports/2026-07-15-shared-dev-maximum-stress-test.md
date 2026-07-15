# Shared Dev Maximum Stress Test — Results (2026-07-15)

**Run:** `full-20260715-191350` · target `https://dev-api.gen-text.app` (namespace `rag-dev`)
**Profile:** maximum (ramp 20→50→100→200→300→400 over 34 min), executed via local k6 v2.1.0 with an inline kubectl readiness/restart monitor.
**Outcome:** monitor triggered a **catastrophic abort ~3m52s in**, during the ramp to 50 VUs. The 100/200/300/400 stages were never reached — the system broke well below the max profile.

Evidence: `/tmp/rag-stress/full-20260715-191350/` (`k6.log`, `summary.json`, `monitor.log`, `baseline.txt`, `recovery.txt`, `status.txt`).

## Observed facts

- **Breaking point ≈ 40–50 concurrent users.** Readiness (`/health/readiness`) failed 3 consecutive 5s samples (19:17:24 → 19:17:43) during the "moderate" stage ramping to 50 VUs; the monitor SIGINTed k6.
- **Failure was readiness collapse, not a crash.** Backend `restartCount` stayed **0**; no OOM. Memory held ~1.5 GiB / 2 GiB throughout. Pod was never killed — it was removed from Service endpoints while readiness was red.
- **Backend CPU *fell* during the collapse.** ~993m (near the 1-core limit) at 16 VUs in warm-up, then **down to ~100–260m** while readiness was failing. Compute was not the binding constraint at the break.
- **Latency piled into the client timeout ceiling.** Aggregate `http_req_duration`: median ~2.0 s, avg 4.3 s, p90 7.2 s, **p95 30.0 s** (= the 30 s request timeout), max 45.1 s.
- **Error rate at collapse:** `http_req_failed` **9.88%**; checks passed **88.31%** over 759 requests (~2 req/s effective — throughput had collapsed). By endpoint: search 274✓/36✗, documents 103✓/12✗, profile 79✓/10✗, **upload 20✓/5✗ (worst, 20%)**.
- **Recovery was fast and clean.** Within ~90 s of load stopping, 3/3 readiness probes returned 200; no restart.
- **Setup auth loss:** 38/50 identities authenticated; the 12 failures were Supabase password-grant rate-limiting.

## Hypothesis (not yet confirmed)

The signature — CPU *dropping* while readiness fails, latency queueing to the 30 s ceiling, memory flat — points to **request queueing / connection-pool contention on the single backend replica**, not CPU/memory exhaustion. Search is 60% of the mix and runs on the **sync** DB path (`get_db_sync`); with one replica against the Supabase pooler, the connection pool likely saturates, and `/health/readiness` (which touches the DB) then can't acquire a connection → 503 → endpoint removal.

**To confirm** (evidence not yet gathered): backend logs for pool-exhaustion / worker-timeout signatures across 19:16–19:18, the readiness probe's actual dependency checks, and Supabase pooler connection metrics. Do not treat the pool hypothesis as root cause until logs support it.

## Recommendations (ranked)

1. **Investigate the hot search path under contention** — DB pool sizing vs. the single replica, and sync (`get_db_sync`) vs. async in the 60%-of-traffic search route. A breaking point of ~50 users is low for a 1 CPU / 2 GiB replica.
2. **Backend autoscaling is disabled.** Readiness-shedding is correct behavior, but users get 503s; consider HPA/KEDA on the backend (worker autoscaling already exists) or a larger connection pool.
3. **Uploads degrade first** (20% failure) — expected (heaviest op) but worth a separate targeted profile.

## Cleanup status — shared dev left clean

- k6 teardown (ran on abort): **docs deleted=26, residual=0; users deleted=38, residual=0**.
- Out-of-band: **12 orphaned Supabase users** (created-but-unauthenticated in setup) were found and deleted; re-verified **0 `stress-` users remain**.
- Harness fixed so this can't recur: setup now compensating-deletes any user it can't obtain a token for, and throttles 0.1 s between identities.

## Caveats

Single run; the 100–400 VU stages were never exercised (correctly aborted). Per-endpoint latency percentiles were not captured (no per-tag thresholds → k6 emits no tagged submetrics); only aggregate `http_req_duration` is available. Executed via local k6 (Docker unavailable) with an inline monitor equivalent to `run-shared-dev-max.sh`'s abort logic.
