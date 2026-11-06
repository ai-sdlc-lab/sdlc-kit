# sdlc-kit

The reusable SDLC workflow of the ai-sdlc-lab: one change goes intent → spec → plan → code on a feature
branch, authored and reviewed by subagents in the owner's Claude Code session, checked by a deterministic
gate and a CI verifier (no AI in CI). The only human step is the owner's merge into `main`.
Security requirements, reviewer agents and gate scripts come from `ai-sdlc-lab/appsec-baseline`, pinned by
`appsec-baseline.lock`.

Extracted from `ai-sdlc-lab/dogs-app`, where it was built and proven (changes 0003 and 0004: unattended runs
to the final PR).

## What is in `template/`

Files copied unchanged into a project, at the same paths:

| Path | What |
|---|---|
| `.claude/skills/stage/` | `/stage` skill and the INT/SPEC/PLAN templates |
| `.claude/agents/` | author, intent-completeness, spec-completeness, architecture-conformance |
| `.claude/hooks/protect-paths.py`, `.claude/settings.json` | guardrails: protected paths, author scope, explicit allow list |
| `scripts/` | `stage_step.py` (one call per step), final PR body, stage log, preflight, appsec-baseline checkout and lock check, JUnit merge |
| `stages.yml` | stages, reviewers, rounds; `repo:` is the project's GitHub name |
| `.github/workflows/security.yml` | CI: workflow tests, review verifier, scanners, `stage gate` |
| `.github/CODEOWNERS`, `.github/zizmor.yml` | owner review on protected paths; workflow linter config |
| `security/exceptions.yml`, `security/trivyignore` | the project's own exceptions (empty) |
| `tests/process/` | tests of the workflow itself |
| `appsec-baseline.lock` | the appsec-baseline commit this kit version was proven with |

## What a project provides

- `stages.yml`: `repo: <project>` set to the GitHub repository name.
- Makefile targets: `venv` (also installs `tests/process/requirements.txt`), `fmt`, `test`, `lint`, `build`, and
  `ci-test`: runs every test suite and writes one `junit.xml` (the named-test check reads it).
- `security.yml`: the toolchain setup lines marked "Project toolchain" (dogs-app: Node 24).
- Its own `CLAUDE.md`, `REVIEW.md`, `docs/architecture.md`, `docs/pipeline.md`, `ci.yml`, `deploy.yml`.

v1 is proven for Python and TypeScript web services. Other stacks need their Makefile and toolchain lines;
C++ also needs memory-safety requirements in appsec-baseline first.

## Versions

A tag (`v1`, `v1.1`, …) is a version that a real run went through unattended. The workflow changes only when a
real run stops or asks the owner: root cause, fix, no-AI rehearsal, owner merge, rehearsal on `main`, new tag.
Ideas for improvements are collected in one issue and wait.
