// ===========================================================================
// STALE SMOKE VARIANT — OUT OF SYNC; NOT AN OUTPUT-SHAPE GATE (as of 2026-07).
// This file DOES exist (correcting an earlier, false "no full-audit.smoke.js in
// this checkout" claim — it was searched for in the wrong dir). It is a full
// COPY of an OLDER full-audit.js fork with web-researcher disabled (see the
// SMOKE VARIANT note ~L717-721), taken BEFORE: the BUG-1..7 fixes, the P0
// `recommendation` / `root_cause` finding fields, and the P1 batch (`category`
// derivation, per-axis `scores`, systemic `crossReferencePass` + `related_ids`
// + `systemic_patterns`). Its `cleanFinding` and `output` object below
// therefore lack those keys ON PURPOSE — they are NOT a regression here.
// It has ZERO assert statements and ends with a bare top-level `return output`
// over free globals (agent/phase/log/parallel/args), so it runs ONLY inside the
// Workflow harness and CANNOT be executed or shape-checked via plain `node`
// (a module-mode `node --check` fails: "Illegal return statement" at `return
// output`). Consequently it cannot serve as the output-shape gate the
// RFC-INTEGRATION-PLAN Batch-2 step assumed.
//   => AUTHORITATIVE runtime + schema truth = full-audit.js. This variant is
//   intentionally DEFERRED; re-sync it from full-audit.js the next time the
//   web-researcher-disabled smoke variant is actually exercised.
// ===========================================================================
export const meta = {
  name: 'full-audit',
  description: 'Recall-first multi-wave read-only code audit (full-audit v1.10.8 engine). Consumes Phase-0 `args`, runs Wave 1 (CLI+research) -> Wave 2 (review) -> Wave 2.5 (reproduction) -> Wave 3 (deep+adversarial, L3) -> scoring -> fresh-evidence verification gate, and returns ONE structured findings object. Phase 0 and the fix phase stay in the conversational session.',
  phases: [
    { title: 'Validate', detail: 'strict args schema check; abort on failure' },
    { title: 'Wave 1', detail: 'cli-scanner per stack + universal + waste-scanner + web-researcher (FAST/RESEARCH)' },
    { title: 'Wave 2', detail: 'diff/history/comment/convention/impact reviewers (DEEP)' },
    { title: 'Wave 2.5', detail: 'reproduction agents on CRITICAL/HIGH (DEEP; verified mode or L3)' },
    { title: 'Wave 3', detail: 'stack/security/quality/logic/ui/arch reviewers + adversarial hunt (DEEP; L3)' },
    { title: 'Scoring', detail: 'confidence 0-100, reproduction override, threshold filter, recall-first demotion (FAST)' },
    { title: 'Verify', detail: 'Iron-Law fresh-evidence re-run on CRITICAL/HIGH + security; strip unverified phrases' },
    { title: 'Guard', detail: 'read-only safety guard: detect (+ revert if git_baseline given) any repo-tree changes the audit introduced' },
    { title: 'Assemble', detail: 'coverage + audit_limitations + summary; emit structured object' },
  ],
}

// ===========================================================================
// full-audit dynamic workflow — orchestration only. Audit DOMAIN LOGIC
// (severity, confidence, thresholds, report format, integrity rules, FP
// whitelist, Iron-Law verification gate, prohibited phrases) is preserved
// verbatim from full-audit README v1.10.8. Recall-first additions
// (suspected_unconfirmed, coverage block, adversarial hunt, depth funnel)
// are layered on top per the build spec — they EXTEND, never replace.
// ===========================================================================

// --- model tiers (README 412-416): FAST=haiku, RESEARCH=sonnet, DEEP=opus ---
const FAST = 'haiku', RESEARCH = 'sonnet', DEEP = 'opus'

// --- per-level confidence thresholds (README 894-900) ---
const THRESHOLD = { 1: 75, 2: 60, 3: 40, S: 60 }

// --- reproduction-signal score overrides (README 909-913) ---
// REPRODUCED -> floor 90; NOT_REPRODUCED -> cap 25, severity -1; SKIPPED_RUNTIME -> unchanged
const SEV_ORDER = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

// --- false-positive whitelist (README 936-946): auto-filter score = 0 ---
const FP_WHITELIST = [
  'pre-existing, unrelated to recent changes (diff mode)',
  'intentional patterns in CLAUDE.md or comments (// nolint: reason)',
  'CI/linter catches separately',
  'non-modified lines (diff mode / quick)',
  'test code intentionally mirroring anti-patterns',
  'generated code (protobuf, swagger, migrations)',
  'vendor/third-party (vendor/, node_modules/, third_party/)',
  'gofmt/format failures caused by CRLF vs LF line endings on Windows (core.autocrlf) — verify with a line-ending diff before reporting',
]

// --- prohibited unverified phrases (README 1090-1100, 473) ---
const PROHIBITED_PHRASES = [
  'appears to be', 'no issues found', 'should be fine', "i've verified",
  'everything looks good', 'tests are passing', 'all tests pass',
  'the fix works', 'looks good', 'seems fine', 'probably fine',
]

// --- MCP capability -> role map (README 704-712). Prefix is discovered at
//     runtime (plugin vs direct install); the EXPECTED prefix + liveness come
//     from args.tool_status.mcp. Sequential-Thinking prefix is fixed. ---
const SEQ_THINKING = 'mcp__sequential-thinking__sequentialthinking'

// --- per-stack pinned CLI catalog (tools.md v1.10.8). The cli-scanner agent
//     gets these EXACT commands; it still reads {spec_root}/{stack}.md for the
//     level-scoped checklist. Pins must match versions.lock. ---
const STACK_TOOLS = {
  go: {
    manifests: ['go.mod'],
    L1: [
      ['go build', 'go build ./... 2>&1'],
      ['go vet', 'go vet ./... 2>&1'],
      ['staticcheck@v0.7.0', 'staticcheck ./... 2>&1'],
      ['govulncheck@v1.3.0', 'govulncheck ./... 2>&1'],
      ['go test', 'go test -timeout 60s -count=1 ./... 2>&1'],
    ],
    L2: [
      ['golangci-lint@v2.12.2', 'golangci-lint run ./... --timeout 5m 2>&1'],
      ['gosec@v2.26.1', 'gosec ./... 2>&1  # post-filter //nolint:gosec'],
      ['deadcode@v0.45.0', 'deadcode ./... 2>&1'],
      ['go test -race', 'CGO_ENABLED=1 go test -race -timeout 120s ./... 2>&1'],
      ['gitleaks@v8.30.1', 'gitleaks detect --source . --redact --report-path "$TMP/gitleaks.json" 2>&1'],
      ['go mod verify', 'go mod verify; go mod tidy -diff 2>&1'],
    ],
    L3: [['go-licenses@v2.0.1', 'go-licenses report ./... 2>&1']],
  },
  python: {
    manifests: ['pyproject.toml', 'requirements.txt', 'setup.py', 'Pipfile'],
    L1: [
      ['ruff@0.15.15', 'ruff check src tests 2>&1'],
      ['pip-audit@2.10.0', 'pip-audit -r requirements.txt 2>&1'],
      ['pytest', 'python -m pytest --tb=short -q 2>&1'],
    ],
    L2: [
      ['bandit@1.9.4', 'bandit -r . -x ./.venv,./tests -f json 2>&1'],
      ['mypy@2.1.0', 'mypy . 2>&1'],
      ['vulture@2.16', 'vulture . --min-confidence 80 2>&1'],
      ['radon@6.0.1', 'radon cc . -a -nc 2>&1; radon mi . -nc 2>&1'],
      ['ruff format', 'ruff format --check . 2>&1; ruff check --select I . 2>&1'],
    ],
    L3: [['pip-licenses@5.5.5', 'pip-licenses --fail-on="GPL-2.0;AGPL-3.0;LGPL-3.0" 2>&1']],
  },
  frontend: {
    manifests: ['package.json'],
    L1: [
      ['build', '<pm> run build 2>&1  # pm detected from lockfile'],
      ['lint', '<pm> run lint 2>&1'],
      ['audit', '<pm> audit 2>&1  # npm/pnpm/yarn npm/bun'],
      ['tests', '<pm> test 2>&1  # vitest/jest/angular'],
    ],
    L2: [
      ['tsc', 'npx --yes vue-tsc@3.3.2 -b --noEmit 2>&1  # or: npx tsc --noEmit'],
      ['knip@6.14.2', 'npx --yes knip@6.14.2 --reporter compact --no-progress 2>&1'],
      ['gitleaks@8.30.1', 'gitleaks detect --source . --no-git --redact --report-format json --report-path "$TMP/gitleaks.json" 2>&1'],
    ],
    L3: [
      ['@axe-core/cli@4.11.3', 'npx --yes @axe-core/cli@4.11.3 "$URL" 2>&1  # needs dev server'],
      ['linkinator@7.6.1', 'npx --yes linkinator@7.6.1 "$URL" --recurse 2>&1'],
      ['license-checker-evergreen@6.3.1', 'npx --yes license-checker-evergreen@6.3.1 --failOn "GPL-2.0;AGPL-3.0" 2>&1'],
    ],
  },
  rust: {
    manifests: ['Cargo.toml'],
    L1: [
      ['cargo build', 'cargo build 2>&1'],
      ['clippy', 'cargo clippy -- -D warnings 2>&1'],
      ['cargo test', 'cargo test 2>&1'],
      ['cargo-audit@0.22.1', 'cargo audit 2>&1'],
      ['fmt', 'cargo fmt --check 2>&1'],
    ],
    L2: [
      ['cargo-deny@0.19.8', 'cargo deny check advisories licenses bans sources 2>&1'],
      ['cargo-geiger@0.13.0', 'cargo geiger --all-features 2>&1'],
      ['cargo-udeps@0.1.61', 'cargo +nightly udeps --all-targets 2>&1'],
      ['cargo-outdated@0.19.0', 'cargo outdated -R 2>&1'],
    ],
    L3: [['cargo-vet@0.10.2', 'cargo vet 2>&1']],
  },
  java: {
    manifests: ['pom.xml', 'build.gradle', 'build.gradle.kts'],
    L1: [
      ['build+test', 'mvn -q compile test 2>&1  # or ./gradlew build test'],
      ['checkstyle@3.6.0', 'mvn -q checkstyle:check 2>&1'],
      ['owasp dependency-check@12.2.2', 'mvn -B org.owasp:dependency-check-maven:12.2.2:check 2>&1  # NVD_API_KEY'],
    ],
    L2: [
      ['spotbugs', 'mvn spotbugs:check 2>&1  # or ./gradlew spotbugsMain'],
      ['pmd@3.27.0', 'mvn -q pmd:check 2>&1'],
      ['jacoco', 'mvn -q jacoco:report 2>&1'],
    ],
    L3: [],
  },
  csharp: {
    manifests: ['*.csproj', '*.sln', 'global.json'],
    L1: [
      ['build', 'dotnet build --no-incremental 2>&1'],
      ['test', 'dotnet test --no-build 2>&1'],
      ['format', 'dotnet format --verify-no-changes 2>&1'],
      ['vuln pkgs', 'dotnet list package --vulnerable --include-transitive 2>&1'],
    ],
    L2: [
      ['analyzers', 'dotnet build /p:EnableNETAnalyzers=true /p:AnalysisLevel=latest 2>&1'],
      ['outdated', 'dotnet list package --outdated 2>&1; dotnet list package --deprecated 2>&1'],
      ['NuGone@2.1.1', 'nugone 2>&1'],
    ],
    L3: [['nuget-license@4.0.10', 'nuget-license 2>&1']],
  },
  infra: {
    manifests: ['Dockerfile', 'docker-compose.yml', '*.tf', '.github/workflows'],
    L1: [
      ['hadolint@2.14.0', 'hadolint Dockerfile 2>&1'],
      ['actionlint@1.7.12', 'actionlint 2>&1'],
    ],
    L2: [
      ['trivy config@0.69.3', 'trivy config . 2>&1  # PIN 0.69.3 ONLY (0.69.4-0.69.6 compromised)'],
      ['checkov@3.2.530', 'checkov -d . 2>&1'],
      ['kube-linter@0.8.3', 'kube-linter lint . 2>&1'],
    ],
    L3: [['zizmor@1.25.2', 'zizmor .github/workflows/ 2>&1']],
  },
}

