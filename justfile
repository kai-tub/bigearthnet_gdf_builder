
env-cmd := "poetry run"
set dotenv-load := false

install: install_python_deps install_ipykernel

install_python_deps:
    poetry install

install_ipykernel:
	{{env-cmd}} python -m ipykernel install --user

build: install_ipykernel
	{{env-cmd}} sphinx-build {{justfile_directory()}}/docs {{justfile_directory()}}/docs/_build/

serve-docs: build
	{{env-cmd}} python {{justfile_directory()}}/serve_docs.py

test:
	{{env-cmd}} pytest tests/
