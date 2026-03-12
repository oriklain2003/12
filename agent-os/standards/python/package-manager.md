# Python Package Manager: uv

Always use **uv** for Python project and package management.

## Rules

- Use `uv` instead of `pip`, `pip-tools`, `poetry`, `pipenv`, or `conda`
- Use `uv init` to create new Python projects
- Use `uv add <package>` to add dependencies (not `pip install`)
- Use `uv remove <package>` to remove dependencies
- Use `uv sync` to install/sync dependencies from `pyproject.toml`
- Use `uv run <command>` to run commands within the project environment
- Use `uv lock` to generate/update the lockfile
- Use `uv venv` if a virtual environment needs to be created explicitly
- Use `uv pip install` only when working outside a uv-managed project

## Project Setup

- Projects should use `pyproject.toml` (not `requirements.txt` or `setup.py`)
- Lock file: `uv.lock` (committed to version control)
- Virtual environment: `.venv/` (not committed)

## Common Commands

```bash
uv init my-project          # Create new project
uv add fastapi uvicorn      # Add dependencies
uv add --dev pytest ruff    # Add dev dependencies
uv sync                     # Install all dependencies
uv run pytest               # Run tests
uv run python main.py       # Run scripts
```