// --- universal git-hygiene scanner (Wave 1 cli-scanner-universal, L2+) ---
const UNIVERSAL_CLI = [
  ['osv-scanner@v2.3.8', 'osv-scanner --recursive . 2>&1  # universal SCA'],
  ['gitleaks@8.30.1', 'gitleaks detect --source . --redact --report-path "$TMP/gl.json" 2>&1'],
  ['git hygiene', 'git ls-files | git check-attr -a --stdin; check large/suspicious files + .gitignore coverage'],
]

// --- waste-scanner pinned step list (README 536-557, L2+) ---
const WASTE_STEPS = [
  '0. Universal SCA: osv-scanner --recursive .   [v2.3.8]  (skip_if no_tool)',
  '1. Supply-chain integrity gate (npm view <pkg> time/maintainers/dependencies; npm audit)',
  '2. Dead code: npx --yes knip@6.14.2 --reporter compact --no-progress',
  '3. Dead CSS: npx --yes purgecss@8.0.0 --rejected --output $TMP  (skip_if tailwind>=4)',
  '4. Dead i18n: npx --yes i18n-unused@0.19.0 display-unused  (if locale files)',
  '5. Dead env vars: dotenv-linter  (fallback npx --yes dotenv-check@1.0.4; if .env)',
  '6. Dep 2nd opinion: knip@6.14.2 --dependencies / cargo udeps / pip-extra-reqs',
  '7. tsconfig/eslint strictness: noUnusedLocals, noUnusedParameters, no-unused-imports',
]

// ===========================================================================
// JSON SCHEMAS — enforced via the StructuredOutput tool (schema option). A
// finding missing a required field is rejected at the tool layer (the agent
// retries) BEFORE it can enter output. (Build spec: "schema validation = code".)
// ===========================================================================

const FINDING_PROPS = {
  severity: { type: 'string', enum: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] },
  file: { type: 'string', description: 'repo-relative path' },
  line: { type: 'integer' },
  end_line: { type: 'integer', description: 'last line of multi-line finding; optional' },
  title: { type: 'string' },
  detail: { type: 'string' },
  snippet: { type: 'string', description: '3-5 line code excerpt at file:line' },
  detection_method: { type: 'string', enum: ['tool', 'manual', 'adversarial'] },
  cwe: { type: 'string', description: 'CWE id if applicable, else empty' },
  cve: { type: 'string', description: 'CVE id(s) for SCA findings, else empty' },
  repro_command: { type: 'string', description: 'exact command/test that proves it, or empty if none' },
  origin: { type: 'string', description: 'wave/agent that produced it, e.g. wave2:impact-reviewer-go' },
}
const FINDING_REQUIRED = ['severity', 'file', 'line', 'title', 'detail', 'snippet', 'detection_method', 'origin']

const FINDINGS_SCHEMA = {
  type: 'object',
  required: ['findings', 'inspected', 'not_inspected', 'uncertainty', 'tools_run'],
  properties: {
    findings: {
      type: 'array',
      items: { type: 'object', required: FINDING_REQUIRED, properties: FINDING_PROPS },
    },
    inspected: { type: 'array', items: { type: 'string' }, description: 'files/packages actually read' },
    not_inspected: { type: 'array', items: { type: 'string' }, description: 'in-scope but NOT read + why' },
    bug_classes_out_of_reach: { type: 'array', items: { type: 'string' }, description: 'classes static review structurally misses here' },
    uncertainty: { type: 'string', description: 'where I am unsure / could not verify (routes targeted re-reads)' },
    tools_run: { type: 'array', items: { type: 'string' }, description: 'tool:exitcode pairs, e.g. gosec:1' },
    limitations: {
      type: 'array',
      items: { type: 'object', required: ['capability', 'status', 'impact'], properties: {
        capability: { type: 'string' }, status: { type: 'string' }, impact: { type: 'string' } } },
    },
  },
}

const SCORING_SCHEMA = {
  type: 'object',
  required: ['scored'],
  properties: {
    scored: {
      type: 'array',
      items: { type: 'object', required: ['id', 'confidence', 'verdict', 'evidence'], properties: {
        id: { type: 'string' },
        confidence: { type: 'integer', minimum: 0, maximum: 100 },
        adjusted_severity: { type: 'string', enum: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'unchanged'] },
        verdict: { type: 'string', enum: ['CONFIRMED', 'FALSE_POSITIVE', 'NEEDS_HUMAN'] },
        evidence: { type: 'string', description: 'exit code / line / output proving the score' },
        uncertainty: { type: 'string' },
      } },
    },
  },
}

const SCRATCH_SCHEMA = {
  type: 'object',
  required: ['created', 'note'],
  properties: {
    created: { type: 'array', items: { type: 'string' }, description: 'absolute paths actually created under {artifact_dir}/scratch' },
    note: { type: 'string' },
  },
}

const REPRO_SCHEMA = {
  type: 'object',
  required: ['results'],
  properties: {
    results: {
      type: 'array',
      items: { type: 'object', required: ['id', 'result', 'method', 'evidence'], properties: {
        id: { type: 'string' },
        result: { type: 'string', enum: ['REPRODUCED', 'NOT_REPRODUCED', 'SKIPPED_RUNTIME'] },
        method: { type: 'string', description: 'failing test / CLI command / scanner re-run' },
        evidence: { type: 'string', description: 'exit code + output excerpt' },
      } },
    },
  },
}

