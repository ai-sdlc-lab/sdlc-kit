"""/new-project's deterministic steps. Run with sdlc-kit's venv (`make venv`): .venv/bin/python3 -I -B new-project/new_project.py

  check FILE                 validate the answers; prints JSON {"ok": bool, "errors": [{"field", "error"}]}
  render FILE DEST           write the new repository's files into DEST (missing or empty except .git)
  lab-admin FILE LAB_DIR     add the project to lab-admin's Terraform (repo, rulesets' checks, CI role, deploy policy)

Answers are data: they only ever land in fixed places (docs, page title, Terraform strings), after the checks
below restrict them to characters that can't break out of those places.
"""

import json
import re
import shutil
import sys
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parent.parent
VERSION = "v1"
CHECKS = '["build-and-test", "stage gate", "security scanners"]'  # same required checks as dogs-app
NAME = re.compile(r"^[a-z](?:[a-z0-9]|-(?=[a-z0-9])){2,39}$")
TITLE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .-]{0,39}$")
LINE = re.compile(r'^[^"\\$`{}<>\n\r@]{1,120}$')  # one line, safe in a Terraform string and Markdown
HOST = re.compile(r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
TEXT_MAX = 800
SKIP = {"__pycache__", ".ruff_cache", ".pytest_cache", "node_modules"}  # local tool output, never part of the kit
# What v1 can build. Every choice is the owner's: the template has no defaults and `check` rejects blanks.
ORG = "ai-sdlc-lab"  # the org lab-admin manages
AWS_ACCOUNT, AWS_REGION = "992382408037", "eu-north-1"  # the lab account lab-admin manages
NO_DEPLOY_PATHS = ("infra/", ".github/workflows/deploy.yml")
MARK = re.compile(r"@@(IF|END):(\w+)@@")


def _text(v, field, errors, required=True):
    if not isinstance(v, str) or (required and not v.strip()):
        errors.append({"field": field, "error": "required text"})
    elif len(v) > TEXT_MAX or "@@" in v or "\r" in v:
        errors.append({"field": field, "error": f"at most {TEXT_MAX} characters, no '@@'"})


def check(a) -> list[dict]:
    e: list[dict] = []
    if not isinstance(a, dict):
        return [{"field": "-", "error": "not a YAML mapping"}]
    p, prod = a.get("project") or {}, a.get("product") or {}
    gh, dep, loc = a.get("github") or {}, a.get("deploy") or {}, a.get("local") or {}
    if a.get("kit") != VERSION:
        e.append({"field": "kit", "error": f"must be {VERSION} (this kit)"})
    if gh.get("org") != ORG:
        e.append({"field": "github.org", "error": f"{ORG} (the only org lab-admin manages in {VERSION})"})
    target = dep.get("target")
    if target not in ("none", "aws-lambda"):
        e.append({"field": "deploy.target", "error": "none or aws-lambda"})
    lam = {"aws_account": AWS_ACCOUNT, "region": AWS_REGION, "when": ("on-merge", "manual")}
    for k, ok in lam.items():
        v, allowed = dep.get(k), ok if isinstance(ok, tuple) else (ok,)
        if target == "aws-lambda" and str(v) not in allowed:
            e.append({"field": f"deploy.{k}", "error": " or ".join(allowed) + f" (what {VERSION} supports)"})
        elif target == "none" and v not in ("", None):
            e.append({"field": f"deploy.{k}", "error": "only for aws-lambda; leave empty"})
    if not isinstance(loc.get("run_app"), bool):
        e.append({"field": "local.run_app", "error": "true or false"})
    if not isinstance(p.get("name"), str) or not NAME.match(p["name"]):
        e.append({"field": "project.name", "error": "a-z, 0-9 and single '-', 3-40 characters, starts with a letter"})
    if not isinstance(p.get("title"), str) or not TITLE.match(p["title"]):
        e.append({"field": "project.title", "error": "1-40 characters: letters, digits, space, '.', '-'"})
    if p.get("visibility") not in ("public", "private"):
        e.append({"field": "project.visibility", "error": "public or private"})
    if not isinstance(p.get("description"), str) or not LINE.match(p["description"]):
        e.append({"field": "project.description", "error": 'one line, 1-120 characters, none of " \\ $ ` { } < > @'})
    _text(p.get("purpose"), "project.purpose", e)
    if prod.get("users") not in ("anonymous", "authenticated"):
        e.append({"field": "product.users", "error": "anonymous or authenticated"})
    auth = prod.get("auth", "")
    if prod.get("users") == "authenticated":
        _text(auth, "product.auth", e)
    elif auth not in ("", None):
        e.append({"field": "product.auth", "error": "only for authenticated users; leave empty"})
    if not isinstance(prod.get("writes"), bool):
        e.append({"field": "product.writes", "error": "true or false"})
    _text(prod.get("stored_data"), "product.stored_data", e)
    _text(prod.get("personal_data"), "product.personal_data", e)
    hosts = prod.get("external_services", [])
    if not isinstance(hosts, list) or not all(isinstance(h, str) and HOST.match(h) for h in hosts):
        e.append({"field": "product.external_services", "error": "a list of host names, e.g. [api.example.com]"})
    _text(a.get("first_change", "") or "", "first_change", e, required=False)
    return e


def load(path: str) -> dict:
    raw = Path(path).read_text()
    if len(raw) > 20_000:
        sys.exit("answers file larger than 20 kB")
    return yaml.safe_load(raw)


def product(a) -> str:
    prod = a["product"]
    users = "authenticated: " + prod["auth"].strip() if prod["users"] == "authenticated" else "anonymous (no login)"
    hosts = ", ".join(prod.get("external_services") or []) or "none"
    lines = [
        f"- Users: {users}",
        f"- Writes: {'yes: users create, change, delete or upload data' if prod['writes'] else 'no (read-only)'}",
        f"- Stored data: {prod['stored_data'].strip()}",
        f"- Personal data: {prod['personal_data'].strip()}",
        f"- External services: {hosts}",
    ]
    if (a.get("first_change") or "").strip():
        lines.append(f"- First change: {a['first_change'].strip()}")
    return "\n".join(lines)


def flags(a) -> dict[str, bool]:
    deploy = a["deploy"]["target"] == "aws-lambda"
    run = a["local"]["run_app"]
    on_merge = deploy and a["deploy"]["when"] == "on-merge"
    return {"deploy": deploy, "nodeploy": not deploy, "on_merge": on_merge, "manual": deploy and not on_merge,
            "run_local": run, "norun_local": not run}


def strip(text: str, f: dict[str, bool]) -> str:
    """Keep lines inside @@IF:x@@ ... @@END:x@@ only when flag x is on; marker lines always go."""
    out, keep = [], []
    for line in text.splitlines(keepends=True):
        m = MARK.search(line)
        if m and m[1] == "IF":
            keep.append(f[m[2]])
        elif m:
            if not keep:
                sys.exit(f"unbalanced @@END:{m[2]}@@")
            keep.pop()
        elif all(keep):
            out.append(line)
    if keep:
        sys.exit("unclosed @@IF@@ block")
    return "".join(out)


def render(a, src_file: str, dest: Path) -> list[str]:
    if dest.exists() and any(p.name != ".git" for p in dest.iterdir()):
        sys.exit(f"{dest} is not empty")
    p = a["project"]
    values = {
        "@@NAME@@": p["name"],
        "@@TITLE@@": p["title"],
        "@@DESCRIPTION@@": p["description"],
        "@@PURPOSE@@": " ".join(p["purpose"].split()),
        "@@PRODUCT@@": product(a),
        "@@KIT@@": VERSION,
    }
    f_on = flags(a)
    written = []
    for base, fill in ((KIT / "template", False), (KIT / "scaffold", True)):
        for f in sorted(x for x in base.rglob("*") if x.is_file() and not SKIP & set(x.parts)):
            rel = f.relative_to(base)
            if fill and f_on["nodeploy"] and rel.as_posix().startswith(NO_DEPLOY_PATHS):
                continue
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            if fill:
                text = strip(f.read_text(), f_on)
                for k, v in values.items():
                    text = text.replace(k, v)
                out.write_text(text)
            else:
                shutil.copy2(f, out)
            written.append(rel.as_posix())
    stages = dest / "stages.yml"
    stages.write_text(stages.read_text().replace("repo: <project>", f"repo: {p['name']}", 1))
    shutil.copy2(src_file, dest / "project.yml")
    left = [w for w in written if "@@" in (dest / w).read_text(errors="ignore")]
    if left or f"repo: {p['name']}" not in stages.read_text():
        sys.exit(f"placeholders left in {left or ['stages.yml']}")
    return written + ["project.yml"]


def insert(path: Path, marker: str, line: str) -> None:
    text = path.read_text()
    if text.count(marker) != 1:
        sys.exit(f"{path.name}: marker {marker!r} not found exactly once")
    path.write_text(text.replace(marker, f"{line}\n{marker}", 1))


def lab_admin(a, lab: Path) -> None:
    p = a["project"]
    n, desc = p["name"], p["description"]
    gh, aws = lab / "github.tf", lab / "aws.tf"
    if re.search(rf"^\s*{n}\s*=\s*\{{\s*visibility", gh.read_text(), re.MULTILINE):
        sys.exit(f"github.tf: repository {n} already exists")
    insert(gh, "    # /new-project: repos above", f'    {n} = {{ visibility = "{p["visibility"]}", description = "{desc}" }}')
    if p["visibility"] == "public":  # rulesets exist only for public repos (GitHub Free)
        insert(gh, "    # /new-project: required checks above", f"    {n} = {CHECKS}")
    if a["deploy"]["target"] == "aws-lambda":  # no deploy: no AWS role, no deploy environment
        insert(aws, "    # /new-project: CI roles above", f'    {n}-dev = {{ repo = "{n}", env = "dev" }}')
        insert(aws, "    # /new-project: Lambda apps above", f"    {n} = {{}}")


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("check", "render", "lab-admin"):
        print(__doc__)
        return 2
    a = load(argv[1])
    errors = check(a)
    if argv[0] == "check" or errors:
        print(json.dumps({"ok": not errors, "errors": errors}, indent=1))
        return 1 if errors else 0
    if argv[0] == "render" and len(argv) == 3:
        print(json.dumps({"ok": True, "files": len(render(a, argv[1], Path(argv[2])))}))
        return 0
    if argv[0] == "lab-admin" and len(argv) == 3:
        lab_admin(a, Path(argv[2]))
        print(json.dumps({"ok": True}))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
