# Releasing

## Cutting a new version

1. **Confirm `main` is green.** All five test suites pass locally and in CI.
   ```bash
   pytest tests/
   ```
2. **Update the version** in `pyproject.toml` (`[project] version = "X.Y.Z"`).
3. **Add a CHANGELOG entry.** New top-of-file section dated today, following the existing format: bullet-list of bug fixes, schema changes, new verifiers, new tools.
4. **Regenerate the manifest.**
   ```bash
   python scripts/regenerate_manifest.py
   ```
   CI runs `scripts/regenerate_manifest.py --check` and fails if the manifest drifts from the current files.
5. **Commit and tag.**
   ```bash
   git add -A
   git commit -m "Release vX.Y.Z"
   git tag vX.Y.Z
   git push origin main --tags
   ```
6. **Build and publish.** PyPI is not currently a publish target. The supported install path is `pip install -e .` from a checkout. If/when a PyPI release is cut:
   ```bash
   python -m build
   python -m twine upload dist/*
   ```

## Frozen distribution snapshots

`concordance_engine-1.0.4/` (gitignored locally) is a frozen snapshot of the 1.0.4 distribution. Snapshots are kept for reproducibility but are not edited after the tag is cut. If a future tester reports a bug against 1.0.4, fix it in `main` and cut a new patch — do not touch the snapshot.

## Release-gate checklist

Before publishing:
- [ ] Five test suites pass on Python 3.10, 3.11, 3.12.
- [ ] `ruff check src/ tests/` clean.
- [ ] CHANGELOG entry written.
- [ ] Version bumped in `pyproject.toml`.
- [ ] Examples/ packets still parse and validate (`python -m concordance_engine.cli validate examples/sample_packet_chemistry_verify.json --now-epoch 9999999999`).
- [ ] MCP server smoke test (`python -c "from concordance_engine.mcp_server.tools import ALL_TOOLS; print(len(ALL_TOOLS))"`).

## Rollback

If a release breaks downstream users:
1. `git revert` the offending commit on `main`.
2. Cut a patch version with the revert.
3. Note the rollback in the CHANGELOG of the patch release.
