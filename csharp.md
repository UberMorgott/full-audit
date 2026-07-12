# C# / .NET Audit Checks

> **Cross-references:** [README.md](README.md) (orchestration), [universal.md](universal.md) (language-agnostic).
>
> **Required reading:**
> - **Confidence Scoring** (README.md) — 0-100 per finding. L1≥75, L2≥60, L3≥40.
> - **False Positive Detection** (universal.md) — stack-specific auto-discard patterns.
> - **CLI Finding Verification** (universal.md) — 5-step protocol per CLI finding.
> - **YAGNI Check** (universal.md) — verify need before suggesting additions.
> - **Anti-Rationalization Rules** (universal.md) — no skipping/softening findings.

Applies when `*.csproj`, `*.sln`, or `global.json` detected.
All commands assume `cd {solution_root}`.

> **Stack sub-profile (gate the web tables).** The L2/L3 web sections below — SQLi, XSS/Blazor/Razor, ASP.NET-specific, Entity Framework Core, Blazor-specific — are conditional on detecting the matching package: `Microsoft.AspNetCore.*` / `Microsoft.EntityFrameworkCore.*` / Blazor. A **Unity/Harmony/game-mod or library profile** (`net47x`/`netstandard`, no ASP.NET/EF/Blazor, hand-rolled `BinaryReader`/`BinaryWriter` codecs, no `System.Text.Json`) SUPPRESSES those tables wholesale — clean documented SKIP, one-line limitation each, NOT findings/BLOCKERs. Cross-ref universal.md → Stack Profile & Applicability Gating (`has_http_surface`/`has_db`).

---

## Level 1: Quick

### Build + tests
```bash
dotnet build --no-incremental 2>&1
dotnet test --no-build 2>&1
```

> **Split-test-suite coverage — report pure vs runtime-gated separately.** A test project that needs an external runtime (game/engine DLLs, GPU, live host) CANNOT run here; only the BCL-pure/mockable suites do. Report the two buckets explicitly (`pure: N passed`, `runtime-gated: SKIPPED — needs <runtime>`) so "tests PASS" is NOT read as "the reflection/runtime glue is verified." That runtime-gated layer often has NO automated coverage by construction — say so; it is frequently the project's dominant risk.

### Lint (Roslyn analyzers)
```bash
dotnet build /p:TreatWarningsAsErrors=true 2>&1
# Or SDK built-in `dotnet format` (no install; standalone dotnet-format tool is deprecated):
dotnet format --verify-no-changes 2>&1
```

### Dependency vulnerabilities
> **requires:** `PackageReference` or `packages.config`. A **local-DLL-reference project** (`<Reference>` + `<HintPath>` with `<Private>false</Private>`; deps are game-/vendor-shipped binaries with no version metadata) has no manifest for `dotnet list package` to read — every `--vulnerable`/`--outdated`/`--deprecated` is a no-op. Downshift to a **manual DLL/assembly-version note** (record the shipped versions you can determine) + one-line limitation; do NOT report the no-op as a BLOCKER. See universal.md → Supply Chain (local-DLL downshift).
```bash
dotnet list package --vulnerable --include-transitive 2>&1
# Universal — ⚠️ Trivy: pin `0.69.3` (v0.69.4–0.69.6 compromised, supply-chain; do NOT bump until 0.70.0; detail: tools.md):
trivy version 2>&1 | head -1
trivy fs --scanners vuln --severity HIGH,CRITICAL . 2>&1
```

### .NET SDK currency
```bash
dotnet --version 2>&1
```
> If `dotnet list package --vulnerable` reports SDK issues, update SDK via dotnet.microsoft.com/download.

**Pass criteria:** 0 errors, 0 critical/high vulns.

---

## Level 2: Full (includes Level 1)

### Security scan
```bash
# .NET security analyzers (if in csproj)
dotnet build /p:EnableNETAnalyzers=true /p:AnalysisLevel=latest 2>&1

# semgrep (catches patterns Roslyn misses)
semgrep --config=auto . 2>&1
```

### Outdated packages
> **requires:** `PackageReference`/`packages.config` (a resolvable NuGet manifest). A local-DLL-only project makes Outdated / Deprecated / Removable-transitive — and `dotnet-outdated-tool` / `NuGone` / the license tooling below — all no-ops; skip each with a one-line limitation (see L1 Dependency vulnerabilities → local-DLL downshift), NOT a BLOCKER.
```bash
dotnet list package --outdated 2>&1
dotnet-outdated 2>&1
```