const VERIFY_SCHEMA = {
  type: 'object',
  required: ['id', 'admitted', 'command', 'exit_code', 'evidence'],
  properties: {
    id: { type: 'string' },
    admitted: { type: 'boolean', description: 'true only if fresh evidence confirms the claim' },
    command: { type: 'string' },
    exit_code: { type: 'integer' },
    evidence: { type: 'string' },
  },
}

// ===========================================================================
// ARGS VALIDATION — abort with a clear message; NO silent defaults.
// ===========================================================================
function validateArgs(a) {
  const err = []
  if (!a || typeof a !== 'object') return ['args missing or not an object']
  if (!a.stack || !Array.isArray(a.stack.packages) || a.stack.packages.length === 0)
    err.push('args.stack.packages[] required (Phase-0 stack detection output)')
  if (!a.scope || typeof a.scope !== 'object') err.push('args.scope required')
  else {
    if (!Array.isArray(a.scope.paths)) err.push('args.scope.paths[] required')
    if (!['security', 'quality', 'full'].includes(a.scope.focus))
      err.push("args.scope.focus must be 'security' | 'quality' | 'full'")
  }
  if (![1, 2, 3, 'S'].includes(a.level)) err.push("args.level must be 1 | 2 | 3 | 'S' (no default)")
  if (!['broad', 'security', 'targeted'].includes(a.approach))
    err.push("args.approach must be 'broad' | 'security' | 'targeted'")
  if (!a.tool_status || !a.tool_status.mcp || !a.tool_status.cli)
    err.push('args.tool_status.{mcp,cli} required (Phase-0 health-check output)')
  if (typeof a.project_root !== 'string' || !a.project_root)
    err.push('args.project_root required (absolute path to the audited project)')
  if (typeof a.spec_root !== 'string' || !a.spec_root)
    err.push('args.spec_root required (absolute path to full-audit checklist files: go.md, universal.md, ...)')
  if (typeof a.commit !== 'string') err.push('args.commit required (HEAD sha; or "uncommitted")')
  if (typeof a.date !== 'string') err.push('args.date required (YYYY-MM-DD; Date.now() unavailable in scripts)')
  // project_rules may be '' (no CLAUDE.md) but must be present
  if (typeof a.project_rules !== 'string') err.push("args.project_rules required (project CLAUDE.md text or '')")
  return err
}

// ===========================================================================
// HELPERS
// ===========================================================================

// Build the MCP wiring block for a role. Reads liveness + expected prefix from
// args.tool_status.mcp; instructs the agent to confirm the prefix at runtime
// (ToolSearch) and to degrade gracefully, recording each gap as a limitation.
function mcpBlock(a, servers) {
  const m = a.tool_status.mcp || {}
  const lines = []
  for (const s of servers) {
    if (s === 'sequential-thinking') {
      const live = m.sequential_thinking && m.sequential_thinking.live
      lines.push(live
        ? `- Sequential-Thinking: use \`${SEQ_THINKING}\` for multi-hypothesis planning.`
        : `- Sequential-Thinking: DOWN -> linear reasoning. Record limitation.`)
      continue
    }
    const info = m[s] || {}
    if (info.live) {
      const prefixLine = `- ${s}: LIVE. Expected tool prefix \`${info.prefix || `mcp__${s}__`}\`. Confirm exact prefix at runtime via ToolSearch query "${s}" (plugin installs use \`mcp__plugin_${s}_${s}__\`).`
      if (s === 'serena') {
        lines.push(`${prefixLine} CODE-vs-TEXT RULE: Serena is REQUIRED whenever you study or navigate CODE — symbols, definitions, references, the call/usage graph, cross-file logic, or understanding any implementation. Do NOT Grep/Read through code for symbol / navigation work while Serena is LIVE. Grep/Read are appropriate ONLY for plain-TEXT targets: documentation, markdown, comments-as-prose, config/text files, log output. RECORD EVERY navigation tool you actually invoke in \`tools_run\` (e.g. "serena:find_symbol", "serena:find_referencing_symbols", "grep", "read") — tools_run must be non-empty.`)
      } else if (s === 'context7') {
        lines.push(`${prefixLine} Use it (resolve-library-id -> query-docs) when judging library/API correctness. Only claim Context7 use if you ACTUALLY called it — record each call in \`tools_run\` (e.g. "context7:query-docs"). If you used it, do NOT also record a "Context7 not used" limitation. If you did NOT or could NOT use it, record a limitation { capability:"context7", status:"not used", impact:"..." }.`)
      } else {
        lines.push(`${prefixLine} Use it directly — do NOT raw-read when an MCP op exists. Record each MCP tool you actually invoke in \`tools_run\`.`)
      }
    } else {
      const fb = s === 'serena' ? 'fall back to Grep/Read/Glob (no semantics — slower)'
        : s === 'playwright' ? 'SKIP live DOM checks entirely'
        : s === 'context7' ? 'proceed without live docs; flag higher error risk'
        : 'degrade'
      lines.push(`- ${s}: DOWN per Phase-0 health check -> ${fb}. Record an Audit Limitation { capability:"${s}", status:"not available", impact:"..." }.`)
    }
  }
  return lines.join('\n')
}

const IRON_LAW = `VERIFICATION (Iron Law — "No claim without fresh evidence"):
1. IDENTIFY the command that proves the claim. 2. RUN it freshly (never cached). 3. READ full output + exit code. 4. VERIFY output confirms the claim. 5. ONLY THEN report it.
- CLI exit codes: capture $LASTEXITCODE / $? BEFORE piping into head/grep/tail (piping discards the tool's real exit code).
- NEVER use these phrases without attached evidence: ${PROHIBITED_PHRASES.map(p => `"${p}"`).join(', ')}.`

const FP_BLOCK = `FALSE-POSITIVE WHITELIST (drop / score 0, do NOT report as a finding):
${FP_WHITELIST.map((w, i) => `${i + 1}. ${w}`).join('\n')}
Exception: never silently drop a *plausible real bug* on low confidence — emit it (confidence will demote it to suspected_unconfirmed, not delete it).`

function header(a, role, mcpServers) {
  return `You are \`${role}\`, a subagent of the full-audit workflow (v1.10.8 engine). You share NO context with the orchestrator — everything you need is below.

PROJECT ROOT: ${a.project_root}
SPEC ROOT (full-audit checklist files): ${a.spec_root}
ARTIFACT DIR: ${a.artifact_dir}  (ALL files you create go here — see ARTIFACTS rule below)
AUDIT: level=${a.level} approach=${a.approach} focus=${a.scope.focus} verified=${!!a.verified} commit=${a.commit} date=${a.date}
SCOPE paths: ${JSON.stringify(a.scope.paths)}
CRITICAL modules: ${JSON.stringify(a.scope.critical_modules || [])}
EXCLUSIONS: ${JSON.stringify(a.scope.exclusions || [])}
COMPLIANCE: ${JSON.stringify(a.scope.compliance || [])}
PROJECT RULES (CLAUDE.md — these OVERRIDE generic checks; a pattern allowed here is NOT a finding):
${a.project_rules ? a.project_rules.slice(0, 4000) : '(none provided)'}

MCP SERVERS (use them for your work; degrade + record limitation if down):
${mcpBlock(a, mcpServers)}

${IRON_LAW}

${FP_BLOCK}

READ-ONLY (HARD LAW — violating this is a hard failure, abort the task):
- This is a READ-ONLY audit. NEVER write, reformat, rewrite, or codegen any file in the repo working tree. NEVER pass an in-place / write / fix flag to ANY tool. Forbidden flags on ANY tool: \`-w\`, \`-i\`, \`--fix\`, \`--write\`, \`-write\`.
- Formatters/linters: CHECK MODE ONLY. gofmt -l / gofmt -d ONLY (NEVER \`gofmt -w\`, NEVER \`go fmt\`); goimports -d (never -w); \`ruff format --check\` / \`ruff check\` (never \`--fix\` / \`--write\`); \`dotnet format --verify-no-changes\` (never bare \`dotnet format\`); \`cargo fmt --check\` (never \`cargo fmt\`); prettier \`--check\` (never \`--write\`); eslint with NO \`--fix\`; clang-format \`--dry-run\` / \`-n\` (never \`-i\`).
- Build/test/scan/lint in CHECK mode only. NO codegen, NO installs, NO \`go mod tidy\` (use \`go mod tidy -diff\`). Do not generate, mutate, stage, or commit anything in the repo tree.

ARTIFACTS (single-folder discipline — everything deletable at once):
- Every file you create — scratch tests, scanner reports (e.g. gitleaks --report-path), temp output, intermediate dumps — MUST be written UNDER ${a.artifact_dir} (create it if missing). Write NOTHING else into the repo working tree. Never commit, never modify source.
- In any command below, \`$TMP\` / \`$ARTIFACT\` mean \`${a.artifact_dir}/tmp\`. NOTE: this is for tool/scanner temp output only — runnable repro/scratch programs go to \`${a.artifact_dir}/scratch\` (a DIFFERENT dir; see repro instructions), never \`$TMP\`.
- Before returning, also write your StructuredOutput JSON to \`${a.artifact_dir}/raw/${role}.json\` (intermediate visibility for background runs).

OUTPUT: call the StructuredOutput tool exactly once matching the schema. Each finding REQUIRES: severity, file, line, title, detail, snippet (3-5 lines), detection_method (tool|manual|adversarial), origin. Add cwe/cve/end_line/repro_command when known. Sort file -> line. Your returned text IS data, not a message.
- \`tools_run\` is MANDATORY and must be non-empty: list every navigation/scanner tool you actually invoked (e.g. "serena:find_symbol", "serena:find_referencing_symbols", "grep", "read", or "tool:exitcode" pairs like "gosec:1").
- \`line\` MUST be the line where the reported problem actually is and where \`snippet\` begins — NOT the enclosing function/symbol declaration line. \`snippet\` (3-5 lines) must bracket that exact line.`
}

