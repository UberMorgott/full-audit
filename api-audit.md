# Specialized: API Request Audit

> **Cross-references:** Works with [README.md](README.md) (orchestration), [universal.md](universal.md) (language-agnostic checks).
>
> **Required reading for all agents:**
> - **Confidence Scoring** (README.md) — assign 0-100 per finding. Thresholds: L1≥75, L2≥60, L3≥40.
> - **False Positive Detection** (universal.md) — check stack-specific auto-discard patterns first.
> - **CLI Finding Verification** (universal.md) — 5-step protocol per CLI tool finding.
> - **YAGNI Check** (universal.md) — verify need before suggesting additions.
> - **Anti-Rationalization Rules** (universal.md) — never skip checks or soften findings.

Not part of L1-2-3 hierarchy. Run independently when:
- Adding polling or WebSocket handlers
- Refactoring data-fetching layer
- Investigating API-related performance issues
- Adding external API integrations

**Team:** `TeamCreate("audit-api")`. 3 `code-reviewer-{N}` (DEEP).

---

## Agent 1: Backend — External API Calls

> **Reviewer mapping:** Security → diff-scanner + impact-reviewer. Concurrency → diff-scanner + history-reviewer. Resource leaks → diff-scanner. Conventions → convention-checker. Stale comments/TODOs → comment-checker.

Check for:
- **Unbounded HTTP request loops** — must have semaphore/throttle
- **Infinite polling** — timer+fetch without stop condition or context cancellation
- **Unbounded goroutine/thread fan-out** — N requests without concurrency limit
- **Retry without exponential backoff** — fixed interval causes thundering herd
- **No caching** — frequently requested data fetched every time
- **Per-request external calls** — every client request triggers external API (no cache/batch)
- **No timeout on external calls** — hanging request blocks handler
- **No circuit breaker** — failing external service cascades failures

**Pass:** request loops throttled, polling conditional, retry with backoff+jitter, frequent data cached, timeouts set.

---

## Agent 2: Frontend — Data Fetching

### With query library (TanStack Query, SWR, Apollo, etc.)

- **Unconditional polling** — polling when tab inactive or data fresh
- **staleTime: 0** for WS-updated data (should be 10-30s min)
- **Broad invalidation** — `queryClient.invalidateQueries()` without specific key (refetches everything)
- **Duplicate WS subscriptions** — multiple components subscribe to same event, each triggering refetch
- **Query on mount without guard** — `enabled: false` not used when fetch shouldn't fire immediately
- **Missing error retry limits** — infinite retries on 4xx (should only retry 5xx/network)
- **refetchOnWindowFocus** for rarely-changing data

### With raw fetch/axios

- **`setInterval` + fetch** without cleanup on unmount (leak + phantom requests)
- **Fetch in watch/useEffect without debounce** — request per keystroke
- **Multiple components fetching identical data** — no shared cache or lifted state
- **Multiple WebSocket connections** to same endpoint — should be singleton
- **Reconnect without backoff** — rapid reconnect loop on server failure
- **No abort controller** — previous request not cancelled on new one (race condition)

### General

- **No loading states** — user sees stale data during refetch
- **No error states** — failed requests silently ignored
- **Optimistic updates without rollback** — mutation fails but UI shows success

---

## Agent 3: Cross-Layer Trace

Trace request flows end-to-end for amplification patterns:

- **Frontend polling → backend → external API** — 1 poll = 1+ external calls. N users: N × polling_rate × external_calls_per_handler
- **WS event → broad invalidation → mass refetch** — 1 event triggers 10+ query refetches
- **Mutation → onSuccess → cascade invalidation** — saving 1 record refetches unrelated data
- **N tabs × polling = N× backend load** — multiple tabs multiply requests
- **Backend fan-out** — 1 frontend request → N parallel external calls without aggregation
- **Retry amplification** — frontend retries → backend retries → external retries (exponential growth)

### How to trace

1. List all frontend data-fetching hooks/composables
2. For each: find backend endpoint called
3. For each endpoint: list external API calls made
4. Calculate: `frontend_frequency × backend_fan_out × external_calls` = total external load
5. Identify highest amplification flows
6. Recommend caching, batching, or deduplication at right layer

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

If project uses GraphQL:
- **Query depth limiting:** unbounded nested queries cause exponential DB load
- **Query complexity analysis:** assign cost to fields, reject over-budget queries
- **Alias batching / `@defer` amplification:** repeated field aliases or array-batched/`@defer`/`@stream` ops multiply resolver work in one request — N+1/DoS vector; cap alias count, batch size, and `@defer`/`@stream` per request alongside depth/complexity limits (standard mitigation)
- **Introspection disabled in prod:** `__schema`/`__type` queries leak API structure
- **N+1 in resolvers:** use DataLoader or equivalent batching
- **Persisted queries:** consider allowing only pre-approved query hashes in prod
- **Field-level authorization:** sensitive fields need per-field auth, not just type-level

### gRPC-Specific Patterns

If project uses gRPC:
- **Deadline propagation:** every RPC must set and propagate deadlines to prevent cascade timeouts
- **Streaming backpressure:** streaming must handle slow consumers (bounded buffers)
- **Interceptors for auth:** use metadata interceptors, not per-method checks
- **Reflection disabled in prod:** server reflection exposes service definitions
- **Load balancing:** client-side LB for direct pod-to-pod communication
- **Error codes:** use canonical gRPC status codes, not generic UNKNOWN