### Deprecated packages
```bash
dotnet list package --deprecated 2>&1
```

### Removable transitive package references
> Flags PackageReferences that are pulled in transitively and can be dropped from the project (not truly "unused" packages).
```bash
# NuGone (replaces deprecated snitch)
dotnet tool install --global NuGone --version 2.1.1
nugone 2>&1
```

### Code coverage
```bash
dotnet test --collect:"XPlat Code Coverage" 2>&1
# Report: dotnet tool install -g dotnet-reportgenerator-globaltool
# reportgenerator -reports:**/coverage.cobertura.xml -targetdir:coveragereport
```

### Secrets scan
> Skip if Trivy used.
```bash
gitleaks detect --source . --no-git --redact --report-path gitleaks-report.log 2>&1
```

---

## Level 2: Code Review (DEEP agents)

> **Reviewer mapping:** Security → diff-scanner + impact-reviewer. Concurrency → diff-scanner + history-reviewer. Resource leaks → diff-scanner. Conventions → convention-checker. Stale comments/TODOs → comment-checker.

### Security review

> **Applicability:** the web-specific items (SQLi, XSS/Blazor/Razor, SSRF, CORS, ASP.NET-specific) require ASP.NET/EF/Blazor detection — skip cleanly on a non-web profile (see Stack sub-profile at top). Deserialization (`BinaryFormatter`), `Process.Start`+user-input, and hardcoded connection strings/secrets apply to ANY C# and are always checked. For hand-rolled binary codecs also run universal.md → Deserialization Safety (untrusted length-prefix → allocation).

- **SQL injection:** string interpolation in SQL (`$"SELECT ... WHERE id = {id}"`)
  - Use parameterized queries: `command.Parameters.AddWithValue()` or EF Core LINQ
- **Deserialization:** `BinaryFormatter` (banned — RCE), `JsonSerializer` without type restrictions
  - Use `System.Text.Json` with `[JsonSerializable]` source gen or explicit type
- **Path traversal:** `Path.Combine(basePath, userInput)` without `Path.GetFullPath()` + prefix check
- **XSS (Blazor/Razor):** `@Html.Raw(userInput)`, `MarkupString(userInput)`
- **SSRF:** `HttpClient.GetAsync(userUrl)` without URL scheme validation
- **CORS:** `AllowAnyOrigin()` + `AllowCredentials()` (dangerous combo)
- **Connection strings:** hardcoded (use config + User Secrets / Key Vault)
- **ASP.NET-specific:**
  - Missing `[ValidateAntiForgeryToken]` on POST actions
  - `[AllowAnonymous]` on sensitive endpoints
  - `app.UseDeveloperExceptionPage()` in production
  - Missing `app.UseHsts()` / `app.UseHttpsRedirection()`
  - Custom auth middleware instead of Identity/OIDC

### Concurrency

> **Concurrency model first.** The items below assume TPL/ASP.NET (threads, `ConcurrentDictionary`, `SemaphoreSlim`, `Task.Run`). A **Unity/game-loop + Steam/network-callback + coroutine** project has a different model — the real risk is off-thread callbacks not marshalled to the main thread, coroutine lifetime/guards, and barrier stuck-states, NOT missing locks. See universal.md → Concurrency Safety (single-threaded UI/game-loop profile) + Liveness & Recovery.

- `async void` (exceptions crash process — must be `async Task`)
- `.Result` / `.Wait()` on Task (deadlock — use `await`)
- `lock` on `this`/`typeof(T)` (lock on private `object`)
- Shared `static` mutable state without `lock`/`Interlocked`
- `Dictionary<>` across threads (use `ConcurrentDictionary`)
- `HttpClient` per request (use `IHttpClientFactory` — socket exhaustion)
- `SemaphoreSlim` without `try/finally` release
- `CancellationToken` not passed through async chain
- `Task.Run()` in ASP.NET (steals ThreadPool threads)
- Fire-and-forget `Task` without exception observation

### Resource management

- `IDisposable` not disposed (no `using`)
- `HttpClient` not via `IHttpClientFactory` (socket leak)
- `DbContext` wrong lifetime (Scoped, not Singleton)
- `StreamReader`/`StreamWriter` not in `using`
- `Timer` without `Dispose`
- Unsubscribed event handlers (memory leak via strong ref)
- `CancellationTokenSource` not disposed

