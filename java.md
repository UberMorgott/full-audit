# Java / Kotlin (JVM) Audit Checks

> **Cross-references:** [README.md](README.md) (orchestration), [universal.md](universal.md) (language-agnostic checks).
>
> **Required reading:**
> - **Confidence Scoring** (README.md) — 0-100 per finding. Thresholds: L1≥75, L2≥60, L3≥40.
> - **False Positive Detection** (universal.md) — check stack-specific auto-discard patterns before including.
> - **CLI Finding Verification** (universal.md) — 5-step protocol per CLI tool finding.
> - **YAGNI Check** (universal.md) — verify need before suggesting additions.
> - **Anti-Rationalization Rules** (universal.md) — no skipping checks or softening findings.

Applies when `pom.xml`, `build.gradle`/`build.gradle.kts`, or `*.java`/`*.kt` detected.
All commands assume `cd {project_root}`.

---

## Level 1: Quick

### Build + tests

**Maven:**
```bash
mvn compile -q 2>&1
mvn test -q 2>&1
```

**Gradle:**
```bash
./gradlew build 2>&1
./gradlew test 2>&1
```

### Lint / static analysis

**Maven (if configured):**
```bash
mvn checkstyle:check -q 2>&1   # pin maven-checkstyle-plugin 3.6.0 + checkstyle engine 13.4.2 in pom.xml
mvn pmd:check -q 2>&1          # pin maven-pmd-plugin 3.27.0 + pmd-java 7.25.0 in pom.xml
```

**Gradle:**
```bash
./gradlew check 2>&1
# Kotlin detekt:
./gradlew detekt 2>&1
```

### Dependency vulnerabilities
```bash
# OWASP Dependency-Check (if plugin configured) — set NVD_API_KEY to avoid 403/slow updates
mvn -B org.owasp:dependency-check-maven:12.2.2:check 2>&1
# Gradle: plugin id 'org.owasp.dependencycheck' version '12.2.2'
./gradlew dependencyCheckAnalyze 2>&1
# Universal (verify version — v0.69.4-6 compromised, see tools.md):
trivy version 2>&1 | head -1
trivy fs --scanners vuln --severity HIGH,CRITICAL . 2>&1
```

### JDK currency
```bash
java --version 2>&1
```
> If dependency-check reports JDK vulns, update JDK. Check adoptium.net for latest LTS patch.

**Pass criteria:** 0 errors, 0 critical/high vulnerabilities.

---

## Level 2: Full (includes L1)

### SpotBugs

**Maven:**
```bash
mvn spotbugs:check 2>&1
```

**Gradle:**
```bash
./gradlew spotbugsMain 2>&1
```

Key patterns:
- `NP_NULL_ON_SOME_PATH` — null deref
- `SQL_NONCONSTANT_STRING_PASSED_TO_EXECUTE` — SQL injection
- `RCN_REDUNDANT_NULLCHECK` — redundant null check
- `EI_EXPOSE_REP` — mutable object exposed
- `MS_SHOULD_BE_FINAL` — mutable static field

### Error Prone

> Requires compiler plugin. If configured:
```bash
mvn compile -Derror-prone 2>&1
```

### Dependency tree
```bash
# Maven
mvn dependency:tree 2>&1
mvn dependency:analyze 2>&1    # unused + used-undeclared

# Gradle
./gradlew dependencies --configuration runtimeClasspath 2>&1
```

### Code coverage (JaCoCo)
```bash
# Maven (if jacoco plugin configured)
mvn jacoco:report -q 2>&1
# Check: target/site/jacoco/index.html

# Gradle
./gradlew jacocoTestReport 2>&1
# Check: build/reports/jacoco/test/html/index.html
```

### Semgrep SAST
```bash
semgrep --config=auto . 2>&1
```

### Secrets scan
> Skip if Trivy used.
```bash
gitleaks detect --source . --no-git --redact --report-path gitleaks-report.json 2>&1   # add gitleaks-report.json to .gitignore
```

---

## Level 2: Code Review (Opus agents)

> **Reviewer mapping:** Security → diff-scanner + impact-reviewer. Concurrency → diff-scanner + history-reviewer. Resource leaks → diff-scanner. Conventions → convention-checker. Stale comments/TODOs → comment-checker.

### Security

- **SQL injection:** string concat in SQL (`"SELECT * FROM users WHERE id = " + id`) — use PreparedStatement / JPA parameterized / named params
- **Deserialization:** `ObjectInputStream.readObject()` on untrusted data (RCE) — use JSON/Protobuf or whitelist via `ObjectInputFilter`
- **XXE:** `DocumentBuilderFactory`/`SAXParser` without disabling external entities
  ```java
  // REQUIRED:
  factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
  ```
- **Path traversal:** `new File(basePath + userInput)` without canonical path check
- **SSRF:** `URL.openConnection()`/`HttpClient` with user-supplied URL
- **Log injection:** user input logged unsanitized (log forging)
- **Spring-specific:**
  - `@RequestMapping` without method restriction (accepts all HTTP methods)
  - Missing `@Valid`/`@Validated` on request body
  - `@CrossOrigin("*")` on controller
  - Actuator endpoints exposed without auth
  - `server.error.include-stacktrace=always` in prod

