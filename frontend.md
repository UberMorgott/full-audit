# Frontend Audit Checks

> **Cross-references:** [README.md](README.md) (orchestration), [universal.md](universal.md) (language-agnostic).
>
> **Required reading:**
> - **Confidence Scoring** (README.md) — 0-100 per finding. Thresholds: L1≥75, L2≥60, L3≥40.
> - **False Positive Detection** (universal.md) — check stack-specific auto-discard before including.
> - **CLI Finding Verification** (universal.md) — 5-step protocol per CLI finding.
> - **YAGNI Check** (universal.md) — verify need before suggesting "add X".
> - **Anti-Rationalization** (universal.md) — no skipping/softening findings.

Applies when `package.json` detected. Framework auto-selected:
- `vue`/`nuxt` → Vue
- `react`/`next` → React
- `svelte`/`@sveltejs/kit` → Svelte
- `angular` → Angular

All commands assume `cd {frontend_root}`.

---

## Level 1: Quick

### Build + lint
```bash
npm run build 2>&1
```
```bash
npm run lint 2>&1
```

### Dependency vulnerabilities
```bash
npm audit 2>&1
# Or (verify version — v0.69.4-6 compromised, see tools.md):
# trivy fs --scanners vuln --severity HIGH,CRITICAL . 2>&1
```

> Vulns found → `npm audit fix`. Breaking: `npm audit fix --force` (review). Report unfixable as findings.

### Tests (if configured)
> skip_if: windows (bash `if`/`grep`). PowerShell: `Select-String '"vitest"' package.json` etc., or run the matching command directly.
```bash
if grep -q '"vitest"' package.json; then
  npx vitest run 2>&1
elif grep -q '"jest"' package.json; then
  npx jest --passWithNoTests 2>&1
elif grep -q '"@angular/core"' package.json; then
  # Angular: Karma/Jasmine via Angular CLI (CI-safe: headless, no watch)
  npx ng test --watch=false --browsers=ChromeHeadless 2>&1
elif grep -q '"test"' package.json; then
  npm test 2>&1
fi
```

**E2E (if configured):** Playwright or Cypress.
```bash
if grep -q '"@playwright/test"' package.json; then
  npx playwright test 2>&1
elif grep -q '"cypress"' package.json; then
  npx cypress run 2>&1
fi
```

### Node.js runtime currency
```bash
node --version 2>&1
```
> Node.js core vulns in `npm audit` → update via `nvm install --lts` or nodejs.org.

**Pass criteria:** 0 errors in all commands.

---

## Level 2: Full (includes Level 1)

### TypeScript strict check

**Vue:**
```bash
npx --yes vue-tsc@3.3.2 --noEmit 2>&1  # pin alongside typescript@~5.8
```

**React / generic TS:**
```bash
npx tsc --noEmit 2>&1
```

### Dead exports & unused deps
```bash
npx --yes knip@6.14.2 2>&1
```

### Bundle analysis
```bash
# Vite
npx --yes vite-bundle-visualizer@1.2.1 2>&1

# Webpack
npx --yes webpack-bundle-analyzer@5.3.0 stats.json 2>&1

# Next.js
ANALYZE=true npm run build 2>&1
```

Check:
- Lazy loading for routes
- No full lodash/moment.js (use lodash-es, date-fns)
- Tree-shaking working (no side-effect imports)
- Images optimized (WebP, lazy loading)
- CSS scoped/modules (no global leaks)
- Dynamic imports for heavy components

### Secrets scan
> Skip if Trivy used.
```bash
# --redact hides secret values; write findings to gitignored report (add gitleaks-report.json to .gitignore)
gitleaks detect --source . --no-git --redact --report-format json --report-path gitleaks-report.json 2>&1
```

### Code coverage
```bash
# Vitest
npx vitest run --coverage 2>&1

# Jest
npx jest --coverage --passWithNoTests 2>&1
```

### Semgrep SAST
```bash
semgrep --config=auto . 2>&1
```

---

### Dead Asset Detection (L2)

#### Automated (CLI — `waste-scanner` agent)

