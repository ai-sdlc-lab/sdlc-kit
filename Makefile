# sdlc-kit's own tooling: /new-project's script and its tests (PyYAML + pytest, hashed, from the template).
.PHONY: venv test

venv:
	python3.14 -m venv .venv
	.venv/bin/pip install -q --require-hashes -r template/tests/process/requirements.txt

test:
	.venv/bin/python3 -I -B -m pytest -q -p no:cacheprovider new-project
