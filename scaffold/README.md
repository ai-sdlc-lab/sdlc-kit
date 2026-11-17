# @@NAME@@

@@DESCRIPTION@@

@@PURPOSE@@

Built with the ai-sdlc-lab SDLC workflow (sdlc-kit @@KIT@@): every change goes intent → spec → plan → code
through `/stage` (see `CLAUDE.md`, `docs/pipeline.md`). Setup answers: `project.yml`.

```
browser ──HTTPS──> Lambda function URL (auth NONE)
                    └─ FastAPI via Mangum: /api/* + built web (web/dist)
```

| Path | What |
|---|---|
| `api/` | FastAPI: `GET /api/health`. Lambda via Mangum; container via uvicorn |
| `web/` | Vite + TypeScript page |
| `infra/` | Terraform, state `s3://sdlc-lab-tfstate-992382408037/apps/@@NAME@@/dev/terraform.tfstate` |
| `k8s/` | Deployment + Service for the API container (kind in CI only) |

## Commands

```
make venv            # once
make test lint build
```

CI: `ci.yml` and `security.yml` on pull requests; `deploy.yml` on push to `main` (environment `dev`, OIDC →
`sdlc-lab-gh-@@NAME@@-dev`, terraform apply, smoke test).
