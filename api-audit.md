# Specialized: API Request Audit

Not part of the Level 1-2-3 hierarchy. Run independently when:
- Adding polling or WebSocket handlers
- Refactoring data-fetching layer
- Investigating performance issues related to API calls
- Adding new external API integrations

**Team:** `TeamCreate("audit-api")`. 3 `code-reviewer-{N}` (opus).

---

## Agent 1: Backend — External API Calls

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
