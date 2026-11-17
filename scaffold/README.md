# @@NAME@@

@@DESCRIPTION@@

@@PURPOSE@@

Built with the ai-sdlc-lab SDLC workflow (sdlc-kit @@KIT@@): every change goes intent → spec → plan → code
through `/stage` (see `CLAUDE.md`, `docs/pipeline.md`). Setup answers: `project.yml`.

<!-- @@IF:deploy@@ -->
```
browser ──HTTPS──> Lambda function URL (auth NONE)
                    └─ FastAPI via Mangum: /api/* + built web (web/dist)
```
<!-- @@END:deploy@@ -->
<!-- @@IF:nodeploy@@ -->
Not deployed anywhere (`project.yml` → `deploy.target: none`).
<!-- @@END:nodeploy@@ -->

| Path | What |
|---|---|
| `api/` | FastAPI: `GET /api/health`. Lambda via Mangum; container via uvicorn |
| `web/` | Vite + TypeScript page |
<!-- @@IF:deploy@@ -->
| `infra/` | Terraform, state `s3://sdlc-lab-tfstate-992382408037/apps/@@NAME@@/dev/terraform.tfstate` |
<!-- @@END:deploy@@ -->
| `k8s/` | Deployment + Service for the API container (kind in CI only) |

## Commands

```
make venv            # once
make test lint
<!-- @@IF:run_local@@ -->
make run-api         # then, in a second terminal: npm --prefix web run dev → http://localhost:5173
<!-- @@END:run_local@@ -->
```

CI: `ci.yml` and `security.yml` on pull requests.
<!-- @@IF:on_merge@@ -->
`deploy.yml` on every merge into `main` (environment `dev`, OIDC → `sdlc-lab-gh-@@NAME@@-dev`, terraform
apply, smoke test).
<!-- @@END:on_merge@@ -->
<!-- @@IF:manual@@ -->
`deploy.yml` only when started by hand (Actions → deploy → Run workflow on `main`; environment `dev`, OIDC →
`sdlc-lab-gh-@@NAME@@-dev`, terraform apply, smoke test). Merging into `main` deploys nothing.
<!-- @@END:manual@@ -->
<!-- @@IF:nodeploy@@ -->
No deploy workflow.
<!-- @@END:nodeploy@@ -->
