# Agent instructions

## Project

This Home Assistant integration polls Audiobookshelf libraries for new books, emits events, and can send detected ebooks to a configured e-reader.

## Working in this repository

- Read `README.md` before changing polling, duplicate suppression, or e-reader delivery behavior.
- Preserve the startup baseline: the first poll establishes the current library state without firing events or resending existing books.
- Before changing CI, check [pschmitt/ci-workflows](https://github.com/pschmitt/ci-workflows) for reusable components and preserve this repository's existing checks.

## Validation

- Run `uvx ruff check .` and `uvx ruff format --check .` for Python changes.
- CI runs Hassfest and the shared Ruff checks; it currently has no test job.