// Severity -1 level (NOT_REPRODUCED override)
function demoteSeverity(sev) {
  const i = SEV_ORDER.indexOf(sev)
  return i > 0 ? SEV_ORDER[i - 1] : sev
}
function isSecurityClass(f) {
  const s = `${f.title} ${f.detail} ${f.cwe || ''}`.toLowerCase()
  return /\b(xss|sqli|sql injection|ssrf|xxe|rce|idor|bola|bfla|auth|csrf|deserializ|secret|injection|traversal|cve|cwe|jwt|crypto|priv)/.test(s)
}
function chunk(arr, n) {
  const out = []
  for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n))
  return out
}

// Dedup cross-wave duplicate findings. Conservative: only merge when file AND
// line AND normalized-title ALL match (lowercase, non-alphanumeric collapsed).
// Merge keeps highest severity, unions origins (distinct, comma-joined), keeps
// the longest detail + snippet, keeps the first id. Returns the merged list.
function normTitle(t) {
  return String(t || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
}
// Merge finding b INTO a (a wins identity): keep highest severity, union origins,
// keep the longest detail + snippet. Shared by both dedup passes.
function mergeInto(a, b) {
  if (SEV_ORDER.indexOf(b.severity) > SEV_ORDER.indexOf(a.severity)) a.severity = b.severity
  const origins = new Set(String(a.origin || '').split(',').map(s => s.trim()).filter(Boolean))
  for (const o of String(b.origin || '').split(',').map(s => s.trim()).filter(Boolean)) origins.add(o)
  a.origin = [...origins].join(', ')
  if ((b.detail || '').length > (a.detail || '').length) a.detail = b.detail
  if ((b.snippet || '').length > (a.snippet || '').length) a.snippet = b.snippet
}
function dedupeFindings(findings) {
  const byKey = new Map()
  const order = []
  for (const f of findings) {
    const key = `${f.file} ${f.line} ${normTitle(f.title)}`
    const prev = byKey.get(key)
    if (!prev) { byKey.set(key, f); order.push(key); continue }
    mergeInto(prev, f) // keep prev's id — first wins
  }
  return order.map(k => byKey.get(k))
}

// R2 — conservative SEMANTIC dedup: a second pass that merges findings sharing
// the same (file, line) but with DIFFERENT normalized titles, IFF their normTitle
// token sets overlap by Jaccard >= 0.6 (same bug, two titles). Distinct issues at
// the same line (overlap < 0.6) stay separate. Highest sev / union origins / one id.
function jaccard(aTokens, bTokens) {
  const A = new Set(aTokens), B = new Set(bTokens)
  if (A.size === 0 && B.size === 0) return 1
  let inter = 0
  for (const t of A) if (B.has(t)) inter++
  const union = A.size + B.size - inter
  return union === 0 ? 0 : inter / union
}
function dedupeSemantic(findings) {
  const kept = []
  for (const f of findings) {
    const fTokens = normTitle(f.title).split(' ').filter(Boolean)
    let merged = false
    for (const k of kept) {
      if (k.file !== f.file || k.line !== f.line) continue
      const kTokens = normTitle(k.title).split(' ').filter(Boolean)
      if (jaccard(kTokens, fTokens) >= 0.6) { mergeInto(k, f); merged = true; break }
    }
    if (!merged) kept.push(f)
  }
  return kept
}

// ===========================================================================
// PROMPT BUILDERS (one per role) — self-contained, MCP-wired.
// ===========================================================================

function cliScannerPrompt(a, stack, pkg) {
  const t = STACK_TOOLS[stack] || { L1: [], L2: [], L3: [] }
  const lvls = a.level === 1 ? ['L1'] : a.level === 3 ? ['L1', 'L2', 'L3'] : ['L1', 'L2']
  const cmds = lvls.flatMap(L => (t[L] || []).map(([name, cmd]) => `  [${name}] ${cmd}`))
  const status = a.tool_status.cli || {}
  return `${header(a, `cli-scanner-${stack}`, [])}

TASK: run the pinned ${stack} CLI scanners for package "${pkg.root}" at level ${a.level}. Read ${a.spec_root}/${stack}.md for the level-scoped checklist context. Tools install-status (Phase 0): ${JSON.stringify(status)}.
Run each from "${pkg.root}". If a tool is not installed -> SKIP it and record a limitation { capability, status:"not installed", impact }. NEVER install anything.
COMMANDS (exact pins — versions.lock):
${cmds.join('\n')}
For every tool: capture exit code FIRST, then parse. Emit one finding per real issue with detection_method:"tool", the tool name in origin (e.g. "wave1:cli-scanner-${stack}:gosec"), file:line, snippet, and repro_command = the exact scanner command. Put "tool:exitcode" pairs in tools_run.`
}

function universalCliPrompt(a) {
  return `${header(a, 'cli-scanner-universal', [])}

TASK: universal git-hygiene + SCA scan (L2+). Run from ${a.project_root}:
${UNIVERSAL_CLI.map(([n, c]) => `  [${n}] ${c}`).join('\n')}
Check: committed large/binary files, suspicious files (keys, dumps), .gitignore coverage gaps, lockfile-wide CVEs (osv-scanner), committed secrets (gitleaks --redact). Capture exit codes first. detection_method:"tool".`
}

function wasteScannerPrompt(a) {
  return `${header(a, 'waste-scanner', [])}

TASK: cross-ref waste detection (L2+), ALL tools PINNED (no @latest). Run from ${a.project_root} in order; skip a step when its precondition is absent:
${WASTE_STEPS.map(s => `  ${s}`).join('\n')}
Report dead code, dead CSS/i18n/env, unused deps, weak tsconfig/eslint strictness as MEDIUM/LOW findings with detection_method:"tool" and repro_command. Step 1 supply-chain red flags (typosquat, sudden maintainer change, install scripts) -> HIGH.`
}

function webResearcherPrompt(a) {
  return `${header(a, 'web-researcher', ['context7'])}

TASK (RESEARCH): for each manifest in scope, check runtime + dependency currency and known CVEs. Use WebSearch/WebFetch for advisories and Context7 (resolve-library-id -> query-docs) for current library docs. Require a source URL for every claim (Iron Law: web-researcher -> require source URL).
Emit findings for: EOL/behind runtimes, vulnerable dep versions (severity per CVSS), with cve set, detection_method:"tool" (scanner-corroborated) or "manual", repro_command = "re-run <scanner>, pinned vulnerable version from lockfile". Read ${a.spec_root}/universal.md "Stack Currency" section.`
}

function wave2Prompt(a, role, stack, focusText, mcp) {
  return `${header(a, stack ? `${role}-${stack}` : role, mcp)}

TASK (DEEP, Wave 2 code review): ${focusText}
Read ${a.spec_root}/${stack || 'universal'}.md (L2 sections) for the exact checklist. Use Serena for symbol nav / find-references / cross-file impact (fallback Grep/Read/Glob if down). Review only scope paths${stack ? ` for the ${stack} package(s)` : ''}; honor exclusions. Reviewer line discipline: file:line, problem, fix. Sort file->line. detection_method:"manual".`
}

// ORCHESTRATOR-CREATED scratch isolation (Fix #3). One FAST agent pre-creates
// {artifact_dir}/scratch and an isolation SENTINEL so any source dropped there is
// excluded from the audited project's module/package graph. For Go: a nested
// go.mod (module audit_scratch) — a nested module is excluded from the parent's
// `go list ./...`, killing the `main redeclared` / DuplicateDecl poisoning. For
// Node: a package.json with a private name. Creates the dir for any stack. It
// must ONLY create files UNDER {artifact_dir}/scratch — nothing in the project tree.
function scratchSetupPrompt(a) {
  const stacks = new Set()
  for (const p of (a.stack.packages || [])) for (const s of (p.stacks || [])) stacks.add(s)
  const isGo = stacks.has('go')
  const isNode = stacks.has('frontend')
  return `${header(a, 'scratch-setup', [])}

TASK (FAST, scratch isolation setup): PRE-CREATE the isolated scratch workspace so later repro/adversarial agents can drop runnable source there WITHOUT poisoning the audited project's module/package graph. You ONLY create files UNDER \`${a.artifact_dir}/scratch\` — create NOTHING anywhere in the project tree (\`${a.project_root}\` outside \`${a.artifact_dir}\`).
STEPS:
1. Create the directory \`${a.artifact_dir}/scratch\` (mkdir -p / New-Item -ItemType Directory -Force).
${isGo ? `2. Create \`${a.artifact_dir}/scratch/go.mod\` with exactly this content (module name \`audit_scratch\`) — this makes scratch a NESTED Go module, excluded from the parent project's \`go list ./...\`, which prevents \`main redeclared\` / DuplicateDecl when scratch \`package main\` files are added:
-----
module audit_scratch

go 1.21
-----` : ''}${isNode ? `${isGo ? '\n3.' : '\n2.'} Create \`${a.artifact_dir}/scratch/package.json\` with exactly this content (private package, name \`audit_scratch\`) so scratch is an isolated Node package, not part of the project's workspace/package graph:
-----
{"name":"audit_scratch","private":true}
-----` : ''}
Do NOT run \`go mod init\`, \`npm init\`, or any installer — write the sentinel file(s) directly with the literal content above. Do NOT modify the repo. Return via the schema: created = the absolute paths you actually created (the dir + sentinel file(s)); note = a one-line summary.`
}

