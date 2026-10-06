# Notes for working on this repo

## Dictation rules and the dictionary must stay in sync

Users learn how to dictate from the «Λεξικό υπαγόρευσης» window in the page, built by `app/guide.py`.
Whenever a dictation rule is added or changed (in `app/dictation.py` or `app/numbers.py`):

1. Add or update its entry in `app/guide.py` (with a spoken example; the result is computed by the real rules).
2. Add a test case for the rule (`tests/test_dictation.py` or `tests/test_numbers.py`).
3. Update the tables in `README.md`.

`tests/test_guide.py` fails if a voice command is missing from the dictionary.

## Checks before pushing

- Run `pytest -q` (plain `pytest`, as CI does).
- Pushing to `main` deploys to the production server automatically (see `DEPLOY.md`).
