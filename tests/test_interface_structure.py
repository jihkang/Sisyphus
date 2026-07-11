from __future__ import annotations

from pathlib import Path
from argparse import Namespace
import sys
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


class InterfaceStructureTests(unittest.TestCase):
    def test_config_module_reexports_infra_loader_surface(self) -> None:
        import sisyphus.config as public_config
        from sisyphus.infra.config import loader

        self.assertIs(public_config.EventBusConfig, loader.EventBusConfig)
        self.assertIs(public_config.SisyphusConfig, loader.SisyphusConfig)
        self.assertIs(public_config.load_config, loader.load_config)
        self.assertIs(public_config.resolve_config_path, loader.resolve_config_path)

    def test_state_module_reexports_task_repository_surface(self) -> None:
        import sisyphus.state as public_state
        from sisyphus.domain.task import repository

        self.assertIs(public_state.ensure_task_record_defaults, repository.ensure_task_record_defaults)
        self.assertIs(public_state.list_task_records, repository.list_task_records)
        self.assertIs(public_state.load_task_record, repository.load_task_record)
        self.assertIs(public_state.normalize_task_projection, repository.normalize_task_projection)
        self.assertIs(public_state.save_task_record, repository.save_task_record)
        self.assertIs(public_state.sync_task_support_files, repository.sync_task_support_files)

    def test_planning_module_reexports_domain_service_surface(self) -> None:
        import sisyphus.planning as public_planning
        from sisyphus.domain.planning import service

        self.assertIs(public_planning.approve_task_plan, service.approve_task_plan)
        self.assertIs(public_planning.freeze_task_spec, service.freeze_task_spec)
        self.assertIs(public_planning.generate_subtasks, service.generate_subtasks)

    def test_workflow_module_delegates_to_domain_service_and_preserves_provider_patch(self) -> None:
        import sisyphus.workflow as public_workflow
        from sisyphus.domain.workflow import service

        repo_root = Path("/tmp/repo")
        config = object()
        original_public_wrapper = public_workflow.run_provider_wrapper
        original_service_wrapper = service.run_provider_wrapper
        patched_wrapper = object()
        try:
            public_workflow.run_provider_wrapper = patched_wrapper
            with mock.patch("sisyphus.domain.workflow.service.run_workflow_cycle", return_value=2) as delegated:
                self.assertEqual(public_workflow.run_workflow_cycle(repo_root, config), 2)
            delegated.assert_called_once_with(repo_root=repo_root, config=config)
            self.assertIs(service.run_provider_wrapper, patched_wrapper)
        finally:
            public_workflow.run_provider_wrapper = original_public_wrapper
            service.run_provider_wrapper = original_service_wrapper

    def test_promotion_module_delegates_to_domain_service_and_preserves_gh_patch(self) -> None:
        import sisyphus.promotion as public_promotion
        from sisyphus.domain.promotion import service

        original_public_run_gh = public_promotion._run_gh
        original_service_run_gh = service._run_gh
        patched_run_gh = object()
        config = object()
        try:
            public_promotion._run_gh = patched_run_gh
            with mock.patch("sisyphus.domain.promotion.service.execute_promotion", return_value="ok") as delegated:
                self.assertEqual(public_promotion.execute_promotion("repo", config, task_id="TF-1"), "ok")
            delegated.assert_called_once_with("repo", config, task_id="TF-1")
            self.assertIs(service._run_gh, patched_run_gh)
        finally:
            public_promotion._run_gh = original_public_run_gh
            service._run_gh = original_service_run_gh

    def test_cli_public_parser_comes_from_parser_module(self) -> None:
        import sisyphus.cli as cli
        from sisyphus.interfaces.cli import parser

        self.assertIs(cli.build_parser, parser.build_parser)
        self.assertEqual(cli.build_parser().prog, "sisyphus")

    def test_cli_dispatch_registry_maps_argparse_names_to_handler_kwargs(self) -> None:
        from sisyphus.interfaces.cli.dispatch import dispatch_command, registered_command_paths

        calls = {}

        def handle_status(**kwargs):
            calls.update(kwargs)
            return 9

        args = Namespace(
            command="status",
            json=True,
            only_open=True,
            only_blocked=False,
            agents=True,
            stale_after_seconds=60,
            repo_root=Path("/tmp/repo"),
        )

        self.assertIn(("status",), registered_command_paths())
        self.assertEqual(dispatch_command(args, [], {"handle_status": handle_status}), 9)
        self.assertEqual(
            calls,
            {
                "as_json": True,
                "only_open": True,
                "only_blocked": False,
                "show_agents": True,
                "stale_after_seconds": 60,
                "repo_root": Path("/tmp/repo"),
            },
        )

    def test_cli_dispatch_registry_passes_agent_run_extras_as_command(self) -> None:
        from sisyphus.interfaces.cli.dispatch import dispatch_command

        calls = {}

        def handle_agent_run(**kwargs):
            calls.update(kwargs)
            return 0

        args = Namespace(
            command="agent",
            agent_command="run",
            task_id="TF-1",
            agent_id="worker-1",
            role="worker",
            provider="codex",
            step=None,
            summary=None,
            owned_paths=None,
            heartbeat_seconds=10,
            repo_root=None,
        )

        self.assertEqual(
            dispatch_command(args, ["python", "-m", "tests"], {"handle_agent_run": handle_agent_run}),
            0,
        )
        self.assertEqual(calls["command"], ["python", "-m", "tests"])

    def test_cli_parser_command_paths_are_registered_for_dispatch(self) -> None:
        import sisyphus.cli as cli
        from sisyphus.interfaces.cli.dispatch import command_path, registered_command_paths

        parser = cli.build_parser()
        samples = [
            ["new", "feature", "add-dashboard"],
            ["request", "create task"],
            ["verify", "TF-1"],
            ["close", "TF-1"],
            ["observe", "TF-1"],
            ["episode", "check", "TF-1"],
            ["eval", "loop", "TF-1"],
            ["eval", "test-first", "TF-1"],
            ["benchmark", "run"],
            ["dataset", "export", "--format", "rl"],
            ["plan", "approve", "TF-1"],
            ["plan", "request-changes", "TF-1"],
            ["plan", "revise", "TF-1"],
            ["spec", "freeze", "TF-1"],
            ["spec", "validate", "TF-1"],
            ["subtasks", "generate", "TF-1"],
            ["agents"],
            ["agent", "start", "TF-1", "worker-1", "--role", "worker"],
            ["agent", "update", "TF-1", "worker-1"],
            ["agent", "finish", "TF-1", "worker-1"],
            ["agent", "run", "TF-1", "worker-1", "--role", "worker", "--provider", "codex", "echo", "ok"],
            ["ingest", "conversation", "create task"],
            ["ingest", "pr-merged", "--pr-number", "1", "--title", "Merge task"],
            ["daemon"],
            ["serve"],
            ["discord-bot"],
            ["index", "rebuild"],
            ["search", "query"],
            ["context", "build", "query"],
            ["evolution", "execute"],
            [
                "evolution",
                "request-followup",
                "EVR-1",
                "--candidate-id",
                "cand-1",
                "--title",
                "Follow up",
                "--summary",
                "Need follow up",
            ],
            ["evolution", "decide", "TF-1"],
            ["evolution", "run", "EVR-1"],
            ["evolution", "status", "EVR-1"],
            ["evolution", "report", "EVR-1"],
            ["evolution", "compare", "EVR-1", "EVR-2"],
            ["status"],
        ]

        parsed_paths = set()
        for argv in samples:
            args, _extras = parser.parse_known_args(argv)
            parsed_paths.add(command_path(args))

        self.assertEqual(parsed_paths, registered_command_paths())

    def test_cli_main_resolves_public_handlers_at_dispatch_time(self) -> None:
        import sisyphus.cli as cli

        argv = [
            "agent",
            "run",
            "TF-1",
            "worker-1",
            "--role",
            "worker",
            "--provider",
            "codex",
            "echo",
            "ok",
        ]
        with mock.patch("sisyphus.cli.handle_agent_run", return_value=7) as delegated:
            self.assertEqual(cli.main(argv), 7)

        delegated.assert_called_once()
        self.assertEqual(delegated.call_args.kwargs["command"], ["echo", "ok"])

    def test_cli_public_new_handler_delegates_to_split_handler(self) -> None:
        import sisyphus.cli as cli

        repo_root = Path("/tmp/repo")
        config = object()
        with (
            mock.patch("sisyphus.cli._resolve_repo_root", return_value=repo_root),
            mock.patch("sisyphus.cli.load_config", return_value=config),
            mock.patch("sisyphus.interfaces.cli.handlers.runtime.handle_new", return_value=0) as delegated,
        ):
            exit_code = cli.handle_new("feature", "add-dashboard", repo_root=repo_root)

        self.assertEqual(exit_code, 0)
        delegated.assert_called_once_with(
            repo_root=repo_root,
            config=config,
            task_type="feature",
            slug="add-dashboard",
        )

    def test_cli_public_daemon_handler_delegates_to_split_handler(self) -> None:
        import sisyphus.cli as cli

        repo_root = Path("/tmp/repo")
        config = object()
        with (
            mock.patch("sisyphus.cli._resolve_repo_root", return_value=repo_root),
            mock.patch("sisyphus.cli.load_config", return_value=config),
            mock.patch("sisyphus.interfaces.cli.handlers.runtime.handle_daemon", return_value=0) as delegated,
        ):
            exit_code = cli.handle_daemon(
                once=True,
                poll_interval_seconds=3,
                max_events=2,
                repo_root=repo_root,
            )

        self.assertEqual(exit_code, 0)
        delegated.assert_called_once_with(
            repo_root=repo_root,
            config=config,
            once=True,
            poll_interval_seconds=3,
            max_events=2,
        )

    def test_cli_public_search_handler_delegates_to_split_handler(self) -> None:
        import sisyphus.cli as cli

        repo_root = Path("/tmp/repo")
        with (
            mock.patch("sisyphus.cli._resolve_repo_root", return_value=repo_root),
            mock.patch("sisyphus.interfaces.cli.handlers.search.handle_search", return_value=7) as delegated,
        ):
            exit_code = cli.handle_search("needle", limit=3, as_json=True, repo_root=repo_root)

        self.assertEqual(exit_code, 7)
        delegated.assert_called_once_with(repo_root=repo_root, query="needle", limit=3, as_json=True)

    def test_cli_public_status_handler_delegates_to_split_handler(self) -> None:
        import sisyphus.cli as cli

        repo_root = Path("/tmp/repo")
        config = object()
        with (
            mock.patch("sisyphus.cli._resolve_repo_root", return_value=repo_root),
            mock.patch("sisyphus.cli.load_config", return_value=config),
            mock.patch("sisyphus.interfaces.cli.handlers.status.handle_status", return_value=0) as delegated,
        ):
            exit_code = cli.handle_status(
                as_json=True,
                only_open=True,
                only_blocked=False,
                show_agents=True,
                stale_after_seconds=60,
                repo_root=repo_root,
            )

        self.assertEqual(exit_code, 0)
        delegated.assert_called_once_with(
            repo_root=repo_root,
            config=config,
            as_json=True,
            only_open=True,
            only_blocked=False,
            show_agents=True,
            stale_after_seconds=60,
        )

    def test_cli_public_request_handler_delegates_to_split_handler(self) -> None:
        import sisyphus.cli as cli

        repo_root = Path("/tmp/repo")
        with (
            mock.patch("sisyphus.cli._resolve_repo_root", return_value=repo_root),
            mock.patch("sisyphus.interfaces.cli.handlers.ingest.handle_request", return_value=0) as delegated,
        ):
            exit_code = cli.handle_request(
                message="create task",
                title="Create Task",
                task_type="feature",
                slug="create-task",
                instruction="follow the plan",
                agent_id="worker-1",
                role="worker",
                provider="codex",
                owned_paths=["src/sisyphus"],
                provider_args=["--full-auto"],
                adopt_current_changes=True,
                adopt_paths=["README.md"],
                no_run=True,
                repo_root=repo_root,
            )

        self.assertEqual(exit_code, 0)
        delegated.assert_called_once_with(
            repo_root=repo_root,
            message="create task",
            title="Create Task",
            task_type="feature",
            slug="create-task",
            instruction="follow the plan",
            agent_id="worker-1",
            role="worker",
            provider="codex",
            owned_paths=["src/sisyphus"],
            provider_args=["--full-auto"],
            adopt_current_changes=True,
            adopt_paths=["README.md"],
            no_run=True,
        )

    def test_cli_public_ingest_pr_handler_delegates_to_split_handler(self) -> None:
        import sisyphus.cli as cli

        repo_root = Path("/tmp/repo")
        changed_files = ['{"path": "src/sisyphus/cli.py", "status": "modified"}']
        with (
            mock.patch("sisyphus.cli._resolve_repo_root", return_value=repo_root),
            mock.patch(
                "sisyphus.interfaces.cli.handlers.ingest.handle_ingest_pull_request_merged",
                return_value=0,
            ) as delegated,
        ):
            exit_code = cli.handle_ingest_pull_request_merged(
                task_id="TF-1",
                branch="feat/example",
                repo_full_name="jihkang/Sisyphus",
                pr_number=12,
                title="Example PR",
                url="https://github.com/jihkang/Sisyphus/pull/12",
                base_branch="main",
                head_branch="feat/example",
                head_sha="abc123",
                merge_commit_sha="def456",
                merged_at="2026-07-06T00:00:00Z",
                merged_by="operator",
                merge_method="squash",
                additions=10,
                deletions=2,
                changed_file_json=changed_files,
                repo_root=repo_root,
            )

        self.assertEqual(exit_code, 0)
        delegated.assert_called_once_with(
            repo_root=repo_root,
            task_id="TF-1",
            branch="feat/example",
            repo_full_name="jihkang/Sisyphus",
            pr_number=12,
            title="Example PR",
            url="https://github.com/jihkang/Sisyphus/pull/12",
            base_branch="main",
            head_branch="feat/example",
            head_sha="abc123",
            merge_commit_sha="def456",
            merged_at="2026-07-06T00:00:00Z",
            merged_by="operator",
            merge_method="squash",
            additions=10,
            deletions=2,
            changed_file_json=changed_files,
        )

    def test_cli_public_plan_handler_delegates_to_split_handler(self) -> None:
        import sisyphus.cli as cli

        repo_root = Path("/tmp/repo")
        config = object()
        with (
            mock.patch("sisyphus.cli._resolve_repo_root", return_value=repo_root),
            mock.patch("sisyphus.cli.load_config", return_value=config),
            mock.patch("sisyphus.interfaces.cli.handlers.planning.handle_plan_approve", return_value=0) as delegated,
        ):
            exit_code = cli.handle_plan_approve("TF-1", reviewer="operator", notes="approved", repo_root=repo_root)

        self.assertEqual(exit_code, 0)
        delegated.assert_called_once_with(
            repo_root=repo_root,
            config=config,
            task_id="TF-1",
            reviewer="operator",
            notes="approved",
        )

    def test_cli_public_agent_run_delegates_to_split_handler(self) -> None:
        import sisyphus.cli as cli

        repo_root = Path("/tmp/repo")
        config = object()
        with (
            mock.patch("sisyphus.cli._resolve_repo_root", return_value=repo_root),
            mock.patch("sisyphus.cli.load_config", return_value=config),
            mock.patch("sisyphus.interfaces.cli.handlers.agent.handle_agent_run", return_value=0) as delegated,
        ):
            exit_code = cli.handle_agent_run(
                task_id="TF-1",
                agent_id="worker-1",
                role="worker",
                provider="codex",
                step="run",
                summary="summary",
                owned_paths=["src/sisyphus"],
                heartbeat_seconds=1,
                command=["python", "-c", "print('ok')"],
                stdin_text="input",
                env={"A": "B"},
                repo_root=repo_root,
            )

        self.assertEqual(exit_code, 0)
        delegated.assert_called_once_with(
            repo_root=repo_root,
            config=config,
            task_id="TF-1",
            agent_id="worker-1",
            role="worker",
            provider="codex",
            step="run",
            summary="summary",
            owned_paths=["src/sisyphus"],
            heartbeat_seconds=1,
            command=["python", "-c", "print('ok')"],
            stdin_text="input",
            env={"A": "B"},
        )

    def test_cli_public_evolution_execute_delegates_to_split_handler(self) -> None:
        import sisyphus.cli as cli

        repo_root = Path("/tmp/repo")
        config = object()
        with (
            mock.patch("sisyphus.cli._resolve_repo_root", return_value=repo_root),
            mock.patch("sisyphus.cli.load_config", return_value=config),
            mock.patch(
                "sisyphus.interfaces.cli.handlers.evolution.handle_evolution_execute",
                return_value=0,
            ) as delegated,
        ):
            exit_code = cli.handle_evolution_execute(
                run_id="EVR-1",
                target_ids=["execution-contract-wording"],
                task_ids=["TF-1"],
                max_events=5,
                repo_root=repo_root,
            )

        self.assertEqual(exit_code, 0)
        delegated.assert_called_once_with(
            repo_root=repo_root,
            config=config,
            run_id="EVR-1",
            target_ids=["execution-contract-wording"],
            task_ids=["TF-1"],
            max_events=5,
            execute_surface=cli.execute_evolution_surface,
        )

    def test_cli_public_verify_handler_delegates_to_split_handler(self) -> None:
        import sisyphus.cli as cli

        repo_root = Path("/tmp/repo")
        config = object()
        with (
            mock.patch("sisyphus.cli._resolve_repo_root", return_value=repo_root),
            mock.patch("sisyphus.cli.load_config", return_value=config),
            mock.patch("sisyphus.interfaces.cli.handlers.verification.handle_verify", return_value=0) as delegated,
        ):
            exit_code = cli.handle_verify("TF-1", repo_root=repo_root)

        self.assertEqual(exit_code, 0)
        delegated.assert_called_once_with(repo_root=repo_root, config=config, task_id="TF-1")

    def test_cli_json_parsing_helpers_normalize_payloads(self) -> None:
        from sisyphus.interfaces.cli.parsing import (
            parse_changed_file_json,
            parse_evidence_summary_json,
            parse_verification_obligation_json,
        )

        self.assertEqual(parse_changed_file_json(['{"path": "src/app.py", "status": "modified"}']), [
            {"path": "src/app.py", "status": "modified"}
        ])

        obligations = parse_verification_obligation_json(
            ['{"claim": "keeps behavior", "method": "unit test", "required": false}']
        )
        self.assertIsNotNone(obligations)
        self.assertEqual(obligations[0].claim, "keeps behavior")
        self.assertFalse(obligations[0].required)

        evidence = parse_evidence_summary_json(
            ['{"kind": "test", "summary": "covered by unit test", "locator": "tests/test_cli.py"}']
        )
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence[0].locator, "tests/test_cli.py")

        with self.assertRaisesRegex(ValueError, "requires non-empty `claim` and `method`"):
            parse_verification_obligation_json(['{"claim": "", "method": ""}'])

    def test_mcp_public_definitions_come_from_split_modules(self) -> None:
        import sisyphus.mcp_core as mcp_core
        from sisyphus.interfaces.mcp import registry, resources, schemas, tools

        self.assertIs(mcp_core.mcp_tool_definitions, tools.mcp_tool_definitions)
        self.assertIs(mcp_core.mcp_resource_definitions, resources.mcp_resource_definitions)

        tool_names = {tool["name"] for tool in tools.mcp_tool_definitions()}
        resource_uris = {resource["uri"] for resource in resources.mcp_resource_definitions()}
        self.assertEqual(tool_names, registry.registered_tool_names())
        self.assertIn("sisyphus.request_task", tool_names)
        self.assertIn("repo://schema/mcp", resource_uris)
        self.assertIn("sisyphus.request_task", schemas._mcp_schema_markdown())

    def test_mcp_tool_executor_registries_match_public_tool_registry(self) -> None:
        from sisyphus.interfaces.mcp import (
            evolution,
            promotion_tools,
            registry,
            search_tools,
            task_tools,
            tools,
            workflow_tools,
        )

        executor_names_by_group = {
            "task": set(task_tools.TOOL_EXECUTORS),
            "search": set(search_tools.TOOL_EXECUTORS),
            "evolution": set(evolution.TOOL_EXECUTORS),
            "promotion": set(promotion_tools.TOOL_EXECUTORS),
            "workflow": set(workflow_tools.TOOL_EXECUTORS),
        }

        self.assertEqual(executor_names_by_group["task"], registry.TASK_TOOL_NAMES)
        self.assertEqual(executor_names_by_group["search"], registry.SEARCH_TOOL_NAMES)
        self.assertEqual(executor_names_by_group["evolution"], registry.EVOLUTION_TOOL_NAMES)
        self.assertEqual(executor_names_by_group["promotion"], registry.PROMOTION_TOOL_NAMES)
        self.assertEqual(executor_names_by_group["workflow"], registry.WORKFLOW_TOOL_NAMES)

        executor_names = set().union(*executor_names_by_group.values())
        schema_names = {tool["name"] for tool in tools.mcp_tool_definitions()}
        self.assertEqual(executor_names, registry.registered_tool_names())
        self.assertEqual(executor_names, schema_names)

    def test_mcp_service_delegates_evolution_tools_to_split_handler(self) -> None:
        from sisyphus.interfaces.mcp import service

        repo_root = Path("/tmp/repo")
        config = object()
        core = service.SisyphusMcpCoreService(repo_root)
        with (
            mock.patch("sisyphus.interfaces.mcp.service.load_config", return_value=config),
            mock.patch(
                "sisyphus.interfaces.mcp.evolution.call_evolution_tool",
                return_value={"run_id": "EVR-1"},
            ) as delegated,
        ):
            payload = core.call_tool("sisyphus.evolution_status", {"run_id": "EVR-1"})

        self.assertEqual(payload, {"run_id": "EVR-1"})
        delegated.assert_called_once_with(
            repo_root=repo_root,
            config=config,
            tool_name="sisyphus.evolution_status",
            args={"run_id": "EVR-1"},
            load_artifacts=service.load_evolution_run_artifacts,
            render_overview=service.render_evolution_run_overview,
            render_status=service.render_evolution_run_status,
            render_report=service.render_evolution_run_report,
            compare_runs=service.compare_evolution_runs,
            render_compare=service.render_evolution_run_compare,
            execute_surface=service.execute_evolution_surface,
            request_followup=service.request_evolution_followup,
            decide_followup=service.evaluate_evolution_followup_decision,
        )

    def test_mcp_service_delegates_task_tools_to_split_handler(self) -> None:
        from sisyphus.interfaces.mcp import service

        repo_root = Path("/tmp/repo")
        config = object()
        core = service.SisyphusMcpCoreService(repo_root)
        with (
            mock.patch("sisyphus.interfaces.mcp.service.load_config", return_value=config),
            mock.patch("sisyphus.interfaces.mcp.task_tools.call_task_tool", return_value={"ok": True}) as delegated,
        ):
            payload = core.call_tool("sisyphus.request_task", {"message": "create task"})

        self.assertEqual(payload, {"ok": True})
        delegated.assert_called_once_with(
            repo_root=repo_root,
            config=config,
            tool_name="sisyphus.request_task",
            args={"message": "create task"},
            request_task_fn=service.request_task,
            list_tasks_fn=service.list_tasks,
            get_task_fn=service.get_task,
        )

    def test_mcp_service_delegates_search_promotion_and_workflow_tools(self) -> None:
        from sisyphus.interfaces.mcp import service

        repo_root = Path("/tmp/repo")
        config = object()
        core = service.SisyphusMcpCoreService(repo_root)
        with (
            mock.patch("sisyphus.interfaces.mcp.service.load_config", return_value=config),
            mock.patch("sisyphus.interfaces.mcp.task_tools.call_task_tool") as task,
            mock.patch("sisyphus.interfaces.mcp.search_tools.call_search_tool", return_value={"search": True}) as search,
        ):
            self.assertEqual(core.call_tool("sisyphus.search", {"query": "needle"}), {"search": True})
        search.assert_called_once()
        task.assert_not_called()

        with (
            mock.patch("sisyphus.interfaces.mcp.service.load_config", return_value=config),
            mock.patch("sisyphus.interfaces.mcp.task_tools.call_task_tool") as task,
            mock.patch("sisyphus.interfaces.mcp.search_tools.call_search_tool") as search,
            mock.patch("sisyphus.interfaces.mcp.evolution.call_evolution_tool") as evolution,
            mock.patch(
                "sisyphus.interfaces.mcp.promotion_tools.call_promotion_tool",
                return_value={"promotion": True},
            ) as promotion,
        ):
            self.assertEqual(core.call_tool("sisyphus.execute_promotion", {"task_id": "TF-1"}), {"promotion": True})
        promotion.assert_called_once()
        task.assert_not_called()
        search.assert_not_called()
        evolution.assert_not_called()

        with (
            mock.patch("sisyphus.interfaces.mcp.service.load_config", return_value=config),
            mock.patch("sisyphus.interfaces.mcp.task_tools.call_task_tool") as task,
            mock.patch("sisyphus.interfaces.mcp.search_tools.call_search_tool") as search,
            mock.patch("sisyphus.interfaces.mcp.evolution.call_evolution_tool") as evolution,
            mock.patch("sisyphus.interfaces.mcp.promotion_tools.call_promotion_tool") as promotion,
            mock.patch(
                "sisyphus.interfaces.mcp.workflow_tools.call_workflow_tool",
                return_value={"workflow": True},
            ) as workflow,
        ):
            self.assertEqual(core.call_tool("sisyphus.verify_task", {"task_id": "TF-1"}), {"workflow": True})
        workflow.assert_called_once()
        task.assert_not_called()
        search.assert_not_called()
        evolution.assert_not_called()
        promotion.assert_not_called()

    def test_mcp_service_delegates_repo_and_task_resources(self) -> None:
        from sisyphus.interfaces.mcp import service

        repo_root = Path("/tmp/repo")
        config = object()
        core = service.SisyphusMcpCoreService(repo_root)
        with (
            mock.patch("sisyphus.interfaces.mcp.service.load_config", return_value=config),
            mock.patch(
                "sisyphus.interfaces.mcp.repo_resources.read_repo_resource",
                return_value={"repo": True},
            ) as repo_resource,
        ):
            self.assertEqual(core.read_resource("repo://status/tasks"), {"repo": True})
        repo_resource.assert_called_once()

        with (
            mock.patch("sisyphus.interfaces.mcp.service.load_config", return_value=config),
            mock.patch("sisyphus.interfaces.mcp.repo_resources.read_repo_resource", return_value=None),
            mock.patch(
                "sisyphus.interfaces.mcp.task_resources.read_task_resource",
                return_value={"task": True},
            ) as task_resource,
        ):
            self.assertEqual(core.read_resource("task://TF-1/record"), {"task": True})
        task_resource.assert_called_once_with(
            repo_root=repo_root,
            config=config,
            parsed=mock.ANY,
            load_record=service.load_task_record,
            list_agents_fn=service.list_agents,
            is_artifact_resource=service.is_feature_task_artifact_resource,
            read_artifact_resource=service.read_feature_task_artifact_resource,
        )

    def test_json_store_round_trips_and_cleans_temp_files(self) -> None:
        from sisyphus.infra.persistence import read_json_file, write_json_file

        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "state" / "record.json"

            write_json_file(path, {"id": "TF-1", "items": [1, 2, 3]})

            self.assertEqual(read_json_file(path), {"id": "TF-1", "items": [1, 2, 3]})
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_agent_repository_round_trips_agent_records(self) -> None:
        from sisyphus.domain.agent import repository

        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            path = repository.agent_file(repo_root, ".planning/tasks", "TF-1", "worker-1")

            repository.save_agent_record(path, {"agent_id": "worker-1", "status": "running"})

            self.assertEqual(repository.read_agent_record(path)["agent_id"], "worker-1")
            self.assertEqual(repository.list_agent_files(repo_root, ".planning/tasks", task_id="TF-1"), [path])
            self.assertEqual(repository.list_agent_files(repo_root, ".planning/tasks"), [path])


if __name__ == "__main__":
    unittest.main()
