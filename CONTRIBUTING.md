# Contributing

AI Usage Monitor is a local-first desktop project.

Before submitting a change:

1. Do not commit credentials, browser cookies, provider tokens, prompts,
   responses, local account identifiers, or monitored project source code.
2. Keep provider-specific logic behind the provider boundary.
3. Preserve metric provenance. Do not present locally observed token totals as
   provider billing totals.
4. Run:

   `python scripts/release_preflight.py`

   `python -m unittest discover -s tests/unit -v`

5. Changes to packaging should be validated on the target operating system.

Generated local state such as `data/`, `schemas/`, `config/local.*`, `build/`,
`dist/`, and `release/` must remain outside Git.