function reproPrompt(a, batch) {
  return `${header(a, 'reproduction-agent', [])}

TASK (DEEP, Wave 2.5): prove each CRITICAL/HIGH finding BEFORE it is trusted. STATIC-BY-DEFAULT — no servers/DBs/network. For each: read it -> pick method (failing test / CLI command / re-run scanner for SCA) -> run ONCE -> capture exit code + output. Classify REPRODUCED / NOT_REPRODUCED / SKIPPED_RUNTIME (runtime-only).
SCRATCH ISOLATION (CRITICAL — do NOT poison the audited project): \`${a.artifact_dir}/scratch\` is ALREADY a pre-created, isolated module (the orchestrator created the dir + its isolation sentinel, e.g. a nested \`go.mod\` module \`audit_scratch\` / a private \`package.json\`). Just write your scratch/repro files THERE (NOT \`$TMP\`, NOT anywhere in the repo tree). Do NOT run \`go mod init\` (or \`npm init\`) yourself — the sentinel already exists. Because scratch is a nested module, \`go list ./...\` / LSP from the project root never sees it (no \`main redeclared\` / DuplicateDecl). PREFER writing a failing TEST inside the scratch module over a \`package main\`. NEVER create any \`.go\` (or other compiled source) inside the project module tree — i.e. inside \`${a.project_root}\` outside \`${a.artifact_dir}\`. Do NOT modify the repo.
FINDINGS TO REPRODUCE:
${batch.map(f => `- id=${f.id} [${f.severity}] ${f.file}:${f.line} — ${f.title}\n  repro hint: ${f.repro_command || '(none — derive one)'}`).join('\n')}
Return one result per id via the schema.`
}

function wave3Prompt(a, role, stack, checklist, mcp) {
  return `${header(a, stack ? `${role}-${stack}` : role, mcp)}

TASK (DEEP, Wave 3 — L3 deep review): ${checklist}
Read ${a.spec_root}/${stack || 'universal'}.md (L3 sections). Use Serena for semantic nav + read_memory; Context7 for current API/library behavior when judging correctness. DEPTH FUNNEL: spend most effort on critical_modules and files where Wave 1/2 already caught signal, but still inspect all assigned scope at least once. Report what you did NOT inspect in not_inspected, and bug classes static review misses in bug_classes_out_of_reach.`
}

function uiReviewerPrompt(a) {
  return `${header(a, 'ui-reviewer', ['playwright'])}

TASK (DEEP, Wave 3 — L3 UI/UX): live DOM testing via Playwright. Use browser_snapshot (accessibility tree — NOT screenshots), browser_console_messages, browser_network_requests. Requires a RUNNING dev server: if no URL is reachable, SKIP and record limitation { capability:"Playwright UI runtime", status:"no dev server", impact:"UI runtime checks skipped" }.
Check (frontend.md L3 Functional UI Testing): navigation, interactive elements (clicks/forms), broken links, empty/error/loading states, responsive breakpoints, keyboard a11y, console errors, failed network requests. detection_method:"manual".`
}

function purposeFitPrompt(a) {
  const purpose = (a.scope && a.scope.product_purpose) || ''
  return `${header(a, 'purpose-fit', ['serena'])}

TASK (DEEP, Wave 3 — L3 Purpose-Fit & Scope-Coherence): read ${a.spec_root}/universal.md section "Level 3: Purpose-Fit & Scope-Coherence". HIGH FALSE-POSITIVE class — severity LOW/MEDIUM only, NEVER CRITICAL/HIGH; when unsure whether something is intentional, STILL emit it (it demotes to suspected_unconfirmed, never dropped). detection_method:"manual". Set origin "wave3:purpose-fit".
PRODUCT PURPOSE: ${purpose
    ? purpose
    : '(NOT PROVIDED — SKIP check #1 Feature relevance and record a limitation { capability:"product_purpose", status:"not provided", impact:"feature-relevance check skipped" }; still run #2 + #3 which do not need stated intent)'}
1. Feature relevance (feature/scope creep, boat anchor): working, REACHABLE features/modules/endpoints/screens NOT traceable to the purpose. This is NOT dead code (waste-scanner already covers unreachable/unused).
2. Adoption consistency (parallel implementations, no single source of truth): a declared tech/pattern used half-way or alongside a second approach — e.g. Tailwind on half the UI + hand CSS elsewhere; two HTTP clients; two state stores; tooling installed+configured but applied to a fraction of its surface. Cite file:line for EACH side.
3. Redundant defenses & log noise (defensive overkill, lava flow): guards/logs for impossible states, dead defensive branches with no reachable trigger, debug logging left after stabilization. EXCLUDE legitimate defense-in-depth (untrusted input, concurrency, external I/O).
Use Serena to trace consumers/usage and prove unreachability/inconsistency. Default LOW; never inflate.`
}

function adversarialPrompt(a, zones) {
  return `${header(a, 'adversarial-hunt', ['serena', 'sequential-thinking'])}

TASK (DEEP, extended reasoning — RECALL-FIRST CORE): assume a bug EXISTS in each zone below. Your job is to FIND it and the nastiest input that triggers it — reason about invariants, edge cases, and failure paths, not the happy path. Use Sequential-Thinking for competing hypotheses; Serena to trace data/control flow.
HUNT CHECKLIST (classes static analysis structurally misses): data races; TOCTOU; integer overflow / resource exhaustion under load; silently swallowed errors; off-by-one in pagination/loops; timezone/locale bugs; float precision; leaks on failure/early-return paths; auth/authorization gaps (IDOR/BOLA/BFLA); correctness only on the happy path; concurrency reordering; partial-write / non-atomic state.
ZONES (critical modules + signal zones from earlier waves):
${zones.map(z => `- ${z}`).join('\n') || '- (whole scope; prioritize critical_modules)'}
Emit findings with detection_method:"adversarial". A plausible-but-unproven bug is STILL emitted (low confidence demotes it to suspected_unconfirmed — never drop it). Put concrete triggering inputs in detail and a repro_command when you can derive one.
SCRATCH ISOLATION (CRITICAL — do NOT poison the audited project): if you write any runnable scratch/repro program, put it under \`${a.artifact_dir}/scratch\` ONLY (NOT \`$TMP\`, NOT the repo tree). That dir is ALREADY a pre-created, isolated module (the orchestrator created the dir + its isolation sentinel, e.g. a nested \`go.mod\` module \`audit_scratch\` / a private \`package.json\`), so \`go list ./...\` / LSP from the project root never sees it (no \`main redeclared\` / DuplicateDecl). Do NOT run \`go mod init\` (or \`npm init\`) yourself — the sentinel already exists. Prefer a failing TEST in the scratch module over a \`package main\`. NEVER create any \`.go\` (or other compiled source) inside the project module tree — i.e. inside \`${a.project_root}\` outside \`${a.artifact_dir}\`.`
}

