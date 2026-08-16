"""Minimal dependency-free CLI."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from xhunter.application.config import load_config
from xhunter.application.models import build_model_provider
from xhunter.application.recovery_commands import (
    get_mission_status,
    recover_task,
)
from xhunter.application.run_agent import run_agent
from xhunter.application.run_ctf import run_ctf
from xhunter.domains.ctf import CtfChallenge
from xhunter.services import RecoveryDecision


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="xhunter")
    parser.add_argument("--config", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "doctor", help="validate configuration and show runtime policy"
    )
    run_parser = subparsers.add_parser(
        "run-agent", help="run one bounded local Agent task"
    )
    run_parser.add_argument("--prompt", required=True)
    run_parser.add_argument("--capability", action="append", default=[])
    run_parser.add_argument("--skill", type=Path, action="append", default=[])
    ctf_parser = subparsers.add_parser(
        "run-ctf", help="run one authorized CTF mission"
    )
    ctf_parser.add_argument("--name", required=True)
    ctf_parser.add_argument("--category", required=True)
    ctf_parser.add_argument("--target", action="append", required=True)
    ctf_parser.add_argument("--flag-pattern", default=r"(?:flag|ctf)\{[^}\r\n]+\}")
    status_parser = subparsers.add_parser(
        "status", help="show persisted Mission and Task status"
    )
    status_parser.add_argument("--mission-id", required=True)
    recover_parser = subparsers.add_parser(
        "recover-task", help="resolve an unknown Tool outcome"
    )
    recover_parser.add_argument("--task-id", required=True)
    recover_choice = recover_parser.add_mutually_exclusive_group(required=True)
    recover_choice.add_argument("--retry", action="store_true")
    recover_choice.add_argument("--fail", action="store_true")
    arguments = parser.parse_args(argv)
    config = load_config(arguments.config)
    if arguments.command == "doctor":
        print(
            json.dumps(
                {
                    "sandbox_provider": config.sandbox_provider,
                    "allowed_targets": config.allowed_targets,
                    "blocked_targets": config.blocked_targets,
                    "trace_path": str(config.trace_path),
                    "local_sandbox_unsafe": config.sandbox_provider == "local",
                },
                indent=2,
            )
        )
        return 0
    if arguments.command == "run-agent":
        model = build_model_provider(config.model)
        result = asyncio.run(
            run_agent(
                config,
                model,
                os.environ,
                arguments.prompt,
                tuple(arguments.capability),
                tuple(arguments.skill),
            )
        )
        print(result)
        return 0
    if arguments.command == "run-ctf":
        model = build_model_provider(config.model)
        result = asyncio.run(
            run_ctf(
                config,
                model,
                os.environ,
                CtfChallenge(
                    arguments.name,
                    arguments.category,
                    tuple(arguments.target),
                    arguments.flag_pattern,
                ),
            )
        )
        print(
            json.dumps(
                {
                    "mission_id": result.mission_id,
                    "status": result.status.value,
                    "completed_tasks": result.completed_tasks,
                    "failed_tasks": result.failed_tasks,
                },
                indent=2,
            )
        )
        return 0
    if arguments.command == "status":
        result = asyncio.run(get_mission_status(config, arguments.mission_id))
        print(
            json.dumps(
                {
                    "mission_id": result.mission_id,
                    "name": result.name,
                    "status": result.status.value,
                    "tasks": [
                        {
                            "task_id": task.task_id,
                            "objective": task.objective,
                            "status": task.status.value,
                            "checkpoint_present": task.checkpoint_present,
                        }
                        for task in result.tasks
                    ],
                },
                indent=2,
            )
        )
        return 0
    if arguments.command == "recover-task":
        decision = (
            RecoveryDecision.RETRY if arguments.retry else RecoveryDecision.FAIL
        )
        task = asyncio.run(recover_task(config, arguments.task_id, decision))
        print(
            json.dumps(
                {"task_id": task.task_id, "status": task.status.value}, indent=2
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
