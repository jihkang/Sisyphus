# Brief

## Task

- Task ID: `TF-20260416-feature-plan-mobile-friendly-automation-spec`
- Type: `feature`
- Slug: `plan-mobile-friendly-automation-spec`
- Branch: `feat/plan-mobile-friendly-automation-spec`

## Problem

- Sisyphus already has task orchestration, service-loop notifications, Discord intake, and a separate remote/mobile bridge surface, but those pieces are not defined as one automation product.
- The repository needs an OpenClaw-style automation spec that makes phone-first monitoring and lightweight intervention a first-class operator path.
- The spec should be grounded in the existing implementation seams instead of inventing a parallel control plane.

## Desired Outcome

- A repository document defines a concrete phone-first automation model for Sisyphus.
- The spec identifies which current modules are reused, which new modules are needed, and what the MVP implementation order should be.
- The spec makes Discord the immediate mobile surface and treats the remote/mobile bridge as an optional drill-down path.

## Acceptance Criteria

- [ ] A doc-backed automation spec exists in the repository for OpenClaw-style phone-first operation.
- [ ] The spec maps onto current code paths such as `discord_bot`, `service`, `workflow`, and the bundled remote/mobile session surface.
- [ ] The spec defines typed triggers, actions, safety constraints, and phone-friendly operator commands.
- [ ] The spec breaks delivery into MVP slices that can be implemented incrementally.
- [ ] The task docs reflect this planning scope and verification approach.

## Constraints

- Reuse existing repository conventions and implementation seams where possible.
- Do not promise a brand-new native mobile app as the first implementation step.
- Re-read the task docs before verify and close.