function scoringPrompt(a, batch) {
  return `${header(a, 'scoring-agent', ['serena'])}

TASK (FAST, scoring): independently RE-READ the code for each finding and assign confidence 0-100 per this scale (README): 0 = false positive/pre-existing/unverifiable; 25 = possibly real, unverified, or stylistic w/o CLAUDE.md backing; 50 = verified nitpick; 75 = re-verified, very likely real, functional impact; 100 = confirmed with direct evidence (exit code, line, output). Per finding evaluate: verified against actual code (not hypothetical)? pre-existing or recent (git blame)? does CLAUDE.md allow this pattern? reproducible by a specific command? Set verdict CONFIRMED / FALSE_POSITIVE / NEEDS_HUMAN, and adjusted_severity if mis-rated (else "unchanged"). Fill evidence (the exact line/output/exit code) and uncertainty (what you could not verify).
This level's discard threshold is ${THRESHOLD[a.level]} — but DO NOT delete: just score honestly; the orchestrator demotes sub-threshold findings to suspected_unconfirmed.
FINDINGS:
${batch.map(f => `- id=${f.id} [${f.severity}] ${f.file}:${f.line} (${f.detection_method}) — ${f.title}: ${f.detail.slice(0, 240)}`).join('\n')}`
}

function verifyPrompt(a, f) {
  return `${header(a, 'verify-gate', [])}

TASK (Iron-Law gate): re-run the detection FRESHLY for this ${f.severity} finding and decide admission. No cached results.
FINDING id=${f.id}: ${f.file}:${f.line} — ${f.title}
detail: ${f.detail}
repro_command: ${f.repro_command || '(derive the command that would prove or refute this)'}
Run it from ${a.project_root}, capture exit_code + output. admitted=true ONLY if the fresh output confirms the claim. If it cannot be run (runtime-only), admitted=true but note SKIPPED_RUNTIME in evidence. Return via schema.`
}

function guardPrompt(a) {
  const hasBaseline = typeof a.git_baseline === 'string'
  return `${header(a, 'read-only-guard', [])}

TASK (FAST, read-only guard): this audit MUST NOT have modified the repo tree. Detect (and, if a baseline is provided, clean up) any tracked-file changes introduced by the audit.
STEPS:
1. Confirm it is a git repo: run \`git -C "${a.project_root}" rev-parse --git-dir\` and capture the exit code. If it is NOT a git repo (non-zero exit) -> set repo_is_git=false, changed_files=[], reverted=[], note="not a git repo — guard is a no-op", and return. Do nothing else.
2. If it IS a git repo (repo_is_git=true): run \`git -C "${a.project_root}" status --porcelain\` and capture the full output.
3. ${hasBaseline
    ? `A BASELINE was provided (the \`git status --porcelain\` captured by Phase 0 BEFORE the run). Diff current status against it. For each TRACKED file modified that is NOT present in the baseline (i.e. a change the audit introduced): run \`git -C "${a.project_root}" checkout -- <file>\` to restore it, and add the file to BOTH changed_files and reverted. Do NOT touch files that already appear in the baseline (those are pre-existing user edits — leave them alone). Do NOT touch untracked files. BASELINE (git status --porcelain captured before the run):\n----- BEGIN BASELINE -----\n${a.git_baseline}\n----- END BASELINE -----`
    : `NO baseline was provided. REPORT ONLY — do NOT revert anything (auto-revert without a baseline could clobber pre-existing user edits). List every tracked file currently shown as modified in changed_files; leave reverted=[]; in note, state that no baseline was available so changes are reported but not reverted.`}
4. Return via the schema: repo_is_git (bool), changed_files (list of repo-relative paths the audit appears to have changed; [] if none), reverted (list actually restored via checkout; [] if none/no baseline), note (short human summary).
Use only the git commands above (status, rev-parse, checkout). Read-only except the explicit \`git checkout -- <file>\` restores when a baseline is provided.`
}

const GUARD_SCHEMA = {
  type: 'object',
  required: ['repo_is_git', 'changed_files', 'reverted', 'note'],
  properties: {
    repo_is_git: { type: 'boolean' },
    changed_files: { type: 'array', items: { type: 'string' } },
    reverted: { type: 'array', items: { type: 'string' } },
    note: { type: 'string' },
  },
}

// ===========================================================================
// MAIN ORCHESTRATION
// ===========================================================================

// ---- Validate ----
phase('Validate')
// NOTE: the Workflow runtime delivers the `args` input to the script as a JSON
// STRING (verified via probe: typeof args === 'string'), while the rest of this
// script expects a parsed object. Normalize defensively here (string -> parse,
// object -> passthrough); harmless either way, so the parse stays in-script.
let _args = args
if (typeof _args === 'string') {
  try { _args = JSON.parse(_args) } catch (e) {
    throw new Error('full-audit: args was a JSON string but failed to parse — ' + e.message)
  }
}
const verrs = validateArgs(_args)
if (verrs.length) {
  throw new Error('full-audit: invalid args — aborting (no silent defaults):\n- ' + verrs.join('\n- '))
}
const a = _args
// Single artifact folder: all subagent junk (scratch tests, scanner reports, raw
// dumps) lands here so it can be deleted in one shot. Phase 0 may override via
// args.artifact_dir; default = <project_root>/audit (platform separator).
const _sep = a.project_root.includes('\\') ? '\\' : '/'
a.artifact_dir = a.artifact_dir || (a.project_root.replace(/[\\/]+$/, '') + _sep + 'audit')
const L = a.level
const isL3 = L === 3
const runRepro = a.verified || isL3
const limitations = []
let rawFindings = []
let nextId = 1
const tag = (f, origin) => ({ id: 'FA-' + String(nextId++).padStart(4, '0'), origin, ...f })
const collectLimits = (res) => { for (const r of res) if (r && Array.isArray(r.limitations)) limitations.push(...r.limitations) }
const coverageInspected = []
const coverageNotInspected = []
const bugClassesOOR = []
const uncertaintyNotes = []
const harvest = (res, originFallback) => {
  for (const r of res) {
    if (!r) continue
    if (Array.isArray(r.findings)) for (const f of r.findings) rawFindings.push(tag(f, f.origin || originFallback))
    if (Array.isArray(r.inspected)) coverageInspected.push(...r.inspected)
    if (Array.isArray(r.not_inspected)) coverageNotInspected.push(...r.not_inspected)
    if (Array.isArray(r.bug_classes_out_of_reach)) bugClassesOOR.push(...r.bug_classes_out_of_reach)
    if (r.uncertainty) uncertaintyNotes.push(r.uncertainty)
  }
  collectLimits(res)
}

log(`full-audit: level=${L} approach=${a.approach} focus=${a.scope.focus} verified=${!!a.verified} | ${a.stack.packages.length} package(s)`)

// Expand (stack, package) pairs in scope.
const stackPkgs = []
for (const p of a.stack.packages) for (const s of (p.stacks || [])) if (STACK_TOOLS[s]) stackPkgs.push({ stack: s, pkg: p })
const securityOnly = a.approach === 'security' || a.scope.focus === 'security'

// ---- WAVE 1 — FAST + RESEARCH (parallel, barrier after) ----
phase('Wave 1')
const wave1Thunks = []
for (const { stack, pkg } of stackPkgs)
  wave1Thunks.push(() => agent(cliScannerPrompt(a, stack, pkg), { label: `cli:${stack}:${pkg.root}`, phase: 'Wave 1', model: FAST, schema: FINDINGS_SCHEMA }))
if (L !== 1) {
  wave1Thunks.push(() => agent(universalCliPrompt(a), { label: 'cli:universal', phase: 'Wave 1', model: FAST, schema: FINDINGS_SCHEMA }))
  wave1Thunks.push(() => agent(wasteScannerPrompt(a), { label: 'waste-scanner', phase: 'Wave 1', model: FAST, schema: FINDINGS_SCHEMA }))
  // SMOKE VARIANT: web-researcher DISABLED — it fired WebFetch+WebSearch+Bash in
  // parallel and hung with no tool-timeout, blocking the Wave 1 barrier (~12min
  // freeze) on the first L3 run. Removed to unblock; CVE coverage falls back to
  // govulncheck/gosec. Recorded as an audit limitation for honesty.
  limitations.push({ capability: 'web-researcher (CVE/currency research)', status: 'disabled', impact: 'Wave-1 web research skipped (hung on WebSearch/WebFetch, no tool-timeout); dep-currency/advisory coverage relies on govulncheck/gosec only' })
}
const wave1 = await parallel(wave1Thunks)
harvest(wave1, 'wave1')
log(`Wave 1 done: ${rawFindings.length} raw findings | inspected ${coverageInspected.length} targets`)

