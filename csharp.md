# C# / .NET Audit Checks

> **Cross-references:** This file works with [README.md](README.md) (orchestration) and [universal.md](universal.md) (language-agnostic checks).
>
> **Required reading for all agents using this file:**
> - **Confidence Scoring** (README.md) — assign 0-100 score to every finding. Level thresholds: L1≥75, L2≥60, L3≥40.
> - **False Positive Detection** (universal.md) — check stack-specific auto-discard patterns before including findings.
> - **CLI Finding Verification** (universal.md) — 5-step protocol for every CLI tool finding.
> - **YAGNI Check** (universal.md) — verify recommendations are needed before suggesting "add X".
> - **Anti-Rationalization Rules** (universal.md) — do not skip checks or soften findings.

Applies when `*.csproj`, `*.sln`, or `global.json` detected.
All commands assume `cd {solution_root}`.

---

## Level 1: Quick

### Build + tests
```bash
dotnet build --no-incremental 2>&1
dotnet test --no-build 2>&1
```

### Lint (Roslyn analyzers)
```bash
dotnet build /p:TreatWarningsAsErrors=true 2>&1
# Or with dotnet-format:
dotnet format --verify-no-changes 2>&1
```

### Dependency vulnerabilities
```bash
dotnet list package --vulnerable --include-transitive 2>&1
# Or universal (verify version first — v0.69.4-6 compromised, see tools.md):
trivy version 2>&1 | head -1
trivy fs --scanners vuln --severity HIGH,CRITICAL . 2>&1
```

**Pass criteria:** 0 errors, 0 critical/high vulnerabilities.

---

## Level 2: Full (includes Level 1)

### Security scan
```bash
# .NET security analyzers (if referenced in csproj)
dotnet build /p:EnableNETAnalyzers=true /p:AnalysisLevel=latest 2>&1

# Also recommended: semgrep (catches different patterns than Roslyn analyzers)
semgrep --config=auto . 2>&1
```

### Outdated packages
```bash
dotnet list package --outdated 2>&1
dotnet-outdated-tool 2>&1
```

### Deprecated packages
```bash
dotnet list package --deprecated 2>&1
```

### Unused packages
```bash
# Requires snitch tool
dotnet tool install -g snitch
snitch 2>&1
```

### Code coverage
```bash
dotnet test --collect:"XPlat Code Coverage" 2>&1
# Report: dotnet tool install -g dotnet-reportgenerator-globaltool
# reportgenerator -reports:**/coverage.cobertura.xml -targetdir:coveragereport
```

### Secrets scan
```bash
gitleaks detect --source . --no-git -v 2>&1
```

---

## Level 2: Code Review (Opus agents)

> **Reviewer mapping:** Security checks → diff-scanner + impact-reviewer. Concurrency → diff-scanner + history-reviewer. Resource leaks → diff-scanner. Convention compliance → convention-checker. Stale comments/TODOs → comment-checker.

### Security review

- **SQL injection:** string interpolation in SQL (`$"SELECT ... WHERE id = {id}"`)
  - Must use parameterized queries: `command.Parameters.AddWithValue()` or EF Core LINQ
- **Deserialization:** `BinaryFormatter` (banned — RCE risk), `JsonSerializer` without type restrictions
  - Use `System.Text.Json` with `[JsonSerializable]` source gen or explicit type
- **Path traversal:** `Path.Combine(basePath, userInput)` without `Path.GetFullPath()` + prefix check
- **XSS (Blazor/Razor):** `@Html.Raw(userInput)`, `MarkupString(userInput)`
- **SSRF:** `HttpClient.GetAsync(userUrl)` without URL scheme validation
- **CORS:** `AllowAnyOrigin()` with `AllowCredentials()` (dangerous combination)
- **Connection strings:** hardcoded in code (should be in config with User Secrets / Key Vault)
- **ASP.NET-specific:**
  - Missing `[ValidateAntiForgeryToken]` on POST actions
  - `[AllowAnonymous]` on sensitive endpoints
  - `app.UseDeveloperExceptionPage()` in production
  - Missing `app.UseHsts()` / `app.UseHttpsRedirection()`
  - Custom auth middleware instead of Identity/OIDC

### Concurrency

- `async void` methods (exceptions crash process — must be `async Task`)
- `.Result` / `.Wait()` on Task (deadlock risk — use `await`)
- `lock` on `this` or `typeof(T)` (should lock on private `object`)
- Shared `static` mutable state without `lock` or `Interlocked`
- `Dictionary<>` shared across threads (use `ConcurrentDictionary`)
- `HttpClient` created per request (use `IHttpClientFactory` — socket exhaustion)
- `SemaphoreSlim` without `try/finally` release pattern
- `CancellationToken` not passed through async chain
- `Task.Run()` in ASP.NET (steals ThreadPool threads from request processing)
- Fire-and-forget `Task` without exception observation (`TaskScheduler.UnobservedTaskException`)

