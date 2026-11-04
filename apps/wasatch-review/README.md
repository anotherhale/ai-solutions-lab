# Wasatch review

React and TypeScript screen for one synthetic Wasatch Business Systems inquiry.

A reviewer opens a support ticket, reads the inbound message and any unsent suggested reply, and approves or rejects that reply. The screen calls the local Wasatch API. It sends `X-Laboratory-Actor` when a laboratory employee is selected. Anonymous access omits the header. `emp_0001` is an approver. `emp_0004` is not.

Approving or rejecting posts to `/api/v1/approval-requests/{approval_id}/decisions`. The page has no send control. It does not call a draft route, an email provider, or any other delivery system.

Wasatch Business Systems data is synthetic.

Nx is not used. This app is a Vite project under `apps/wasatch-review` and does not share a build graph with the API.

## Run locally

Start PostgreSQL, migrate, seed, and the API on port 8000. From the repository root, with `services/wasatch-api/.venv` already installed:

```bash
scripts/wasatch_dev.sh
```

In another shell:

```bash
cd apps/wasatch-review
npm install
npm run dev
```

Open http://127.0.0.1:5173. The dev server proxies `/api` to `http://127.0.0.1:8000`, so `CORS_ORIGINS` can stay empty. Start the API on that address.

`tkt_0007` is the seeded inquiry with suggested reply `msg_0016` and pending approval `apr_0001`. `tkt_0015` is an inbound inquiry with no suggested reply.

Set `VITE_API_BASE_URL` only when the built files are served from a different origin than the API. That origin must be listed in `CORS_ORIGINS`, and the API must be allowed to see `X-Laboratory-Actor`. The dev proxy does not need that setting. Do not set `OPENAI_API_KEY` for this screen. The page does not call a model.

## Checks

These commands do not need a database, an API process, or a provider key:

```bash
npm test
npm run typecheck
npm run build
```

GitHub Actions does not run them. `.github/workflows/validate.yml` has no Node job, and this change does not add one. The Wasatch API database gate is unchanged.
