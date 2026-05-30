# Group AI Portal — E2E Tests (planned)

Playwright is not currently installed. To enable:

```bash
cd frontend
npm install -D @playwright/test
npx playwright install
```

Then create `playwright.config.ts` and place spec files in this directory.

Rename `group-ai-portal.spec.ts.future` → `group-ai-portal.spec.ts` to activate the tests once Playwright is added.

## Planned scenarios

### Customer portal

1. Customer ICP editor → save → verify toast / DB embedding written
2. Customer real-time stats page → 3 core metrics load
3. Customer case library CRUD → add 1 entry → appears in list
4. Customer scan history → modal opens → AI candidates shown

### Admin

1. Admin Inbox group-AI interactions → input customer_id → list loads
2. Admin approve suggested → status becomes `sent`
3. Admin A/B experiments → create → start → view report → download CSV

## Env vars required

| Variable | Purpose |
|---|---|
| `E2E_PORTAL_BASE_URL` | Portal dev/staging base URL (e.g. `https://portal.tg1.ai`) |
| `E2E_CUSTOMER_TOKEN` | Valid customer JWT for portal tests |
| `E2E_ADMIN_BASE_URL` | Admin dev/staging base URL |
| `E2E_ADMIN_TOKEN` | Valid admin JWT for admin tests |

## Running

```bash
# Once Playwright is installed:
cd frontend
E2E_PORTAL_BASE_URL=http://localhost:5173 \
E2E_CUSTOMER_TOKEN=<tok> \
E2E_ADMIN_BASE_URL=http://localhost:5173 \
E2E_ADMIN_TOKEN=<tok> \
npx playwright test e2e/
```