```bash
# 1. Dead code (unused deps, imports, exports, files, types)
npx --yes knip@6.14.2 --reporter compact 2>&1

# 2. Dead CSS in global stylesheets
# Pinned: npm install --save-dev --save-exact purgecss@8.0.0 (or npx --yes purgecss@8.0.0)
# --output needs a writable dir; use a temp dir, not a null device. Windows: $env:TEMP\purgecss (NOT /dev/null; PS has no /dev/null — equivalents are $null / NUL)
npx --yes purgecss@8.0.0 --css <global-css-files> --content 'src/**/*.{svelte,vue,jsx,tsx,html}' --rejected --output "$TMPDIR/purgecss" 2>&1

# 3. Dead i18n keys (if locale files exist)
npx --yes i18n-unused@0.19.0 display-unused 2>&1

# 4. Dead env vars (if .env exists)
# dotenv-check is abandoned -> prefer dotenv-linter (Rust, lints .env + scans source for unused/undefined env vars).
# Pinned install: cargo install dotenv-linter --version 3.3.0  (or pinned GitHub release binary + SHA256 verify)
dotenv-linter 2>&1
# Fallback only if dotenv-linter unavailable (pinned, but unmaintained): npx --yes dotenv-check@1.0.4 2>&1

# 5. TS strictness verification
# tsconfig.json should have "noUnusedLocals": true, "noUnusedParameters": true
# Missing → MEDIUM finding. Then:
npx --yes svelte-check@4.4.8 2>&1  # or vue-tsc@3.3.2 --noEmit, or tsc --noEmit
```

Tool findings: adopt directly, severity = tool's or HIGH default.

#### Manual (reasoning — `impact-reviewer-frontend`)

Require Opus-level reasoning, not automatable:

1. **CSS Framework Utilization** — If knip misses CSS framework (`@import`-ed in CSS, not JS), grep templates for framework class patterns. Zero hits = CRITICAL.

2. **Dead UI Features** — Find state vars controlling visibility (collapsed, isOpen, showX). Verify trigger exists AND visible. State + no trigger = HIGH.

3. **Missing i18n keys** — Keys used in components but missing from locale files = BUG (silent fallback).

