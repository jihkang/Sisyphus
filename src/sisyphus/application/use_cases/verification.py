from __future__ import annotations

from dataclasses import dataclass

from ..contracts.spec_validation import SPEC_VALIDATION_GATE_CODES, SPEC_VALIDATION_SOURCES
from ...domain.task.design import (
    DESIGN_ASSESSMENT_APPROPRIATE,
    DESIGN_ASSESSMENT_OVERDESIGNED,
    DESIGN_ASSESSMENT_UNDERDESIGNED,
    ensure_task_design_defaults,
    evaluate_design_adequacy,
)
from ...domain.verification import CommandExecution, VerificationStatus
from ..planning_records import (
    collect_plan_gate_records,
    dedupe_gate_records,
    make_gate_record,
)
from ..ports.clock import ClockPort
from ..ports.planning import PlanningDocumentPort, SpecValidationPort
from ..ports.review import ExternalReviewEvidenceError, ExternalReviewEvidencePort
from ..ports.verification import (
    VerificationCommandPort,
    VerificationConformancePort,
    VerificationDocumentPort,
    VerificationEvidencePort,
)
from ..ports.workflow import EventPublisherPort, TaskRecord, TaskRecordPort, WorkflowEvent
from ..results.verification import VerificationOutcome
from ..verification_projection import looks_like_unfilled_template, render_verify_markdown
from ..verification_records import (
    blocked_phase,
    blocked_stage,
    collect_conformance_gate_records,
    command_execution_to_record,
    record_verification_lifecycle_transition,
)
from .planning import reopen_task_plan_for_design_replan


VERIFY_GATE_CODES = {
    "SPEC_INCOMPLETE",
    "ACCEPTANCE_CRITERIA_MISSING",
    "VERIFICATION_MAPPING_MISSING",
    "EXTERNAL_LLM_POLICY_MISSING",
    "VERIFY_FAILED",
    "DOC_INCOMPLETE",
    "REPRO_MISSING",
    "REGRESSION_TEST_MISSING",
    "AUDIT_LIMIT_REACHED",
    "TEST_STRATEGY_MISSING",
    "EXTERNAL_LLM_REVIEW_REQUIRED",
    "EXTERNAL_LLM_REVIEW_STALE",
    "PLAN_APPROVAL_REQUIRED",
    "PLAN_CHANGES_REQUESTED",
    "DESIGN_REPLAN_REQUIRED",
    "DESIGN_ARTIFACTS_MISSING",
    *SPEC_VALIDATION_GATE_CODES,
}

TRANSIENT_GATE_SOURCES = {
    "verify",
    "docs",
    "strategy",
    "design",
    "close",
    "plan",
    "conformance",
    *SPEC_VALIDATION_SOURCES,
}

CONFORMANCE_CHECKPOINT_DESIGN_ASSESSMENT = "design_assessment"