// ---- WAVE 2 — DEEP code review (parallel, barrier after). Skipped at L1. ----
if (L !== 1) {
  phase('Wave 2')
  const w2 = []
  for (const { stack } of dedupeStacks(stackPkgs)) {
    w2.push(() => agent(wave2Prompt(a, 'diff-scanner', stack, 'Surface scan: obvious bugs, typos, logic errors without deep context.', ['serena']), { label: `diff:${stack}`, phase: 'Wave 2', model: DEEP, schema: FINDINGS_SCHEMA }))
    w2.push(() => agent(wave2Prompt(a, 'history-reviewer', stack, 'History-aware via git blame: regressions, reverted patterns, repeated mistakes.', ['serena']), { label: `history:${stack}`, phase: 'Wave 2', model: DEEP, schema: FINDINGS_SCHEMA }))
    w2.push(() => agent(wave2Prompt(a, 'impact-reviewer', stack, 'Cross-file impact: breaks dependents? API contracts? serialization tags (json:"-"/@JsonIgnore/[NonSerialized]) with active consumers; progress/counter data flow; dead UI (state vars w/o reachable triggers).', ['serena']), { label: `impact:${stack}`, phase: 'Wave 2', model: DEEP, schema: FINDINGS_SCHEMA }))
  }
  w2.push(() => agent(wave2Prompt(a, 'comment-checker', null, 'Comment compliance: TODO/FIXME match code, no stale annotations.', ['serena']), { label: 'comment-checker', phase: 'Wave 2', model: DEEP, schema: FINDINGS_SCHEMA }))
  w2.push(() => agent(wave2Prompt(a, 'convention-checker', null, 'CLAUDE.md + project conventions: naming, structure compliance.', ['serena']), { label: 'convention-checker', phase: 'Wave 2', model: DEEP, schema: FINDINGS_SCHEMA }))
  harvest(await parallel(w2), 'wave2')
  log(`Wave 2 done: ${rawFindings.length} raw findings total`)
}

// ---- SCRATCH SETUP (Fix #3) — orchestrator-created isolated scratch module.
// Spawn ONCE, BEFORE any agent that writes repro/adversarial scratch (Wave 2.5
// and the L3 adversarial hunt). Pre-creates {artifact_dir}/scratch + an isolation
// sentinel (nested go.mod / private package.json) so scratch source never poisons
// the audited project's module/package graph. Null-guarded. ----
if (runRepro || isL3) {
  const scratch = await agent(scratchSetupPrompt(a), { label: 'scratch-setup', phase: 'Wave 2.5', model: FAST, schema: SCRATCH_SCHEMA })
  if (scratch && Array.isArray(scratch.created))
    log(`Scratch setup: pre-created ${scratch.created.length} path(s) under ${a.artifact_dir}/scratch — ${scratch.note || ''}`)
  else
    log('Scratch setup: agent returned null/incomplete — scratch isolation not confirmed')
}

// ---- WAVE 2.5 — reproduction (DEEP). Runs in verified mode or at L3. ----
if (runRepro) {
  phase('Wave 2.5')
  const highSev = rawFindings.filter(f => f.severity === 'CRITICAL' || f.severity === 'HIGH')
  if (highSev.length) {
    const batches = chunk(highSev, 10) // 1 repro-agent per ~10 high-sev findings (README 593)
    const reproRes = await parallel(batches.map((b, i) => () =>
      agent(reproPrompt(a, b), { label: `repro:${i + 1}`, phase: 'Wave 2.5', model: DEEP, schema: REPRO_SCHEMA })))
    for (const r of reproRes) if (r && Array.isArray(r.results)) for (const res of r.results) {
      const f = rawFindings.find(x => x.id === res.id)
      if (f) f._repro = res // { result, method, evidence }
    }
    log(`Wave 2.5 done: reproduced ${reproRes.filter(Boolean).flatMap(r => r.results || []).filter(r => r.result === 'REPRODUCED').length} / ${highSev.length} high-sev`)
  } else log('Wave 2.5 skipped: no CRITICAL/HIGH findings yet')
}

// ---- WAVE 3 — L3 ONLY: deep reviewers + adversarial (DEEP, parallel) ----
if (isL3) {
  phase('Wave 3')
  const w3 = []
  const stacks = dedupeStacks(stackPkgs)
  for (const { stack } of stacks) {
    w3.push(() => agent(wave3Prompt(a, 'code-reviewer', stack, 'All L3 stack checks: type/lang traps, error handling, DB audit, complexity, perf, overengineering, framework-specific.', ['serena', 'context7']), { label: `code:${stack}`, phase: 'Wave 3', model: DEEP, schema: FINDINGS_SCHEMA }))
    w3.push(() => agent(wave3Prompt(a, 'logic-reviewer', stack, 'Business-logic correctness, edge cases, heuristic accuracy, race conditions, error-handling gaps, resource leaks.', ['serena']), { label: `logic:${stack}`, phase: 'Wave 3', model: DEEP, schema: FINDINGS_SCHEMA }))
  }
  w3.push(() => agent(wave3Prompt(a, 'code-reviewer-security', null, 'XSS, SSRF, deserialization, XXE, ReDoS, log injection, IDOR/BOLA/BFLA, session mgmt, JWT/auth, business-logic abuse, webhook security, file-upload hardening.', ['serena', 'context7']), { label: 'security', phase: 'Wave 3', model: DEEP, schema: FINDINGS_SCHEMA }))
  if (!securityOnly) {
    w3.push(() => agent(wave3Prompt(a, 'code-reviewer-quality', null, 'API contracts, logging/observability, error disclosure, overengineering, docs freshness, input validation, resilience, config/state mgmt, privacy/PII, supply chain, SBOM, license compliance, sharp edges, variant analysis.', ['serena', 'context7']), { label: 'quality', phase: 'Wave 3', model: DEEP, schema: FINDINGS_SCHEMA }))
    w3.push(() => agent(wave3Prompt(a, 'arch-reviewer', null, 'Design decisions, trade-offs, alternatives, communication patterns, scalability, extensibility, dead config, missing implementations.', ['serena']), { label: 'arch', phase: 'Wave 3', model: DEEP, schema: FINDINGS_SCHEMA }))
    // Purpose-fit & scope-coherence (L3, quality only): irrelevant-but-working features, half-adopted tech, redundant defenses. High-FP -> recall-first.
    w3.push(() => agent(purposeFitPrompt(a), { label: 'purpose-fit', phase: 'Wave 3', model: DEEP, schema: FINDINGS_SCHEMA }))
    // UI reviewer only if a frontend stack is present and Playwright is live.
    const hasFE = stacks.some(s => s.stack === 'frontend')
    const pwLive = a.tool_status.mcp.playwright && a.tool_status.mcp.playwright.live
    if (hasFE && pwLive) w3.push(() => agent(uiReviewerPrompt(a), { label: 'ui-reviewer', phase: 'Wave 3', model: DEEP, schema: FINDINGS_SCHEMA }))
    else if (hasFE) limitations.push({ capability: 'Playwright UI', status: 'not available', impact: 'L3 functional UI testing skipped' })
  }
  // Adversarial hunt: target critical modules + files where earlier waves caught signal.
  const signalZones = [...new Set([
    ...(a.scope.critical_modules || []),
    ...rawFindings.filter(f => f.severity === 'CRITICAL' || f.severity === 'HIGH').map(f => f.file),
  ])].slice(0, 40)
  const advBatches = chunk(signalZones.length ? signalZones : ['(whole scope)'], 12)
  for (let i = 0; i < advBatches.length; i++)
    w3.push(() => agent(adversarialPrompt(a, advBatches[i]), { label: `adversarial:${i + 1}`, phase: 'Wave 3', model: DEEP, schema: FINDINGS_SCHEMA }))
  harvest(await parallel(w3), 'wave3')
  log(`Wave 3 done: ${rawFindings.length} raw findings total`)
}

// ---- DEDUP — merge cross-wave duplicates by (file, line, normalized-title). ----
// Conservative: distinct issues sharing only a line are NOT merged. Recall-first
// preserved (a duplicate is a merge, not a drop).
{
  const before = rawFindings.length
  rawFindings = dedupeFindings(rawFindings)
  const afterExact = rawFindings.length
  rawFindings = dedupeSemantic(rawFindings) // R2: same file:line, Jaccard>=0.6 titles
  log(`Dedup: merged ${before - afterExact} exact + ${afterExact - rawFindings.length} semantic duplicate(s) | ${rawFindings.length} distinct findings`)
}

