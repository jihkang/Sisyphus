from __future__ import annotations

from pathlib import Path

from ..application.use_cases.obligations import ObligationConvergenceService
from ..application.use_cases.verification import VerificationService
from ..infra.config.loader import SisyphusConfig
from ..infra.obligations import RepositoryObligationRuntimeAdapter
from .verification import build_verification_service


def build_obligation_convergence_service(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    verification: VerificationService | None = None,
) -> ObligationConvergenceService:
    verifier = verification or build_verification_service(repo_root, config)
    return ObligationConvergenceService(
        runtime=RepositoryObligationRuntimeAdapter(
            repo_root,
            config,
            verify_task=verifier.verify,
        )
    )


__all__ = ["build_obligation_convergence_service"]
