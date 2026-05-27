# Frontend Audit Checks

> **Cross-references:** This file works with [README.md](README.md) (orchestration) and [universal.md](universal.md) (language-agnostic checks).
>
> **Required reading for all agents using this file:**
> - **Confidence Scoring** (README.md) — assign 0-100 score to every finding. Level thresholds: L1≥75, L2≥60, L3≥40.
> - **False Positive Detection** (universal.md) — check stack-specific auto-discard patterns before including findings.
> - **CLI Finding Verification** (universal.md) — 5-step protocol for every CLI tool finding.
> - **YAGNI Check** (universal.md) — verify recommendations are needed before suggesting "add X".
> - **Anti-Rationalization Rules** (universal.md) — do not skip checks or soften findings.

Applies when `package.json` detected. Framework-specific checks auto-selected by detecting:
- `vue` / `nuxt` in dependencies -> Vue checks
- `react` / `next` in dependencies -> React checks
- `svelte` / `@sveltejs/kit` -> Svelte checks
- `angular` -> Angular checks

All commands assume `cd {frontend_root}` (e.g., `cd frontend`).

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
# Or universal (verify version first — v0.69.4-6 compromised, see tools.md):
# trivy fs --scanners vuln --severity HIGH,CRITICAL . 2>&1
```

> If vulnerabilities found, run `npm audit fix`. For breaking changes: `npm audit fix --force` (review changes). Report unfixable vulns as findings.

### Tests (if configured)
```bash
# Detect test runner
if grep -q '"vitest"' package.json; then
  npx vitest run 2>&1
elif grep -q '"jest"' package.json; then
  npx jest --passWithNoTests 2>&1
elif grep -q '"test"' package.json; then
  npm test 2>&1
fi
```

### Node.js runtime currency
```bash
node --version 2>&1
```
> If `npm audit` reports Node.js core vulnerabilities, update Node.js. Use `nvm install --lts` or download from nodejs.org.

**Pass criteria:** 0 errors in all commands.

---

## Level 2: Full (includes Level 1)

### TypeScript strict check

**Vue:**
```bash
npx vue-tsc --noEmit 2>&1
```

**React / generic TS:**
```bash
npx tsc --noEmit 2>&1
```

### Dead exports & unused dependencies
```bash
npx knip 2>&1
```

### Bundle analysis
```bash
# Vite
npx vite-bundle-visualizer 2>&1

# Webpack
npx webpack-bundle-analyzer stats.json 2>&1

# Next.js
ANALYZE=true npm run build 2>&1
```

Check:
- Lazy loading for routes
- No full lodash/moment.js import (use lodash-es, date-fns)
- Tree-shaking working (no side-effect imports)
- Images optimized (WebP, lazy loading)
- CSS scoped / CSS modules (no global style leaks)
- Dynamic imports for heavy components

### Secrets scan
> Skip if Trivy used.
```bash
gitleaks detect --source . --no-git -v 2>&1
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

#### Automated (CLI — run by `waste-scanner` agent)

```bash
# 1. Comprehensive dead code scan (covers: unused deps, imports, exports, files, types)
npx knip@latest --reporter compact 2>&1

# 2. Dead CSS classes in global stylesheets
# List CSS files that are NOT scoped to components (global/shared only)
purgecss --css <global-css-files> --content 'src/**/*.{svelte,vue,jsx,tsx,html}' --rejected --output /dev/null 2>&1

# 3. Dead i18n keys (if project has locale files)
# Configure .i18n-unused.yml first, then:
npx i18n-unused display-unused-keys 2>&1

# 4. Dead environment variables (if .env exists)
npx dotenv-check@latest 2>&1

# 5. TypeScript strictness verification
# Check tsconfig.json for:
#   "noUnusedLocals": true
#   "noUnusedParameters": true
# If not set → MEDIUM finding. Then run:
npx svelte-check 2>&1  # or vue-tsc --noEmit, or tsc --noEmit
```

Findings from tools above: adopt directly, severity = tool's severity or HIGH default.

#### Manual (reasoning — run by `impact-reviewer-frontend`)

These CANNOT be automated by CLI tools and require Opus-level reasoning:

1. **CSS Framework Utilization** — If knip/depcheck does NOT flag a CSS framework (because it's `@import`-ed in CSS, not JS), manually verify: grep component templates for framework-specific class patterns. Zero hits = CRITICAL.

2. **Dead UI Features** — Find state variables controlling visibility (collapsed, expanded, isOpen, showX). Verify trigger (button/toggle) exists AND is visible. State + no trigger = HIGH.

3. **Missing i18n keys** — Reverse check: keys USED in components but MISSING from locale files = BUG (silent fallback to key string).

4. **Dependency Utilization (tool false negatives)** — For deps NOT flagged by knip/depcheck but suspicious:
   - CSS frameworks: see #1 above (template grep)
   - Runtime helpers (tslib, core-js): verify tsconfig/babel actually requires them
   - Type-only packages (@types/*): verify corresponding runtime package exists
---

## Level 2: Code Review (Opus agents)

> **Reviewer mapping:** Security checks → diff-scanner + impact-reviewer. Concurrency → diff-scanner + history-reviewer. Resource leaks → diff-scanner. Convention compliance → convention-checker. Stale comments/TODOs → comment-checker.

### Security review

- **XSS:** `v-html` / `dangerouslySetInnerHTML` / `innerHTML` with user data
- **Open redirect:** `window.location = userInput`, `window.open(userInput)`
- **Sensitive data in localStorage:** tokens, passwords, PII (use httpOnly cookies or secure storage)
- **Eval / Function constructor:** `eval()`, `new Function()`, `setTimeout(string)`
- **PostMessage:** `window.postMessage` without origin check in listener — also check Web Workers' `postMessage`
- **CORS:** frontend sending credentials to wrong origins
- **Source maps:** disabled in production build
- **Prototype pollution:** `_.merge()`, `$.extend()`, `Object.assign()`, spread with user-controlled keys — deep merge of user input into objects can overwrite `__proto__`
- **Subresource Integrity (SRI):** CDN-loaded scripts/styles without `integrity` attribute
- **`window.__STATE__` / SSR hydration:** server-rendered HTML injecting user data into global JS object without sanitization (XSS via hydration)

### State management

- **Vue:** reactive state not mutated outside Pinia/composable, no direct store.$state mutation
- **React:** no direct state mutation, proper dependency arrays in useEffect/useMemo
- **General:** no global mutable state outside store, computed values cached (not recalculated per render)

### Performance patterns

- Lists without `key` prop (Vue: `:key`, React: `key=`)
- Computed/memo without dependencies (recalculates every render)
- Heavy computation in render/template (move to computed/useMemo)
- Event listeners without cleanup on unmount
- Large arrays/objects in reactive state (should be shallowRef/shallowReactive in Vue)
- Images without dimensions (CLS)
- No virtualization for long lists (>100 items)

> React Server Components / Nuxt server components: Verify server-only code is not accidentally bundled to client. Check for 'use server' / 'use client' boundary correctness. Server-only secrets must not leak to client bundle.

> Service Workers: If project registers SW, verify update mechanism (stale SW = cached vulnerabilities). Check SW scope — overly broad scope can intercept requests to other origins.

> Bun runtime: If project uses Bun, replace npm commands with bun equivalents. Check bun.lockb instead of package-lock.json.

### WebSocket hygiene

- Multiple `new WebSocket()` to same endpoint (should be singleton)
- No reconnect logic on disconnect
- Reconnect without exponential backoff
- No connection status in UI
- WS messages not validated/typed

### Quick reference: vulnerability grep patterns

| Pattern | Risk | Severity |
|---------|------|----------|
| `dangerouslySetInnerHTML` / `v-html` / `innerHTML` | XSS | HIGH |
| `eval(` / `new Function(` | Code injection | CRITICAL |
| `document.location` / `window.location` with user input | Open redirect | HIGH |
| `localStorage.setItem` with tokens/secrets | Token theft via XSS | HIGH |
| `fetch(userInput)` / `axios(userInput)` | SSRF | HIGH |
| `postMessage("*")` / `addEventListener("message")` without origin check | Cross-origin data leak | HIGH |
| `__proto__` / `constructor.prototype` | Prototype pollution | HIGH |
| `console.log` with sensitive data | Information disclosure | MEDIUM |
| `cors: { origin: '*' }` | Permissive CORS | HIGH |
| `process.env.` in client bundle | Secret exposure | CRITICAL |

---

## Level 3: Deep (includes Level 2)

### Accessibility (a11y)

> Requires: running dev server. If project has no dev server or `skip_if: no_server`, skip with note.

```bash
# Automated check
npx @axe-core/cli http://localhost:3000 2>&1  # takes URL, not filesystem path
# Or in build:
# eslint-plugin-vuejs-accessibility / eslint-plugin-jsx-a11y
```

Check:
- All images have alt text
- Form inputs have labels
- Interactive elements keyboard-accessible
- Color contrast meets WCAG AA
- ARIA roles used correctly
- Focus management in modals/dialogs

### Error handling

- All `catch` blocks not empty (at minimum log)
- API error responses handled with user-friendly messages
- Loading / error / empty states in data-fetching components
- Global error boundary exists (Vue: `app.config.errorHandler`, React: ErrorBoundary)
- Network failure graceful degradation

### Functional UI Testing (Playwright DOM mode)

> Requires: running dev server. If project has no dev server or `skip_if: no_server`, skip with note.
> This section addresses the #1 user complaint: audits finding code issues but missing broken UI.
>
> **IMPORTANT: DOM mode only — NO screenshots.** Use `browser_snapshot` (accessibility tree, text) instead of `browser_take_screenshot` (image, expensive). Snapshots return structured DOM text — fast, cheap, zero vision tokens. Only use screenshots if user explicitly requests visual regression testing.

**Step 1: Detect and start dev server**
```bash
# Detect dev server command
if grep -q '"dev"' package.json; then
  npm run dev &
  DEV_PID=$!
  # Wait for server readiness (up to 30s)
  for i in $(seq 1 30); do curl -sf http://localhost:3000 >/dev/null && break; sleep 1; done
elif grep -q '"start"' package.json; then
  npm start &
  DEV_PID=$!
  # Wait for server readiness (up to 30s)
  for i in $(seq 1 30); do curl -sf http://localhost:3000 >/dev/null && break; sleep 1; done
fi
```

**Step 2: Broken links & dead navigation**
```bash
# CLI check (fast, no Playwright needed):
npx broken-link-checker http://localhost:3000 --ordered --recursive 2>&1
```

Playwright DOM audit (use `browser_snapshot` after each action):
1. `browser_navigate` to each route from router config
2. `browser_snapshot` — verify page has content (not blank/error)
3. `browser_console_messages` — collect JS errors
4. For each `<a>` in snapshot with internal href → `browser_click` → `browser_snapshot` → verify new page loaded, no error state
5. Check all navigation menu items lead to real pages
6. Verify breadcrumbs link to correct pages

**Step 3: Interactive elements (DOM crawl)**

For each page/route, take `browser_snapshot`, then for each interactive element in the accessibility tree:

- **Buttons:** `browser_click` each button → `browser_snapshot` → verify DOM changed (new content, modal opened, form submitted, etc.). If DOM identical before/after click → dead button, report it.
- **Forms:** `browser_fill_form` with test data → submit → `browser_snapshot` → verify success message or validation errors appear
- **Modals/Dialogs:** `browser_click` trigger → `browser_snapshot` → verify modal in DOM → close → `browser_snapshot` → verify modal gone
- **Dropdowns/Select:** `browser_select_option` → `browser_snapshot` → verify selection applied
- **Tabs:** `browser_click` each tab → `browser_snapshot` → verify content changed
- **Accordions/Collapsibles:** `browser_click` toggle → `browser_snapshot` → verify content appeared/disappeared
- **Search:** `browser_fill_form` search input → submit → `browser_snapshot` → verify results
- **Pagination:** `browser_click` next/prev → `browser_snapshot` → verify content changed

> **Speed optimization:** batch-process pages. Per page: 1 snapshot to enumerate elements, N clicks with snapshots. Typical page = 1 + N snapshots. Skip elements already verified on other pages (shared nav, footer).

**Step 4: Feature completeness**
- **404 page:** `browser_navigate` to `/nonexistent-route-test` → `browser_snapshot` → verify custom 404 content, not blank
- **Auth flows:** if login exists — fill credentials → submit → verify redirect/state change via DOM
- **CRUD operations:** if app has create/read/update/delete — verify each via DOM snapshots
- **File upload:** if upload exists — `browser_file_upload` → verify acceptance
- **Notifications/Toasts:** trigger action → `browser_snapshot` → verify toast/notification in DOM
- **Loading states:** `browser_snapshot` during fetch → verify skeleton/spinner in DOM (use `browser_wait_for` with short timeout)
- **Empty states:** navigate to list page with no data → `browser_snapshot` → verify "no data" message
- **Responsive:** `browser_resize` to 375px, 768px, 1024px → `browser_snapshot` per breakpoint → verify content accessible (no truncated text, no missing elements)

**Step 5: Console & network errors**
After each `browser_navigate`:
1. `browser_console_messages` — collect all errors
2. `browser_network_requests` — collect failed requests

Fail criteria:
- Any `console.error` on page load (excluding known third-party)
- Any failed network request (4xx, 5xx) on page load
- CORS errors
- Mixed content warnings

**Reporting format per broken element:**

| Page/Route | Element (ref from snapshot) | Expected | Actual | Console errors |
|------------|---------------------------|----------|--------|----------------|

> **Cleanup:** after testing, kill dev server: `kill $DEV_PID 2>/dev/null`
> # Note: may need 'kill $(lsof -ti:3000)' if npm child process persists

### License compliance
```bash
npx license-checker --failOn "GPL-2.0;GPL-3.0;AGPL-1.0;AGPL-3.0" 2>&1
# Or: trivy fs --scanners license . 2>&1
```

### Dependency freshness
```bash
npm outdated 2>&1
```

### SSR / Meta-framework checks

<details><summary>Next.js / Nuxt / SvelteKit</summary>

- Hydration mismatch errors (server HTML !== client render)
- SEO: meta tags, Open Graph, canonical URLs
- Lazy routes configured (dynamic imports for route components)
- Route guards / middleware for protected pages
- ISR/SSG where applicable (static pages not SSR'd unnecessarily)
- API routes don't leak server secrets to client bundle
- `getServerSideProps` / `useAsyncData` / `load` error handling
- Auto-imports configured correctly (Nuxt: no manual import of composables)

</details>

### Overengineering

- Component with >300 lines (split it)
- Prop drilling >3 levels (use provide/inject or store)
- Custom hook/composable used in exactly 1 place (inline it)
- Abstraction layer over small utility (just use the utility)
- Multiple state management solutions in same app

