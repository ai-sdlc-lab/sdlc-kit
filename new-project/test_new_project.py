"""/new-project's script: validation, rendering into a repo, lab-admin edits (run: make test)."""

import copy
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import new_project as np  # noqa: E402

GOOD = {
    "kit": "v1",
    "github": {"org": "ai-sdlc-lab"},
    "deploy": {"target": "aws-lambda", "aws_account": "992382408037", "region": "eu-north-1", "when": "on-merge"},
    "local": {"run_app": True},
    "project": {"name": "notes-app", "title": "Notes", "visibility": "public",
                "description": "Personal notes, stored per user", "purpose": "People keep short notes.\nNo sharing."},
    "product": {"users": "authenticated", "auth": "email login with Amazon Cognito", "writes": True,
                "stored_data": "notes: title and text per user", "personal_data": "email addresses",
                "external_services": ["api.example.com"]},
    "first_change": "list my notes",
}


def answers(tmp_path, data=GOOD):
    f = tmp_path / "answers.yml"
    f.write_text(yaml.safe_dump(data))
    return f


def with_(path, value):
    a = copy.deepcopy(GOOD)
    *parents, key = path.split(".")
    node = a
    for p in parents:
        node = node[p]
    node[key] = value
    return a


def test_template_parses_and_lists_every_field_as_missing():
    tpl = yaml.safe_load((HERE / "project.yml").read_text())
    fields = {e["field"] for e in np.check(tpl)}
    assert {"github.org", "project.name", "project.title", "project.visibility", "project.description",
            "project.purpose", "deploy.target", "local.run_app", "product.users", "product.writes",
            "product.stored_data", "product.personal_data"} <= fields  # no defaults: the owner fills every choice
    assert tpl["kit"] == np.VERSION and set(tpl) == set(GOOD)


def test_good_answers_pass():
    assert np.check(GOOD) == []


@pytest.mark.parametrize(("path", "value"), [
    ("kit", "v0"), ("github.org", "other-org"), ("github.org", ""),
    ("deploy.target", ""), ("deploy.target", "k8s"), ("deploy.aws_account", "123456789012"),
    ("deploy.region", "us-east-1"), ("deploy.when", ""), ("deploy.when", "nightly"), ("local.run_app", ""),
    ("project.name", "Notes"), ("project.name", "ab"), ("project.name", "notes-"), ("project.name", "no--tes"),
    ("project.name", "1notes"), ("project.name", "a" * 41),
    ("project.title", "<script>"), ("project.title", "x'; rm -rf /"), ("project.title", ""),
    ("project.visibility", "internal"),
    ("project.description", 'say "hi"'), ("project.description", "${var.x}"), ("project.description", "a\nb"),
    ("project.description", "x" * 121), ("project.purpose", ""), ("project.purpose", "@@NAME@@"),
    ("product.users", "admins"), ("product.auth", ""), ("product.writes", "yes"),
    ("product.external_services", ["https://x.example"]), ("product.external_services", "api.example.com"),
])
def test_bad_answers_are_refused(path, value):
    assert path in {e["field"] for e in np.check(with_(path, value))}


def test_auth_only_for_authenticated_users():
    a = with_("product.users", "anonymous")
    assert {e["field"] for e in np.check(a)} == {"product.auth"}
    a["product"]["auth"] = ""
    assert np.check(a) == []


def test_render_fills_every_placeholder(tmp_path):
    dest = tmp_path / "repo"
    files = np.render(GOOD, str(answers(tmp_path)), dest)
    assert "stages.yml" in files and "api/app/main.py" in files and "project.yml" in files
    assert "repo: notes-app  #" in (dest / "stages.yml").read_text()
    assert "<title>Notes</title>" in (dest / "web/index.html").read_text()
    assert "- Users: authenticated: email login with Amazon Cognito" in (dest / "docs/architecture.md").read_text()
    for f in dest.rglob("*"):
        if f.is_file():
            assert "@@" not in f.read_text(errors="ignore"), f
    kit = HERE.parent / "template"
    for f in kit.rglob("*"):  # kit files land unchanged, except the repo name
        if f.is_file() and f.name != "stages.yml":
            assert (dest / f.relative_to(kit)).read_bytes() == f.read_bytes(), f


def test_render_refuses_non_empty_destination(tmp_path):
    (tmp_path / "repo").mkdir()
    (tmp_path / "repo" / "x").write_text("x")
    with pytest.raises(SystemExit):
        np.render(GOOD, str(answers(tmp_path)), tmp_path / "repo")


