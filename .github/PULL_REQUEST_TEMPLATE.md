## What does this change and why?

## Checks

- [ ] `ruff check src tests scripts`
- [ ] `mypy src tests --exclude '\.venv' --follow-imports=skip`
- [ ] `PYTHONPATH=src python -m pytest tests/ -q`
- [ ] `npm --prefix ui run build`
- [ ] New or changed checks have a positive and a negative test
- [ ] No network calls in unit tests, no secrets committed
