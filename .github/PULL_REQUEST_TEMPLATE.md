## What changed

Describe the user-visible or maintainer-visible outcome.

## Why

Link the issue or explain the concrete problem.

## Validation

- [ ] `ruff check .`
- [ ] `ruff format --check .`
- [ ] `python -m unittest discover -s tests -v`
- [ ] `pip-audit -r requirements.txt`
- [ ] `docker compose config --quiet`
- [ ] UI or API flow checked when applicable

## Security and data

- [ ] No API keys, private documents, personal data, or generated runtime stores are included.
- [ ] New configuration is documented in `.env.example` and README.

## Remaining limitations

List anything intentionally left out or not verified.