### Resource management

- `IDisposable` not disposed (no `using` statement)
- `HttpClient` not via `IHttpClientFactory` (socket leak)
- `DbContext` with wrong lifetime (Scoped, not Singleton)
- `StreamReader`/`StreamWriter` not in `using`
- `Timer` without `Dispose`
- Unsubscribed event handlers (memory leak via strong reference)
- `CancellationTokenSource` not disposed

### Error handling

- Empty `catch` blocks
- `catch (Exception ex)` without re-throw or logging
- `throw ex;` instead of `throw;` (loses stack trace)
- Exception in finally block hiding original exception
- Business logic in catch blocks
- `Task` without exception observation (unobserved task exception)

### Quick reference: vulnerability grep patterns

| Pattern | Risk | Severity |
|---------|------|----------|
| `BinaryFormatter` | Deserialization RCE (banned) | CRITICAL |
| `Process.Start` with user input | Command injection | CRITICAL |
| `[AllowAnonymous]` on sensitive endpoints | Missing auth | HIGH |
| `async void` (non-event-handler) | Unhandled exceptions | HIGH |
| `.Result` / `.Wait()` | Deadlock risk | HIGH |
| `new HttpClient()` in loop | Socket exhaustion | HIGH |
| `SqlCommand` with string concat | SQL injection | CRITICAL |
| `Html.Raw()` with user data | XSS | HIGH |
| `TempData` with sensitive info | Data exposure | MEDIUM |
| `AddCors(o => o.AllowAnyOrigin())` | Permissive CORS | HIGH |

---

## Level 3: Deep (includes Level 2)

> .NET 8+ NativeAOT: If project uses AOT compilation, verify [JsonSerializable] source generators are used (reflection-based serialization breaks in AOT). Check for dynamic type loading patterns.

> .NET 8+ Minimal APIs: Verify endpoint filters for auth/validation (no automatic [Authorize] like controllers). Check for missing .RequireAuthorization() on sensitive endpoints.

### Architecture

- Circular project references
- God class (>500 lines)
- Mixing business logic with infrastructure (EF queries in controllers)
- Missing dependency injection (manual `new` of services)
- Static classes/methods for stateful operations
- `#region` overuse (code organization smell)

### ASP.NET Core specific

<details><summary>ASP.NET Core checks</summary>

- Middleware pipeline order correct (Auth before Authorization before Endpoints)
- `IOptions<T>` / `IOptionsSnapshot<T>` for configuration (not raw strings)
- Health checks configured (`app.MapHealthChecks`)
- Response compression enabled
- Rate limiting configured (`app.UseRateLimiter`)
- CORS policy properly scoped (not global `AllowAnyOrigin`)
- Minimal API vs Controllers: consistent pattern
- `ProblemDetails` for error responses (RFC 7807)
- Output caching for GET endpoints where appropriate
- Graceful shutdown: `IHostApplicationLifetime` handlers

</details>

### Entity Framework Core

<details><summary>EF Core checks</summary>

- No `ToList()` before `Where()` (loads all data, then filters in memory)
- `AsNoTracking()` for read-only queries
- No `Include()` without filter (loading entire related collection)
- Migrations have both Up and Down methods
- No `ExecuteSqlRaw` with string interpolation (SQL injection)
- `DbContext` pooling configured (`AddDbContextPool`)
- Connection resiliency for SQL Server (`EnableRetryOnFailure`)
- No lazy loading in APIs (N+1 serialization)

</details>

### Performance

- `string` concatenation in loop (use `StringBuilder` or `string.Join`)
- LINQ `.Count() > 0` instead of `.Any()`
- Boxing in hot paths (value type cast to `object`)
- `Regex` without `RegexOptions.Compiled` for reused patterns (or source generators)
- Large objects on LOH without pooling (`ArrayPool<T>`)
- Allocations in hot paths (use `Span<T>`, `Memory<T>`, stackalloc)
- Missing `ConfigureAwait(false)` in library code (context capture overhead)

### Blazor-specific (if applicable)

<details><summary>Blazor checks</summary>

- `StateHasChanged()` called too frequently (re-render overhead)
- JS interop without `IJSRuntime` (no isolation)
- Large component without virtualization (`<Virtualize>`)
- No error boundary (`<ErrorBoundary>`)
- Auth state not checked before render
- `NavigationManager.NavigateTo` without validation

</details>

### License compliance
```bash
dotnet-project-licenses -i . 2>&1
# Or: trivy fs --scanners license . 2>&1
```

### Dependency freshness
```bash
dotnet list package --outdated 2>&1
```
