# Java / Kotlin (JVM) Audit Checks

Applies when `pom.xml` (Maven), `build.gradle` / `build.gradle.kts` (Gradle), or `*.java`/`*.kt` detected.
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
mvn checkstyle:check -q 2>&1
mvn pmd:check -q 2>&1
```

**Gradle:**
```bash
./gradlew check 2>&1
# Or if detekt for Kotlin:
./gradlew detekt 2>&1
```

### Dependency vulnerabilities
```bash
# OWASP Dependency-Check (if plugin configured)
mvn org.owasp:dependency-check-maven:check 2>&1
# Or Gradle:
./gradlew dependencyCheckAnalyze 2>&1
# Or universal (verify version first — v0.69.4-6 compromised, see tools.md):
trivy version 2>&1 | head -1
trivy fs --scanners vuln --severity HIGH,CRITICAL . 2>&1
```

**Pass criteria:** 0 errors, 0 critical/high vulnerabilities.

---

## Level 2: Full (includes Level 1)

### SpotBugs (FindBugs successor)

**Maven:**
```bash
mvn spotbugs:check 2>&1
```

**Gradle:**
```bash
./gradlew spotbugsMain 2>&1
```

Key bug patterns:
- `NP_NULL_ON_SOME_PATH` — null dereference
- `SQL_NONCONSTANT_STRING_PASSED_TO_EXECUTE` — SQL injection
- `RCN_REDUNDANT_NULLCHECK` — redundant null check
- `EI_EXPOSE_REP` — mutable object exposed
- `MS_SHOULD_BE_FINAL` — mutable static field

### Error Prone (compile-time checks)

> Requires compiler plugin. If configured:
```bash
mvn compile -Derror-prone 2>&1
```

### Dependency tree analysis
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
```bash
gitleaks detect --source . --no-git -v 2>&1
```

---

## Level 2: Code Review (Opus agents)

### Security review

- **SQL injection:** string concatenation in SQL (`"SELECT * FROM users WHERE id = " + id`)
  - Must use PreparedStatement / JPA parameterized queries / named parameters
- **Deserialization:** `ObjectInputStream.readObject()` on untrusted data (RCE risk)
  - Use JSON/Protobuf instead, or whitelist classes via `ObjectInputFilter`
- **XXE:** `DocumentBuilderFactory` / `SAXParser` without disabling external entities
  ```java
  // REQUIRED:
  factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
  ```
- **Path traversal:** `new File(basePath + userInput)` without canonical path check
- **SSRF:** `URL.openConnection()` / `HttpClient` with user-supplied URL
- **Log injection:** user input logged without sanitization (log forging)
- **Spring-specific:**
  - `@RequestMapping` without method restriction (accepts all HTTP methods)
  - Missing `@Valid` / `@Validated` on request body
  - `@CrossOrigin("*")` on controller
  - Actuator endpoints exposed without auth
  - `server.error.include-stacktrace=always` in prod

### Concurrency

- `synchronized` on wrong object (e.g., on local variable, on `this` in public class)
- `HashMap`/`ArrayList` shared between threads without synchronization (use `ConcurrentHashMap`)
- Double-checked locking without `volatile`
- `Thread.sleep()` in synchronized block (holds lock while sleeping)
- `ExecutorService` without `shutdown()` (thread leak)
- `CompletableFuture` without `exceptionally()` or `handle()` (swallowed exceptions)
- Mutable fields without `volatile` or `synchronized` in concurrent context
- `SimpleDateFormat` shared between threads (not thread-safe)
- **Kotlin coroutines (if applicable):** `GlobalScope.launch` (goroutine leak — use structured concurrency: `viewModelScope`, `lifecycleScope`, or custom `CoroutineScope`), `runBlocking` in production code (blocks thread pool)

### Resource leaks

- JDBC `Connection`/`Statement`/`ResultSet` without try-with-resources
- `InputStream`/`OutputStream` without close
- `ExecutorService` not shut down
- Spring `@Async` without `ThreadPoolTaskExecutor` configuration (unbounded pool)
- HTTP client connections without pool configuration
- File locks not released in finally

### Error handling

- Catching `Exception` or `Throwable` (too broad)
- Empty catch blocks (`catch (Exception e) {}`)
- `e.printStackTrace()` instead of proper logging
- `throws Exception` on method signature (too broad)
- Business logic in catch blocks
- Checked exceptions wrapped in `RuntimeException` without reason

---

## Level 3: Deep (includes Level 2)

### Architecture

- Circular package dependencies
- God class (>500 lines, >20 methods)
- Anemic domain model (DTOs with only getters/setters, all logic in services)
- Service layer doing repository's job (raw SQL in service)
- Controller doing business logic (should delegate to service)
- Package-by-layer vs package-by-feature (prefer feature)

### Spring Boot specific

<details><summary>Spring Boot checks</summary>

- Profile configuration: `application-prod.yml` separate from `application.yml`
- `@Transactional` on correct layer (service, not controller)
- `@Transactional(readOnly=true)` for read operations
- No `@Autowired` on fields (use constructor injection)
- Bean scope correct (singleton vs prototype vs request)
- Health check endpoint (`/actuator/health`) configured
- Graceful shutdown enabled (`server.shutdown=graceful`)
- Connection pool configured (HikariCP defaults reviewed)
- Cache configuration (if `@Cacheable` used)
- Security filter chain properly configured

</details>

### Performance

- N+1 query problem (JPA `@OneToMany` without `@BatchSize` or `JOIN FETCH`)
- `SELECT *` in queries (fetch only needed columns)
- Missing database indexes on frequently queried columns
- `String` concatenation in loop (use `StringBuilder`)
- Autoboxing in hot paths (`int` vs `Integer`)
- Stream operations with side effects
- Large collections loaded fully into memory (use pagination / streaming)

### Kotlin-specific

<details><summary>Kotlin checks</summary>

- `!!` (non-null assertion) — should use safe calls (`?.`) or `requireNotNull`
- `var` where `val` works (immutability preferred)
- Java interop: `@JvmStatic`, `@JvmField` where needed
- Coroutine scope: `GlobalScope` usage (use structured concurrency)
- `runBlocking` in production code (blocks thread)
- Data class with mutable properties
- Sealed class not used where enum + data is needed

</details>

### License compliance
```bash
# Maven
mvn license:third-party-report 2>&1

# Gradle (if license plugin configured)
./gradlew generateLicenseReport 2>&1

# Or universal:
trivy fs --scanners license . 2>&1
```

### Dependency freshness
```bash
# Maven
mvn versions:display-dependency-updates -q 2>&1

# Gradle
./gradlew dependencyUpdates 2>&1
```