### Error handling

- Empty `catch` blocks
- `catch (Exception ex)` without re-throw/logging
- `throw ex;` instead of `throw;` (loses stack trace)
- Exception in finally hiding original exception
- Business logic in catch blocks
- `Task` without exception observation

### Vulnerability grep patterns

| Pattern | Risk | Severity |
|---------|------|----------|
| `BinaryFormatter` | Deserialization RCE (banned) | CRITICAL |
| `Process.Start` + user input | Command injection | CRITICAL |
| `[AllowAnonymous]` on sensitive endpoints | Missing auth | HIGH |
| `async void` (non-event-handler) | Unhandled exceptions | HIGH |
| `.Result` / `.Wait()` | Deadlock risk | HIGH |
| `new HttpClient()` in loop | Socket exhaustion | HIGH |
| `SqlCommand` + string concat | SQL injection | CRITICAL |
| `Html.Raw()` + user data | XSS | HIGH |
| `TempData` + sensitive info | Data exposure | MEDIUM |
| `AddCors(o => o.AllowAnyOrigin())` | Permissive CORS | HIGH |

---

## Level 3: Deep (includes Level 2)

> .NET 8+ NativeAOT: verify `[JsonSerializable]` source generators (reflection serialization breaks in AOT). Check dynamic type loading.

> .NET 8+ Minimal APIs: verify endpoint filters for auth/validation (no automatic `[Authorize]`). Check missing `.RequireAuthorization()`.

### Architecture

- Circular project references
- God class (>500 lines)
- Business logic mixed with infrastructure (EF queries in controllers)
- Missing DI (manual `new` of services)
- Static classes/methods for stateful operations
- `#region` overuse (code organization smell)

### ASP.NET Core specific

<details><summary>ASP.NET Core checks</summary>

- Middleware pipeline order (Auth → Authorization → Endpoints)
- `IOptions<T>` / `IOptionsSnapshot<T>` for config (not raw strings)
- Health checks (`app.MapHealthChecks`)
- Response compression enabled
- Rate limiting (`app.UseRateLimiter`)
- CORS properly scoped (not global `AllowAnyOrigin`)
- Minimal API vs Controllers: consistent pattern
- `ProblemDetails` for errors (RFC 7807)
- Output caching for GET endpoints where appropriate
- Graceful shutdown: `IHostApplicationLifetime` handlers

</details>

### Entity Framework Core

> **Applicability:** requires `Microsoft.EntityFrameworkCore.*` (`has_db`). No EF/ORM → skip cleanly (one-line limitation). Same gate applies to the ASP.NET Core and Blazor sub-sections here.

<details><summary>EF Core checks</summary>

- No `ToList()` before `Where()` (loads all, filters in memory)
- `AsNoTracking()` for read-only queries
- No `Include()` without filter (loads entire related collection)
- Migrations have both Up and Down
- No `ExecuteSqlRaw` with string interpolation (SQL injection)
- `DbContext` pooling (`AddDbContextPool`)
- Connection resiliency for SQL Server (`EnableRetryOnFailure`)
- No lazy loading in APIs (N+1 serialization)

</details>

### Performance

- `string` concat in loop (use `StringBuilder`/`string.Join`)
- `.Count() > 0` instead of `.Any()`
- Boxing in hot paths (value type → `object`)
- Reused `Regex` not using `[GeneratedRegex]` source generator (.NET 7+); `RegexOptions.Compiled` is the legacy fallback
- Large objects on LOH without pooling (`ArrayPool<T>`)
- Allocations in hot paths (use `Span<T>`, `Memory<T>`, stackalloc)
- Missing `ConfigureAwait(false)` in library code

### Blazor-specific (if applicable)

<details><summary>Blazor checks</summary>

- `StateHasChanged()` called too often (re-render overhead)
- JS interop without `IJSRuntime` (no isolation)
- Large component without `<Virtualize>`
- No `<ErrorBoundary>`
- Auth state not checked before render
- `NavigationManager.NavigateTo` without validation

</details>

### License compliance
> **requires:** a package manager (`PackageReference`/`packages.config`). Local-DLL-only → no NuGet graph to scan; skip cleanly with a one-line limitation.
```bash
dotnet-project-licenses -i . 2>&1
# Or: trivy fs --scanners license . 2>&1
```

### Dependency freshness
```bash
dotnet list package --outdated 2>&1
```
