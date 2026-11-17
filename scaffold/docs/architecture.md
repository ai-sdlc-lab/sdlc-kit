# Architecture (as built; starting point from sdlc-kit @@KIT@@)

<!-- @@IF:deploy@@ -->
```
browser ──HTTPS──> Lambda function URL (auth NONE, public)
                    └─ FastAPI + Mangum (python3.14, arm64, 128 MB, 10 s)
                         ├─ GET /api/health
                         └─ static web (Vite build, bundled in the zip)
```
<!-- @@END:deploy@@ -->
<!-- @@IF:nodeploy@@ -->
Not deployed (`project.yml` → `deploy.target: none`). The app runs only in CI (kind) and, if enabled, on the
owner's machine:
```
FastAPI (python3.14, uvicorn)
 ├─ GET /api/health
 └─ static web (Vite build)
```
<!-- @@END:nodeploy@@ -->

One outermost ASGI wrapper sets the SR-004 security headers on every response (fixed CSP: `'self'` only).
Framework validation failures answer `422` with `{"error": "invalid_input", "request_id": ...}` and write one
`input.rejected` JSON line (SR-024 fields) to stdout.
<!-- @@IF:deploy@@ -->
On Lambda, stdout goes to the CloudWatch log group (7 days).
<!-- @@END:deploy@@ -->

## Trust boundaries
<!-- @@IF:deploy@@ -->
1. Internet → function URL: unauthenticated, any caller.
2. Lambda → AWS: execution role `sdlc-lab-app-@@NAME@@-dev` (writes its log group only); carries `sdlc-lab-boundary`.
3. GitHub Actions → AWS: OIDC, role `sdlc-lab-gh-@@NAME@@-dev`, environment `dev` (main only).
<!-- @@END:deploy@@ -->
<!-- @@IF:nodeploy@@ -->
1. No internet exposure and no AWS access: nothing is deployed.
<!-- @@END:nodeploy@@ -->
4. Owner's laptop session → Claude (subscription) and → GitHub with the owner's login: authoring and reviews run
   as local subagents (ADR-0001). The session merges into feature branches only; merging into `main` is the owner's.
5. GitHub Actions → appsec-baseline: the CI verifier and its scripts run at the commit in `appsec-baseline.lock`;
   CI calls no AI.

## Data
None stored yet. No users, no personal data, no writes.

## Product direction (from `project.yml`; not built yet, each part comes through `/stage`)
@@PRODUCT@@

<!-- @@IF:deploy@@ -->
## Known gaps (lab-admin BASELINE)
No CDN/WAF; shared account Lambda concurrency limit of 10 (no reserved concurrency); function URL hostname
changes on rebuild.
<!-- @@END:deploy@@ -->
