# End-to-End Tests

Browser tests for the synthetic Wasatch review workbench in `apps/wasatch-review`.

They start a host-run API against PostgreSQL, serve the built review app with Vite preview (proxying `/api`), and exercise approve-reply and accept-extraction flows. No messages are sent and no financial records are posted.

```bash
# After scripts/bootstrap_laboratory.sh or equivalent setup:
cd tests/e2e
npm ci
npx playwright install chromium
npm test
```

GitHub Actions runs these checks in the **Review workbench browser tests** job alongside unit tests in `apps/wasatch-review`.
