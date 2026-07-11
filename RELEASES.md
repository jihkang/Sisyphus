# Release Policy

Sisyphus uses Semantic Versioning. While the project remains on `0.x`, minor releases may include deliberate contract changes, but every breaking change still requires migration notes and compatibility review.

## Version Authority

The release version is declared in `pyproject.toml`. A release tag must use the same version with a `v` prefix, for example `0.2.0` and `v0.2.0`.

Version changes follow these rules:

- patch: compatible fixes, documentation corrections, and internal refactors
- minor: new user-visible capabilities or intentional `0.x` contract changes
- major: stable-contract breaking changes after the project reaches `1.0`

Persisted task schemas, event schemas, CLI commands, MCP tool/resource contracts, and public Python imports count as compatibility surfaces.

## Release Gates

A release candidate must satisfy all of the following:

1. `main` is clean and contains the intended release commit.
2. `uv.lock` matches `pyproject.toml` and installation uses `--frozen`.
3. GitHub Actions passes on every supported Python version.
4. The coverage job passes the configured floor and publishes its report artifact.
5. Source and wheel distributions build successfully with `uv build --no-sources`.
6. Relevant Sisyphus tasks are verified, promoted, merge-recorded, and closed.
7. Release notes describe user-visible changes, compatibility impact, and known limitations.

## Release Procedure

From an up-to-date `main` checkout:

```bash
uv lock --check
uv sync --frozen --all-extras --group dev
uv run --frozen python -m unittest discover -s tests -v
uv run --frozen --all-extras --group dev coverage run -m unittest discover -s tests
uv run --frozen --all-extras --group dev coverage report
uv build --no-sources
```

Then:

1. Confirm that the version in `pyproject.toml` is final.
2. Create an annotated `v<version>` tag from the verified `main` commit.
3. Push the tag and create a GitHub release from it.
4. Attach the source distribution and wheel produced from that commit.
5. Include upgrade and compatibility notes in the GitHub release body.

Publishing to a package index is a separate operator decision and requires an explicitly configured trusted-publishing workflow. Do not upload artifacts manually from an unverified local checkout.

## Rollback and Corrections

Published tags are immutable. Correct a bad release with a new patch version; do not move or replace the existing tag. If a release exposes a security issue, remove affected downloadable artifacts when appropriate, document the affected versions, and publish a fixed version through the normal gates.