LAB = HERE.parent.parent / "lab-admin"


@pytest.mark.skipif(not (LAB / "github.tf").exists(), reason="lab-admin checkout next to sdlc-kit")
def test_lab_admin_adds_one_line_per_map_and_refuses_duplicates(tmp_path):
    for f in ("github.tf", "aws.tf"):
        shutil.copy2(LAB / f, tmp_path / f)
    np.lab_admin(GOOD, tmp_path)
    gh, aws = (tmp_path / "github.tf").read_text(), (tmp_path / "aws.tf").read_text()
    assert re.search(r'^\s*notes-app = \{ visibility = "public", description = "Personal notes, stored per user" \}$', gh, re.M)
    assert re.search(r'^\s*notes-app = \["build-and-test", "stage gate", "security scanners"\]$', gh, re.M)
    assert re.search(r'^\s*notes-app-dev = \{ repo = "notes-app", env = "dev" \}$', aws, re.M)
    assert re.search(r"^\s*notes-app = \{\}$", aws, re.M)
    with pytest.raises(SystemExit):
        np.lab_admin(GOOD, tmp_path)


def test_cli_check_reports_json(tmp_path):
    bad = answers(tmp_path, with_("project.name", "X"))
    r = subprocess.run([sys.executable, "-I", "-B", str(HERE / "new_project.py"), "check", str(bad)],
                       capture_output=True, text=True)
    out = json.loads(r.stdout)
    assert r.returncode == 1 and out["ok"] is False and out["errors"][0]["field"] == "project.name"


NO_DEPLOY = with_("deploy", {"target": "none", "aws_account": "", "region": "", "when": ""})


def test_no_deploy_refuses_aws_fields():
    assert np.check(NO_DEPLOY) == []
    bad = copy.deepcopy(NO_DEPLOY)
    bad["deploy"]["when"] = "on-merge"
    assert {e["field"] for e in np.check(bad)} == {"deploy.when"}


def test_render_without_deploy_has_no_aws(tmp_path):
    a = copy.deepcopy(NO_DEPLOY)
    a["local"]["run_app"] = False
    dest = tmp_path / "repo"
    files = np.render(a, str(answers(tmp_path, a)), dest)
    assert not any(f.startswith(("infra/", ".github/workflows/deploy.yml")) for f in files)
    ci, mk = (dest / ".github/workflows/ci.yml").read_text(), (dest / "Makefile").read_text()
    assert "terraform" not in ci and "needs: [api, web, kind]" in ci
    assert "terraform" not in mk and "\nplan:" not in mk and "run-api" not in mk and "\nbuild:" not in mk
    assert "aws" not in (dest / "README.md").read_text().lower()
    for f in dest.rglob("*"):
        if f.is_file():
            assert "@@" not in f.read_text(errors="ignore"), f


def test_render_deploy_trigger_follows_answer(tmp_path):
    on = np.render(GOOD, str(answers(tmp_path)), tmp_path / "a")
    assert on and "push:\n    branches: [main]" in (tmp_path / "a/.github/workflows/deploy.yml").read_text()
    manual = with_("deploy.when", "manual")
    np.render(manual, str(answers(tmp_path, manual)), tmp_path / "b")
    wf = (tmp_path / "b/.github/workflows/deploy.yml").read_text()
    assert "workflow_dispatch:" in wf and "push:" not in wf
    assert "run-api:" in (tmp_path / "a/Makefile").read_text()


def test_strip_rejects_unbalanced_markers():
    with pytest.raises(SystemExit):
        np.strip("# @@IF:deploy@@\nx\n", {"deploy": True})
    with pytest.raises(SystemExit):
        np.strip("x\n# @@END:deploy@@\n", {"deploy": True})


@pytest.mark.skipif(not (LAB / "github.tf").exists(), reason="lab-admin checkout next to sdlc-kit")
def test_lab_admin_without_deploy_adds_no_aws_role(tmp_path):
    for f in ("github.tf", "aws.tf"):
        shutil.copy2(LAB / f, tmp_path / f)
    before = (tmp_path / "aws.tf").read_text()
    np.lab_admin(NO_DEPLOY, tmp_path)
    assert (tmp_path / "aws.tf").read_text() == before
    assert "notes-app = {" in (tmp_path / "github.tf").read_text()
