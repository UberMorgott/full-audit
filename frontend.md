# Frontend Audit Checks

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
npm run build && npm run lint 2>&1
```

### Dependency vulnerabilities
```bash
npm audit 2>&1
# Or universal: trivy fs --scanners vuln --severity HIGH,CRITICAL . 2>&1
```

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

## Level 2: Code Review (Opus agents)

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

### WebSocket hygiene

- Multiple `new WebSocket()` to same endpoint (should be singleton)
- No reconnect logic on disconnect
- Reconnect without exponential backoff
- No connection status in UI
- WS messages not validated/typed

---

## Level 3: Deep (includes Level 2)

### Accessibility (a11y)

```bash
# Automated check
npx axe-core-cli . 2>&1
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