// ---- SCORING — FAST, 1 agent per ~20 findings. Recall-first: demote, never drop. ----
phase('Scoring')
let confirmed = []
let suspected = []
if (rawFindings.length === 0) {
  log('Scoring skipped: 0 raw findings')
} else if (L === 1) {
  // L1 has NO scoring agent: reviewers self-apply >=75 inline. Treat tool findings as confirmed.
  confirmed = rawFindings
  log('L1: no scoring agent; reviewers self-applied >=75 gate inline')
} else {
  const batches = chunk(rawFindings, 20)
  const scoreRes = await parallel(batches.map((b, i) => () =>
    agent(scoringPrompt(a, b), { label: `score:${i + 1}`, phase: 'Scoring', model: FAST, schema: SCORING_SCHEMA })))
  const scoreById = {}
  for (const r of scoreRes) if (r && Array.isArray(r.scored)) for (const s of r.scored) scoreById[s.id] = s
  const threshold = THRESHOLD[L]
  for (const f of rawFindings) {
    const s = scoreById[f.id]
    let conf = s ? s.confidence : 25 // unscored -> low-confidence, demoted not dropped
    if (s && s.adjusted_severity && s.adjusted_severity !== 'unchanged') f.severity = s.adjusted_severity
    if (s && s.uncertainty) uncertaintyNotes.push(s.uncertainty)
    // reproduction override (applied AFTER scoring, BEFORE threshold)
    let reproTag = null
    if (f._repro) {
      if (f._repro.result === 'REPRODUCED') { conf = Math.max(conf, 90); reproTag = 'reproduced' }
      else if (f._repro.result === 'NOT_REPRODUCED') { conf = Math.min(conf, 25); f.severity = demoteSeverity(f.severity); reproTag = 'unverified' }
      else if (f._repro.result === 'SKIPPED_RUNTIME') { reproTag = 'unverified: requires runtime' }
    }
    // purpose-fit is a high-FP quality class: hard-cap severity, never CRITICAL/HIGH (enforcement as code)
    if (f.origin && f.origin.includes('purpose-fit') && (f.severity === 'CRITICAL' || f.severity === 'HIGH')) f.severity = 'MEDIUM'
    f.confidence = conf
    f.reproduced = f._repro ? f._repro.result.toLowerCase() : 'n/a'
    f.repro_tag = reproTag
    if (s && s.evidence) f.evidence = s.evidence
    delete f._repro
    // threshold applied LAST, to the reproduction-adjusted score. Demote, don't discard.
    // FALSE_POSITIVE verdict -> suspected_unconfirmed (needs human), never confirmed, never dropped.
    if (conf >= threshold && !(s && s.verdict === 'FALSE_POSITIVE')) confirmed.push(f)
    else {
      // stamp a machine-readable demotion reason (recall-first: demoted, never dropped)
      if (s && s.verdict === 'FALSE_POSITIVE') f.demoted_reason = 'verdict: FALSE_POSITIVE'
      else if (s && s.evidence && /fp-whitelist|whitelist/i.test(s.evidence)) f.demoted_reason = 'fp-whitelist'
      else f.demoted_reason = 'sub-threshold (<' + threshold + ')'
      suspected.push(f)
    }
  }
  log(`Scoring done: ${confirmed.length} confirmed (>=${threshold}) | ${suspected.length} demoted to suspected_unconfirmed`)
}

// ---- VERIFY GATE — Iron Law: re-run detection freshly on CRITICAL/HIGH + security. ----
phase('Verify')
const mustVerify = confirmed.filter(f => f.severity === 'CRITICAL' || f.severity === 'HIGH' || isSecurityClass(f))
if (mustVerify.length) {
  const verifyRes = await parallel(mustVerify.map(f => () =>
    agent(verifyPrompt(a, f), { label: `verify:${f.id}`, phase: 'Verify', model: DEEP, schema: VERIFY_SCHEMA })))
  const vById = {}
  for (const v of verifyRes) if (v) vById[v.id] = v
  const stillConfirmed = []
  for (const f of confirmed) {
    const v = vById[f.id]
    if (!v) { stillConfirmed.push(f); continue }
    f.verify_command = v.command
    f.verify_exit = v.exit_code
    f.verify_evidence = v.evidence
    if (v.admitted) stillConfirmed.push(f)
    else { f.demoted_reason = 'verification gate: fresh evidence did not confirm'; suspected.push(f) }
  }
  confirmed = stillConfirmed
  log(`Verify gate: re-ran ${mustVerify.length} | ${confirmed.length} admitted | ${suspected.length} now in suspected_unconfirmed`)
}

// strip prohibited unverified phrases programmatically (README 1090-1100)
const stripPhrases = (txt) => {
  if (!txt) return txt
  let out = txt
  for (const p of PROHIBITED_PHRASES) out = out.replace(new RegExp(p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'), '[unverified-claim removed]')
  return out
}
for (const f of [...confirmed, ...suspected]) { f.detail = stripPhrases(f.detail); f.title = stripPhrases(f.title) }

// ---- GUARD — read-only safety: detect (+ clean up if baseline given) repo-tree changes. ----
// Runs unconditionally (all levels); no-ops cleanly when not a git repo / nothing changed.
phase('Guard')
let readOnlyViolations = { repo_is_git: false, changed_files: [], reverted: [], note: 'guard not run' }
{
  const g = await agent(guardPrompt(a), { label: 'read-only-guard', phase: 'Guard', model: FAST, schema: GUARD_SCHEMA })
  if (g) {
    readOnlyViolations = {
      repo_is_git: !!g.repo_is_git,
      changed_files: Array.isArray(g.changed_files) ? g.changed_files : [],
      reverted: Array.isArray(g.reverted) ? g.reverted : [],
      note: g.note || '',
    }
  }
  if (readOnlyViolations.changed_files.length) {
    const revd = readOnlyViolations.reverted.length
    limitations.push({
      capability: 'read-only integrity',
      status: revd ? 'violated (auto-reverted)' : 'violated (reported only)',
      impact: `audit modified ${readOnlyViolations.changed_files.length} tracked file(s): ${readOnlyViolations.changed_files.join(', ')}${revd ? ` — ${revd} reverted via git checkout` : ' — NOT reverted (no baseline); inspect/restore manually'}`,
    })
  }
  log(`Guard: repo_is_git=${readOnlyViolations.repo_is_git} | changed=${readOnlyViolations.changed_files.length} | reverted=${readOnlyViolations.reverted.length}`)
}

// ---- ASSEMBLE — coverage + limitations + summary; structured output ----
phase('Assemble')
const summary = { critical: 0, high: 0, medium: 0, low: 0 }
for (const f of confirmed) {
  if (f.severity === 'CRITICAL') summary.critical++
  else if (f.severity === 'HIGH') summary.high++
  else if (f.severity === 'MEDIUM') summary.medium++
  else if (f.severity === 'LOW') summary.low++
}
summary.health = summary.critical > 0 ? 'CRITICAL' : (summary.high + summary.medium > 0 ? 'NEEDS_WORK' : 'PASS')

// dedupe limitations by capability ONLY (R4): collapse multiple entries for the
// same capability into one (keep the first), normalizing the key to trimmed lowercase.
const limSeen = new Set()
const limitationsOut = limitations.filter(l => { const k = String(l.capability || '').trim().toLowerCase(); if (limSeen.has(k)) return false; limSeen.add(k); return true })

const cleanFinding = (f) => ({
  id: f.id, severity: f.severity, file: f.file, line: f.line, end_line: f.end_line,
  cwe: f.cwe || undefined, cve: f.cve || undefined, title: f.title, detail: f.detail,
  snippet: f.snippet, detection_method: f.detection_method, confidence: f.confidence,
  reproduced: f.reproduced || 'n/a', repro_command: f.repro_command || null,
  repro_tag: f.repro_tag || undefined, evidence: f.evidence || undefined,
  verify_command: f.verify_command || undefined, verify_exit: f.verify_exit,
  verify_evidence: f.verify_evidence || undefined, origin: f.origin,
  demoted_reason: f.demoted_reason || undefined,
})

const output = {
  schema_version: '1.1',
  audit: { level: L, verified: !!a.verified, approach: a.approach, focus: a.scope.focus, date: a.date, commit: a.commit, scope: a.scope.paths },
  artifact_dir: a.artifact_dir, // all on-disk junk (scratch/raw/tmp) lives here — delete this folder to clean up; add to .gitignore

  summary,
  findings: confirmed.sort(sortFinding).map(cleanFinding),
  suspected_unconfirmed: suspected.sort(sortFinding).map(cleanFinding), // recall-first: NEVER dropped, flagged "needs human"
  coverage: {
    inspected: [...new Set(coverageInspected)],
    not_inspected: [...new Set(coverageNotInspected)],
    bug_classes_out_of_static_reach: [...new Set(bugClassesOOR)],
    uncertainty_notes: [...new Set(uncertaintyNotes)].slice(0, 50),
    note: 'A "clean" area means: inspected the listed targets, found nothing in the named classes — not silence. Sub-threshold and unverified findings are in suspected_unconfirmed, not discarded.',
  },
  audit_limitations: limitationsOut,
  read_only_violations: readOnlyViolations,
}

log(`full-audit complete: ${summary.critical}C/${summary.high}H/${summary.medium}M/${summary.low}L confirmed | ${output.suspected_unconfirmed.length} suspected | health=${summary.health} | ${limitationsOut.length} limitations`)
return output

// --- sort + dedupe-stacks helpers (hoisted) ---
function sortFinding(x, y) {
  const sev = SEV_ORDER.indexOf(y.severity) - SEV_ORDER.indexOf(x.severity)
  if (sev) return sev
  if (x.file !== y.file) return x.file < y.file ? -1 : 1
  return (x.line || 0) - (y.line || 0)
}
function dedupeStacks(pairs) {
  const seen = new Set(), out = []
  for (const p of pairs) if (!seen.has(p.stack)) { seen.add(p.stack); out.push(p) }
  return out
}