### Concurrency

- `synchronized` on wrong object (local var, `this` in public class)
- `HashMap`/`ArrayList` shared across threads without sync (use `ConcurrentHashMap`)
- Double-checked locking without `volatile`
- `Thread.sleep()` in synchronized block (holds lock)
- `ExecutorService` without `shutdown()` (thread leak)
- `CompletableFuture` without `exceptionally()`/`handle()` (swallowed exceptions)
- Mutable fields without `volatile`/`synchronized` in concurrent context
- `SimpleDateFormat` shared across threads (not thread-safe)
- **Kotlin coroutines:** `GlobalScope.launch` (leak — use structured concurrency: `viewModelScope`, `lifecycleScope`, custom `CoroutineScope`), `runBlocking` in prod (blocks thread pool)

### Resource leaks

- JDBC `Connection`/`Statement`/`ResultSet` without try-with-resources
- `InputStream`/`OutputStream` without close
- `ExecutorService` not shut down
- Spring `@Async` without `ThreadPoolTaskExecutor` config (unbounded pool)
- HTTP client connections without pool config
- File locks not released in finally

### Error handling

- Catching `Exception`/`Throwable` (too broad)
- Empty catch blocks (`catch (Exception e) {}`)
- `e.printStackTrace()` instead of proper logging
- `throws Exception` on signature (too broad)
- Business logic in catch blocks
- Checked exceptions wrapped in `RuntimeException` without reason

### Vulnerability grep patterns

| Pattern | Risk | Severity |
|---------|------|----------|
| `ObjectInputStream` | Deserialization RCE | CRITICAL |
| `Runtime.getRuntime().exec` | Command injection | CRITICAL |
| `@CrossOrigin("*")` | Permissive CORS | HIGH |
| `@Transactional` missing on service methods | Data inconsistency | HIGH |
| `GlobalScope.launch` (Kotlin) | Unstructured concurrency | HIGH |
| `runBlocking` in coroutine context (Kotlin) | Thread starvation | HIGH |
| `new Random()` for security | Predictable values | HIGH |
| `catch (Exception e) {}` | Swallowed exceptions | MEDIUM |
| `.password` in properties files | Hardcoded credentials | CRITICAL |
| `spring.jpa.show-sql=true` | SQL in prod logs | MEDIUM |

---

## Level 3: Deep (includes L2)

> JDK 21-23: Virtual Threads must NOT hold locks during blocking I/O. `synchronized` blocks pin virtual threads to platform threads (use `ReentrantLock` instead). JDK 24+ (JEP 491) no longer pins on `synchronized` — pinning fix not backported, so still applies on 21-23.

> GraalVM Native Image: verify reflection config, serialization registration, resource inclusion in native-image.properties.

> Verify log4j ≥2.17.1 (CVE-2021-44228 Log4Shell + follow-ups). Check JNDI lookup patterns in logging config.

### Architecture

- Circular package dependencies
- God class (>500 lines, >20 methods)
- Anemic domain model (DTOs with only getters/setters, all logic in services)
- Service layer doing repository's job (raw SQL in service)
- Controller doing business logic (should delegate to service)
- Package-by-layer vs package-by-feature (prefer feature)

### Spring Boot specific

<details><summary>Spring Boot checks</summary>

- Profile config: `application-prod.yml` separate from `application.yml`
- `@Transactional` on service layer, not controller
- `@Transactional(readOnly=true)` for reads
- No `@Autowired` on fields (use constructor injection)
- Bean scope correct (singleton vs prototype vs request)
- Health check (`/actuator/health`) configured
- Graceful shutdown (`server.shutdown=graceful`)
- Connection pool configured (HikariCP defaults reviewed)
- Cache config (if `@Cacheable` used)
- Security filter chain properly configured

</details>

### Performance

- N+1 queries (JPA `@OneToMany` without `@BatchSize`/`JOIN FETCH`)
- `SELECT *` (fetch only needed columns)
- Missing indexes on frequently queried columns
- `String` concat in loop (use `StringBuilder`)
- Autoboxing in hot paths (`int` vs `Integer`)
- Stream operations with side effects
- Large collections fully in memory (use pagination/streaming)

### Kotlin-specific

<details><summary>Kotlin checks</summary>

- `!!` (non-null assertion) — use safe calls (`?.`) or `requireNotNull`
- `var` where `val` works (prefer immutability)
- Java interop: `@JvmStatic`, `@JvmField` where needed
- `GlobalScope` usage (use structured concurrency)
- `runBlocking` in prod (blocks thread)
- Data class with mutable properties
- Sealed class not used where enum + data needed

</details>

### License compliance
```bash
# Maven
mvn license:third-party-report 2>&1

# Gradle (if license plugin configured)
./gradlew generateLicenseReport 2>&1

# Universal:
trivy fs --scanners license . 2>&1
```

### Dependency freshness
```bash
# Maven
mvn versions:display-dependency-updates -q 2>&1

# Gradle
./gradlew dependencyUpdates 2>&1
```
