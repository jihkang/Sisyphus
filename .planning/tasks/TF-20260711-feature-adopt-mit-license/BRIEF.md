# Brief

## Task

- Task ID: `TF-20260711-feature-adopt-mit-license`
- Type: `feature`
- Slug: `adopt-mit-license`
- Branch: `feat/adopt-mit-license`

## Problem

- The repository has no root license file, so users and package consumers do not have an explicit grant of rights.
- Python package metadata and the README likewise do not identify a license.

## Desired Outcome

- GitHub and package consumers can identify Sisyphus as MIT licensed.
- The root license text, package metadata, and README all state the same license.
- Runtime behavior remains unchanged.

## Acceptance Criteria

- [ ] Root `LICENSE` contains the canonical MIT text and `Copyright (c) 2026 jihkang`.
- [ ] Python package metadata declares the root license file.
- [ ] README links to the MIT license.
- [ ] Source and wheel distributions include the license text.
- [ ] The full existing test suite still passes.

## Constraints

- Do not change runtime code or behavior.
- Use the operator-selected MIT license without adding incompatible terms.
- Keep the change limited to licensing, package metadata, and task evidence.
