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
    assert {"project.name", "project.title", "project.description", "project.purpose",
            "product.stored_data", "product.personal_data"} <= fields
    assert tpl["kit"] == np.VERSION and set(tpl) == set(GOOD)


def test_good_answers_pass():
    assert np.check(GOOD) == []


@pytest.mark.parametrize(("path", "value"), [
    ("kit", "v0"),
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