4. **Dep Utilization (false negatives)** — Deps not flagged but suspicious:
   - CSS frameworks: see #1 (template grep)
   - Runtime helpers (tslib, core-js): verify tsconfig/babel needs them
   - @types/*: verify corresponding runtime package exists
---

## Level 2: Code Review (Opus agents)

> **Reviewer mapping:** Security → diff-scanner + impact-reviewer. Concurrency → diff-scanner + history-reviewer. Leaks → diff-scanner. Conventions → convention-checker. Stale comments → comment-checker.

### Security review

- **XSS:** `v-html`/`dangerouslySetInnerHTML`/`innerHTML` with user data
- **Open redirect:** `window.location = userInput`, `window.open(userInput)`
- **Sensitive data in localStorage:** tokens, passwords, PII (use httpOnly cookies)
- **Eval:** `eval()`, `new Function()`, `setTimeout(string)`
- **PostMessage:** without origin check — also Web Workers' `postMessage`
- **CORS:** credentials sent to wrong origins
- **Source maps:** disabled in prod build
- **Prototype pollution:** `_.merge()`, `$.extend()`, `Object.assign()`, spread with user-controlled keys — deep merge can overwrite `__proto__`
- **SRI:** CDN scripts/styles without `integrity` attribute
- **SSR hydration:** `window.__STATE__` injecting user data into global JS without sanitization (XSS)

### State management

- **Vue:** reactive state not mutated outside Pinia/composable, no direct store.$state mutation
- **React:**
  - No direct state mutation (treat state/props as immutable; copy then set)
  - **Rules of Hooks:** call hooks only at top level — never in conditionals, loops, or nested functions; same order every render (enforce via `eslint-plugin-react-hooks`)
  - **Exhaustive deps:** complete dep arrays in `useEffect`/`useMemo`/`useCallback` (enable `react-hooks/exhaustive-deps` lint; do not silence without cause)
  - `useCallback`/`useMemo` to stabilize callbacks/values passed to memoized children
  - **React 19 / React Compiler:** the compiler auto-memoizes — manual `useMemo`/`useCallback`/`React.memo` become largely redundant and should be removed where the compiler is enabled (flag leftover manual memo as cleanup, not a bug)
- **General:** no global mutable state outside store, computed values cached

### Performance patterns

- Lists without `key` prop
- Computed/memo without deps (recalculates every render)
- Heavy computation in render (move to computed/useMemo)
- Event listeners without cleanup on unmount
- Large arrays/objects in reactive state (use shallowRef/shallowReactive)
- Images without dimensions (CLS)
- No virtualization for long lists (>100 items)

> RSC/Nuxt server components: verify server-only code not bundled to client. Check 'use server'/'use client' boundaries. Server secrets must not leak to client.

> Service Workers: verify update mechanism (stale SW = cached vulns). Check scope — broad scope can intercept other-origin requests.

> Bun: replace npm with bun equivalents. Check bun.lockb not package-lock.json.

### WebSocket hygiene

- Multiple `new WebSocket()` to same endpoint (singleton)
- No reconnect logic
- No exponential backoff
- No connection status in UI
- Messages not validated/typed

### Vulnerability grep patterns

| Pattern | Risk | Severity |
|---------|------|----------|
| `dangerouslySetInnerHTML`/`v-html`/`innerHTML` | XSS | HIGH |
| `eval(`/`new Function(` | Code injection | CRITICAL |
| `document.location`/`window.location` + user input | Open redirect | HIGH |
| `localStorage.setItem` + tokens/secrets | Token theft via XSS | HIGH |
| `fetch(userInput)`/`axios(userInput)` | SSRF | HIGH |
| `postMessage("*")`/`addEventListener("message")` no origin check | Cross-origin leak | HIGH |
| `__proto__`/`constructor.prototype` | Prototype pollution | HIGH |
| `console.log` + sensitive data | Info disclosure | MEDIUM |
| `cors: { origin: '*' }` | Permissive CORS | HIGH |
| `process.env.` in client bundle | Secret exposure | CRITICAL |

---

## Level 3: Deep (includes Level 2)

### Accessibility (a11y)

> Requires running dev server. If unavailable, skip with note.

```bash
# Use the detected dev URL (port per framework: 5173 Vite/SvelteKit | 4200 Angular | 3000 Nuxt/Next)
npx --yes @axe-core/cli@4.11.3 "$URL" 2>&1
# Or: eslint-plugin-vuejs-accessibility / eslint-plugin-jsx-a11y
```

Check:
- Images have alt text
- Form inputs have labels
- Interactive elements keyboard-accessible
- Color contrast WCAG AA
- ARIA roles correct
- Focus management in modals/dialogs

### Error handling

- No empty `catch` blocks (minimum: log)
- API errors → user-friendly messages
- Loading/error/empty states in data-fetching components
- Global error boundary (Vue: `app.config.errorHandler`, React: ErrorBoundary)
- Network failure graceful degradation

### Functional UI Testing (Playwright DOM mode)

> Requires running dev server. If unavailable, skip with note.
> Addresses #1 complaint: audits find code issues but miss broken UI.
>
> **DOM mode only — NO screenshots.** Use `browser_snapshot` (accessibility tree) not `browser_take_screenshot` (expensive). Snapshots = structured DOM, fast, zero vision tokens. Screenshots only if user requests visual regression.

**Step 1: Start dev server**

> Detect the dev port per framework (do NOT hardcode 3000): Vite/SvelteKit → `5173`, Angular (`ng serve`) → `4200`, Nuxt/Next → `3000`. Set `PORT`/`URL` accordingly before the readiness loop.

> skip_if: windows (`seq`/`for..do`/`curl` loop is bash). PowerShell equivalent below.

```bash
# bash (Linux/macOS). Set PORT per framework first, e.g. PORT=5173 (Vite/SvelteKit) | 4200 (Angular) | 3000 (Nuxt/Next)
PORT=${PORT:-3000}; URL="http://localhost:$PORT"
if grep -q '"dev"' package.json; then
  npm run dev &
  DEV_PID=$!
  for i in $(seq 1 30); do curl -sf "$URL" >/dev/null && break; sleep 1; done
elif grep -q '"start"' package.json; then
  npm start &
  DEV_PID=$!
  for i in $(seq 1 30); do curl -sf "$URL" >/dev/null && break; sleep 1; done
fi
```

```powershell
# PowerShell (Windows). $Port per framework: 5173 Vite/SvelteKit | 4200 Angular | 3000 Nuxt/Next
$Port = 5173; $Url = "http://localhost:$Port"
$script = if (Select-String '"dev"' package.json -Quiet) { 'dev' } elseif (Select-String '"start"' package.json -Quiet) { 'start' } else { $null }
if ($script) {
  $dev = Start-Process npm -ArgumentList "run $script" -PassThru -NoNewWindow
  foreach ($i in 1..30) {
    try { Invoke-WebRequest $Url -UseBasicParsing -TimeoutSec 1 | Out-Null; break } catch { Start-Sleep -Seconds 1 }
  }
}
```

**Step 2: Broken links & dead navigation**
```bash
# broken-link-checker is abandoned + wrong binary name -> use linkinator (pinned). Use the detected $URL (port per framework).
npx --yes linkinator@7.6.1 "$URL" --recurse 2>&1
```

Playwright DOM audit (`browser_snapshot` after each action):
1. `browser_navigate` each route from router config
2. `browser_snapshot` — verify content (not blank/error)
3. `browser_console_messages` — collect JS errors
4. Each internal `<a>` → click → snapshot → verify loaded, no error
5. All nav items lead to real pages
6. Breadcrumbs link correctly

**Step 3: Interactive elements (DOM crawl)**

Per page, `browser_snapshot`, then per interactive element:

- **Buttons:** click → snapshot → verify DOM changed. Identical = dead button.
- **Forms:** fill → submit → snapshot → verify success/validation
- **Modals:** click trigger → snapshot → verify in DOM → close → verify gone
- **Dropdowns:** select option → snapshot → verify applied
- **Tabs:** click each → snapshot → verify content changed
- **Accordions:** toggle → snapshot → verify appeared/disappeared
- **Search:** fill → submit → snapshot → verify results
- **Pagination:** next/prev → snapshot → verify content changed

> **Optimization:** batch per page. 1 snapshot to enumerate, N clicks with snapshots. Skip shared elements (nav, footer) already verified.

**Step 4: Feature completeness**
- **404:** navigate `/nonexistent-route-test` → snapshot → verify custom 404
- **Auth:** if login exists — fill → submit → verify redirect/state change
- **CRUD:** verify each operation via DOM snapshots
- **File upload:** `browser_file_upload` → verify acceptance
- **Notifications:** trigger → snapshot → verify toast in DOM
- **Loading states:** snapshot during fetch → verify skeleton/spinner
- **Empty states:** list with no data → snapshot → verify "no data" message
- **Responsive:** resize 375/768/1024px → snapshot per breakpoint → verify accessible

**Step 5: Console & network errors**
After each `browser_navigate`:
1. `browser_console_messages` — collect errors
2. `browser_network_requests` — collect failures

Fail criteria:
- `console.error` on page load (excluding known third-party)
- Failed requests (4xx, 5xx) on load
- CORS errors
- Mixed content warnings

**Reporting format:**

| Page/Route | Element | Expected | Actual | Console errors |
|------------|---------|----------|--------|----------------|

> **Cleanup (bash):** `kill $DEV_PID 2>/dev/null` — may need `kill $(lsof -ti:$PORT)` if child persists.
> **Cleanup (PowerShell):** `Stop-Process -Id $dev.Id -Force` — if child persists: `Get-NetTCPConnection -LocalPort $Port | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }`

### License compliance
```bash
# license-checker is abandoned -> license-checker-evergreen (drop-in fork, same --failOn). Copyleft set harmonized with python.md.
npx --yes license-checker-evergreen@6.3.1 --failOn "GPL-2.0;GPL-3.0;LGPL-2.1;LGPL-3.0;AGPL-3.0" 2>&1
# Or: trivy fs --scanners license . 2>&1
```

### Dependency freshness
```bash
npm outdated 2>&1
```

### SSR / Meta-framework checks

<details><summary>Next.js / Nuxt / SvelteKit</summary>

- Hydration mismatch errors
- SEO: meta tags, Open Graph, canonical URLs
- Lazy routes (dynamic imports)
- Route guards/middleware for protected pages
- ISR/SSG where applicable
- API routes don't leak server secrets to client
- `getServerSideProps`/`useAsyncData`/`load` error handling
- Auto-imports configured (Nuxt: no manual composable imports)

</details>

### Overengineering

- Component >300 lines (split)
- Prop drilling >3 levels (provide/inject or store)
- Hook/composable used in 1 place (inline)
- Abstraction over small utility (use directly)
- Multiple state management solutions