@dataclass(slots=True)
class VerificationService:
    tasks: TaskRecordPort
    planning_documents: PlanningDocumentPort
    documents: VerificationDocumentPort
    validation: SpecValidationPort
    conformance: VerificationConformancePort
    commands: VerificationCommandPort
    evidence: VerificationEvidencePort
    external_reviews: ExternalReviewEvidencePort
    events: EventPublisherPort
    clock: ClockPort

    def verify(self, task_id: str) -> VerificationOutcome:
        task = self.tasks.load(task_id)
        task = self.planning_documents.sync_strategy(task_id, task)
        lifecycle = record_verification_lifecycle_transition(
            task,
            self.conformance.snapshot(task),
            created_at=self.clock.now(),
        )
        if not lifecycle.allowed:
            task["updated_at"] = self.clock.now()
            task["verify_status"] = VerificationStatus.FAILED.value
            task["status"] = "blocked"
            task["stage"] = blocked_stage(lifecycle)
            task["workflow_phase"] = blocked_phase(lifecycle)
            task["last_verify_results"] = []
            task["last_verified_at"] = self.clock.now()
            artifact = self.documents.write(
                task_id,
                str(task["docs"]["verify"]),
                render_verify_markdown(task, ()),
            )
            self.tasks.save(task)
            self._publish_completion(task)
            return _outcome(task, (), artifact)

        self._evaluate_and_record_design(task)
        task["audit_attempts"] = int(task.get("audit_attempts", 0)) + 1
        task["updated_at"] = self.clock.now()
        task["stage"] = "audit"

        gates = [
            gate
            for gate in task.get("gates", [])
            if gate.get("code") not in VERIFY_GATE_CODES
            and gate.get("source") not in TRANSIENT_GATE_SOURCES
        ]
        if not self.validation.required(task_id, task):
            gates.extend(self._collect_doc_gates(task_id, task))
        spec_gates = self._collect_spec_gates(task_id, task)
        gates.extend(spec_gates)
        design_gates = self._collect_design_gates(task)
        gates.extend(design_gates)
        validation_gates = list(
            self.validation.collect_gates(
                task_id,
                task,
                action="verify",
                require_existing_report=True,
            )
        )
        gates.extend(validation_gates)
        plan_gates = collect_plan_gate_records(
            task,
            action="verify",
            created_at=self.clock.now(),
        )
        gates.extend(plan_gates)
        conformance_gates = collect_conformance_gate_records(
            self.conformance.snapshot(task),
            action="verify",
            created_at=self.clock.now(),
        )
        gates.extend(conformance_gates)

        command_results: tuple[CommandExecution, ...] = ()
        if not (
            spec_gates
            or design_gates
            or validation_gates
            or plan_gates
            or conformance_gates
        ):
            task["stage"] = "audit"
            gates.extend(self._collect_test_strategy_gates(task))
            command_results = self.commands.run(
                task_id,
                tuple(str(command) for command in task.get("verify_commands", [])),
            )
        task["last_verify_results"] = [
            command_execution_to_record(result) for result in command_results
        ]
        task["last_verified_at"] = self.clock.now()

        if any(result.status == VerificationStatus.FAILED for result in command_results):
            gates.append(
                self._gate("VERIFY_FAILED", "one or more verify commands failed", "verify")
            )
        if int(task["audit_attempts"]) >= int(task.get("max_audit_attempts", 10)):
            gates.append(
                self._gate("AUDIT_LIMIT_REACHED", "maximum audit attempts reached", "verify")
            )

        task["gates"] = dedupe_gate_records(gates)
        passed = not task["gates"]
        task["verify_status"] = (
            VerificationStatus.PASSED.value if passed else VerificationStatus.FAILED.value
        )
        task["status"] = "verified" if passed else "blocked"
        if passed:
            task["stage"] = "done"
            task["workflow_phase"] = "verified"
        elif spec_gates:
            task["stage"] = "spec"
        elif design_gates or plan_gates:
            task["stage"] = "plan_review"
        elif validation_gates:
            task["stage"] = "spec"
            task["workflow_phase"] = "spec_in_review"
        else:
            task["stage"] = "audit"

        artifact = self.documents.write(
            task_id,
            str(task["docs"]["verify"]),
            render_verify_markdown(task, command_results),
        )
        task.setdefault("meta", {})["evidence_graph_required"] = True
        self.evidence.write(task_id, task, command_results)
        self.tasks.save(task)
        self._publish_completion(task)
        return _outcome(task, command_results, artifact)

    def _collect_doc_gates(self, task_id: str, task: TaskRecord) -> list[dict]:
        gates: list[dict] = []
        required_doc_keys = ["brief", "plan"] if task["type"] == "feature" else ["brief", "repro", "fix_plan"]
        for key in required_doc_keys:
            relative_path = task["docs"].get(key)
            if not relative_path:
                gates.append(
                    self._gate(
                        "DOC_INCOMPLETE",
                        f"{key} document is missing from task metadata",
                        "docs",
                    )
                )
                continue
            content = self.documents.read(task_id, str(relative_path))
            if content is None:
                gates.append(
                    self._gate("DOC_INCOMPLETE", f"{relative_path} does not exist", "docs")
                )
            elif looks_like_unfilled_template(content.strip()):
                gates.append(
                    self._gate("DOC_INCOMPLETE", f"{relative_path} is incomplete", "docs")
                )

        if task["type"] == "issue":
            repro_path = str(task["docs"].get("repro") or "")
            repro_content = self.documents.read(task_id, repro_path) or ""
            if "Regression Test Target" in repro_content and "Describe the test" in repro_content:
                gates.append(
                    self._gate(
                        "REGRESSION_TEST_MISSING",
                        "issue task is missing a regression test target",
                        "docs",
                    )
                )
        return gates

    def _collect_spec_gates(self, task_id: str, task: TaskRecord) -> list[dict]:
        gates: list[dict] = []
        brief_content = self.documents.read(task_id, str(task["docs"]["brief"])) or ""
        if task["type"] == "feature":
            if "Criterion 1" in brief_content or "- [ ] Criterion 1" in brief_content:
                gates.append(
                    self._gate(
                        "ACCEPTANCE_CRITERIA_MISSING",
                        "feature task requires filled acceptance criteria",
                        "docs",
                    )
                )
        else:
            repro_content = self.documents.read(task_id, str(task["docs"]["repro"])) or ""
            if "1. Step 1" in repro_content or "Describe the test" in repro_content:
                gates.append(
                    self._gate(
                        "SPEC_INCOMPLETE",
                        "issue repro and regression target must be completed before audit",
                        "docs",
                    )
                )

        strategy = task.get("test_strategy", {})
        if not strategy.get("normal_cases") or not strategy.get("edge_cases") or not strategy.get("exception_cases"):
            gates.append(
                self._gate(
                    "SPEC_INCOMPLETE",
                    "task spec must define normal, edge, and exception cases before audit",
                    "strategy",
                )
            )
        if not strategy.get("verification_methods"):
            gates.append(
                self._gate(
                    "VERIFICATION_MAPPING_MISSING",
                    "verification mapping must be completed before audit",
                    "strategy",
                )
            )
        external_llm = strategy.get("external_llm", {})
        if external_llm.get("required") and (
            not external_llm.get("provider")
            or not external_llm.get("purpose")
            or not external_llm.get("trigger")
        ):
            gates.append(
                self._gate(
                    "EXTERNAL_LLM_POLICY_MISSING",
                    "external LLM review policy must be fully defined",
                    "strategy",
                )
            )
        return gates

    def _collect_design_gates(self, task: TaskRecord) -> list[dict]:
        ensure_task_design_defaults(task)
        assessment = task.get("design", {}).get("assessment", {})
        missing_artifacts = list(assessment.get("missing_artifacts") or [])
        gates: list[dict] = []
        if assessment.get("status") == DESIGN_ASSESSMENT_UNDERDESIGNED:
            gates.append(
                self._gate(
                    "DESIGN_REPLAN_REQUIRED",
                    "design assessment requires a plan revision before verify",
                    "design",
                )
            )
        if missing_artifacts:
            gates.append(
                self._gate(
                    "DESIGN_ARTIFACTS_MISSING",
                    f"missing required design artifacts: {', '.join(missing_artifacts)}",
                    "design",
                )
            )
        return gates

    def _collect_test_strategy_gates(self, task: TaskRecord) -> list[dict]:
        strategy = task.get("test_strategy", {})
        gates: list[dict] = []
        normal_cases = strategy.get("normal_cases", [])
        edge_cases = strategy.get("edge_cases", [])
        exception_cases = strategy.get("exception_cases", [])
        verification_methods = strategy.get("verification_methods", [])
        external_llm = strategy.get("external_llm", {})
        if not normal_cases or not edge_cases or not exception_cases or not verification_methods:
            gates.append(
                self._gate(
                    "TEST_STRATEGY_MISSING",
                    "normal, edge, exception cases and verification methods must be defined",
                    "strategy",
                )
            )
        if task["type"] == "issue" and not normal_cases:
            gates.append(
                self._gate(
                    "REPRO_MISSING",
                    "issue task requires explicit regression-oriented test coverage",
                    "strategy",
                )
            )
        if external_llm.get("required") and external_llm.get("status") != "passed":
            gates.append(
                self._gate(
                    "EXTERNAL_LLM_REVIEW_REQUIRED",
                    "required external LLM review is not complete",
                    "strategy",
                )
            )
        elif external_llm.get("required"):
            gates.extend(self._collect_external_review_evidence_gates(task, external_llm))
        return gates

    def _collect_external_review_evidence_gates(
        self,
        task: TaskRecord,
        review: dict,
    ) -> list[dict]:
        report_path = str(review.get("report_path") or "").strip()
        reviewed_head_sha = str(review.get("reviewed_head_sha") or "").strip().lower()
        report_digest = str(review.get("report_digest") or "").strip().lower()
        workspace = str(task.get("worktree_path") or "").strip()
        if not report_path or not reviewed_head_sha or not report_digest or not workspace:
            return [
                self._gate(
                    "EXTERNAL_LLM_REVIEW_STALE",
                    "external LLM review is missing head-bound evidence metadata",
                    "strategy",
                )
            ]
        try:
            inspected = self.external_reviews.inspect(workspace, report_path)
        except ExternalReviewEvidenceError as exc:
            return [
                self._gate(
                    "EXTERNAL_LLM_REVIEW_STALE",
                    f"external LLM review evidence is unavailable: {exc}",
                    "strategy",
                )
            ]
        if inspected.current_head_sha.lower() != reviewed_head_sha:
            return [
                self._gate(
                    "EXTERNAL_LLM_REVIEW_STALE",
                    "external LLM review does not cover the current Git HEAD",
                    "strategy",
                )
            ]
        if inspected.digest.lower() != report_digest:
            return [
                self._gate(
                    "EXTERNAL_LLM_REVIEW_STALE",
                    "external LLM review report digest no longer matches",
                    "strategy",
                )
            ]

        task_dir = str(task.get("task_dir") or "").strip().rstrip("/")
        unrelated = [
            path
            for path in inspected.dirty_paths
            if path != inspected.relative_path
            and not (task_dir and (path == task_dir or path.startswith(f"{task_dir}/")))
        ]
        if unrelated:
            detail = ", ".join(unrelated[:5])
            return [
                self._gate(
                    "EXTERNAL_LLM_REVIEW_STALE",
                    f"external LLM review does not cover workspace changes: {detail}",
                    "strategy",
                )
            ]
        return []

    def _evaluate_and_record_design(self, task: TaskRecord) -> None:
        ensure_task_design_defaults(task)
        previous_status = str(task.get("design", {}).get("assessment", {}).get("status") or "")
        assessment = evaluate_design_adequacy(task)
        status = str(assessment.get("status") or "")
        summary = str(assessment.get("summary") or "design adequacy evaluated")
        if status == DESIGN_ASSESSMENT_UNDERDESIGNED:
            self.conformance.append(
                task,
                checkpoint_type=CONFORMANCE_CHECKPOINT_DESIGN_ASSESSMENT,
                status="yellow",
                summary=summary,
                source="audit.design",
                resolved=False,
                drift=0,
            )
            reopen_task_plan_for_design_replan(
                task,
                actor="design-audit",
                notes=assessment.get("escalation_reason") or summary,
                clock=self.clock,
            )
        elif status in {DESIGN_ASSESSMENT_APPROPRIATE, DESIGN_ASSESSMENT_OVERDESIGNED}:
            self.conformance.append(
                task,
                checkpoint_type=CONFORMANCE_CHECKPOINT_DESIGN_ASSESSMENT,
                status="green",
                summary=summary,
                source="audit.design",
                resolved=previous_status == DESIGN_ASSESSMENT_UNDERDESIGNED,
                drift=0,
            )

    def _gate(self, code: str, message: str, source: str) -> dict:
        return make_gate_record(
            code,
            message,
            source,
            created_at=self.clock.now(),
        )

    def _publish_completion(self, task: TaskRecord) -> None:
        self.events.publish(
            WorkflowEvent(
                event_type="verify.completed",
                source={"module": "audit"},
                data={
                    "task_id": task["id"],
                    "status": task["verify_status"],
                    "stage": task["stage"],
                    "gate_count": len(task["gates"]),
                },
            )
        )


def _outcome(task: TaskRecord, commands: tuple[CommandExecution, ...], artifact) -> VerificationOutcome:
    return VerificationOutcome(
        task_id=str(task["id"]),
        status=str(task["verify_status"]),
        stage=str(task["stage"]),
        audit_attempts=int(task.get("audit_attempts", 0)),
        max_audit_attempts=int(task.get("max_audit_attempts", 10)),
        gates=tuple(task["gates"]),
        command_results=commands,
        verify_artifact=artifact,
    )


__all__ = ["TRANSIENT_GATE_SOURCES", "VERIFY_GATE_CODES", "VerificationService"]
