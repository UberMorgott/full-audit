# Specialized: API Request Audit

> **Cross-references:** This file works with [README.md](README.md) (orchestration) and [universal.md](universal.md) (language-agnostic checks).
>
> **Required reading for all agents using this file:**
> - **Confidence Scoring** (README.md) — assign 0-100 score to every finding. Level thresholds: L1≥75, L2≥60, L3≥40.
> - **False Positive Detection** (universal.md) — check stack-specific auto-discard patterns before including findings.
> - **CLI Finding Verification** (universal.md) — 5-step protocol for every CLI tool finding.
> - **YAGNI Check** (universal.md) — verify recommendations are needed before suggesting "add X".
> - **Anti-Rationalization Rules** (universal.md) — do not skip checks or soften findings.

Not part of the Level 1-2-3 hierarchy. Run independently when:
- Adding polling or WebSocket handlers
- Refactoring data-fetching layer
- Investigating performance issues related to API calls
- Adding new external API integrations

**Team:** `TeamCreate("audit-api")`. 3 `code-reviewer-{N}` (opus).

---

## Agent 1: Backend — External API Calls

> **Reviewer mapping:** Security checks → diff-scanner + impact-reviewer. Concurrency → diff-scanner + history-reviewer. Resource leaks → diff-scanner. Convention compliance → convention-checker. Stale comments/TODOs → comment-checker.

Check for:
- **Unbounded loops with HTTP requests** — must have semaphore/throttle
- **Infinite polling** — timer+fetch without stop condition or context cancellation
- **Unbounded goroutine/thread fan-out** — spawning N requests without concurrency limit
- **Retry without exponential backoff** — fixed interval retry causes thundering herd
- **No caching** — frequently requested data fetched every time
- **Per-request external calls** — every client request triggers external API (no intermediate cache/batch)
- **No timeout on external calls** — hanging request blocks handler
- **No circuit breaker** — failing external service cascades failures

**Pass:** all request loops throttled, polling conditional, retry with backoff+jitter, frequent data cached, timeouts set.

---

## Agent 2: Frontend — Data Fetching

### With query library (TanStack Query, SWR, Apollo, etc.)

- **Unconditional polling interval** — polling even when tab inactive or data fresh
- **staleTime: 0** for data also updated via WebSocket (should be 10-30s minimum)
- **Broad invalidation** — `queryClient.invalidateQueries()` without specific key (refetches everything)
- **Duplicate WS subscriptions** — multiple components subscribing to same event, each triggering refetch
- **Query on mount without guard** — `enabled: false` not used when data shouldn't fetch immediately
- **Missing error retry limits** — infinite retries on 4xx errors (should only retry 5xx/network)
- **refetchOnWindowFocus** for data that rarely changes

### With raw fetch/axios

- **`setInterval` + fetch** without cleanup on unmount (memory leak + phantom requests)
- **Fetch in watch/useEffect without debounce** — request per keystroke
- **Multiple components fetching identical data** — no shared cache or lifted state
- **Multiple WebSocket connections** to same endpoint — should be singleton
- **Reconnect without backoff** — rapid reconnect loop on server failure
- **No abort controller** — previous request not cancelled when new one starts (race condition)

### General

- **No loading states** — user sees stale data during refetch
- **No error states** — failed requests silently ignored
- **Optimistic updates without rollback** — mutation fails but UI shows success

---

## Agent 3: Cross-Layer Trace

Trace request flows end-to-end to find amplification patterns:

- **Frontend polling -> backend handler -> external API** — 1 frontend poll = 1+ external calls. With N users: N * polling_rate * external_calls_per_handler
- **WS event -> broad invalidation -> mass refetch** — 1 WebSocket event triggers refetch of 10+ queries
- **Mutation -> onSuccess -> cascade invalidation** — saving one record triggers refetch of unrelated data
- **N tabs x polling = Nx backend load** — multiple browser tabs multiply polling requests
- **Backend fan-out** — 1 frontend request triggers N parallel external API calls without aggregation
- **Retry amplification** — frontend retries -> backend retries -> external API retries (exponential growth)

### How to trace

1. List all frontend data-fetching hooks/composables
2. For each: find the backend endpoint it calls
3. For each backend endpoint: list external API calls it makes
4. Calculate: `frontend_frequency * backend_fan_out * external_calls` = total external load
5. Identify: which flows have highest amplification factor
6. Recommend: caching, batching, or deduplication at the right layer

### Example output table

```markdown
| Flow | Frontend freq | Backend fan-out | External calls | Amplification | Risk | Recommendation |
|------|--------------|-----------------|----------------|--------------|------|----------------|
| Device polling → /api/devices → External Device API | 5s interval | 1 | 3 (status + config + telemetry) | 3x per user per 5s | HIGH | Cache external API responses 10s, batch into single call |
| WS "device_update" → invalidateQueries(["devices"]) | On event | 1 | 0 (local cache) | Refetches 5 queries | MEDIUM | Narrow invalidation to specific device key |
| Save settings → onSuccess → invalidateQueries() | On mutation | 1 | 0 | Refetches ALL queries | HIGH | Use specific query keys, not broad invalidation |
| Login → /api/auth → LDAP bind + token gen | On submit | 1 | 1 (LDAP) | 1x | LOW (rate limited) | OK if rate limited |
```

---

### GraphQL-Specific Patterns

If the project uses GraphQL:
- **Query depth limiting:** unbounded nested queries can cause exponential DB load
- **Query complexity analysis:** assign cost to fields, reject queries exceeding budget
- **Introspection disabled in production:** `__schema` and `__type` queries leak API structure
- **N+1 in resolvers:** use DataLoader pattern or equivalent batching
- **Persisted queries:** consider allowing only pre-approved query hashes in production
- **Field-level authorization:** not just type-level — sensitive fields need per-field auth checks

### gRPC-Specific Patterns

If the project uses gRPC:
- **Deadline propagation:** every RPC call should set and propagate deadlines to prevent cascade timeouts
- **Streaming backpressure:** server/client streaming must handle slow consumers (bounded buffers)
- **Interceptors for auth:** authentication via metadata interceptors, not per-method checks
- **Reflection disabled in production:** gRPC server reflection exposes service definitions
- **Load balancing:** client-side load balancing for direct pod-to-pod communication
- **Error codes:** use canonical gRPC status codes, not generic UNKNOWN for everything
