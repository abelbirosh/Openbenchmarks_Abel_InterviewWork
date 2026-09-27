# Repository conventions

- Keep each Python module in its own directory under `closed_bench/`, exposed through that directory's `__init__.py`. Keep `closed_bench/<module>` imports stable.
- Keep the root README limited to what the tool does, setup, and the engineering log. For every architectural build or change, add one concise dated row to the engineering log with Context, Change, and Result.
- After each push, give the user a brief TL;DR in plain language that an eight-year-old could follow. Include the pushed commit and whether `main` is synchronized.
- Run the commit-time lint hook and the relevant tests before pushing. CI must remain required on `main`.
