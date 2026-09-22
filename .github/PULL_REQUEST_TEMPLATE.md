## Summary

Describe the change and the user/developer problem it solves.

## Validation

- [ ] `python scripts/release_preflight.py`
- [ ] `python -m unittest discover -s tests/unit -v`
- [ ] Target-platform packaging was tested if packaging/runtime behavior changed.

## Provenance boundary

- [ ] I did not relabel `LOCAL_OBSERVED` or estimated metrics as provider-verified data.
- [ ] Any new metric clearly identifies its evidence/provenance.

## Privacy / security

- [ ] No credentials, tokens, cookies, prompts, responses, private rollout bodies, or monitored source-code bodies were added.
- [ ] Local/generated state remains outside Git.
- [ ] New network behavior, if any, is documented explicitly.

## Release impact

Describe any effect on Windows, macOS ARM64/Intel, Linux amd64, or signing/notarization.
