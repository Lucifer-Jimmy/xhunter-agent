import unittest
from collections.abc import Mapping, Sequence

from xhunter.adapters.sandbox.docker import (
    DockerCommandResult,
    DockerSandbox,
    DockerSandboxConfig,
)
from xhunter.application.bootstrap import SandboxConfig, build_mission_sandbox
from xhunter.contracts.sandbox import SandboxRequest


class FakeDockerTransport:
    def __init__(
        self,
        network_exists: bool = False,
        network_internal: bool = True,
    ) -> None:
        self.network_exists = network_exists
        self.network_internal = network_internal
        self.commands: list[tuple[tuple[str, ...], dict[str, str], bytes | None]] = []

    async def run(
        self,
        command: Sequence[str],
        environment: Mapping[str, str],
        stdin: bytes | None = None,
        timeout_seconds: float = 30.0,
    ) -> DockerCommandResult:
        del timeout_seconds
        argv = tuple(command)
        self.commands.append((argv, dict(environment), stdin))
        if "inspect" in argv:
            if not self.network_exists:
                return DockerCommandResult(1, stderr=b"not found")
            return DockerCommandResult(
                0, b"true" if self.network_internal else b"false"
            )
        if "exec" in argv:
            return DockerCommandResult(0, b"sandbox output", b"")
        return DockerCommandResult(0, b"created", b"")


class DockerSandboxTests(unittest.IsolatedAsyncioTestCase):
    async def test_creates_internal_network_and_long_lived_container_once(self) -> None:
        transport = FakeDockerTransport()
        sandbox = DockerSandbox(
            DockerSandboxConfig(
                image="xhunter/base:test",
                docker_host="tcp://linux:2376",
            ),
            transport,
        )
        request = SandboxRequest(
            ("printf", "hello"),
            environment={"TASK_VALUE": "safe"},
            stdin=b"input",
        )
        first = await sandbox.execute(request)
        second = await sandbox.execute(request)
        await sandbox.close()

        commands = [call[0] for call in transport.commands]
        create_network = next(command for command in commands if "create" in command)
        run = next(command for command in commands if "run" in command)
        exec_commands = [command for command in commands if "exec" in command]
        self.assertIn("--internal", create_network)
        self.assertIn("--network", run)
        self.assertIn("--cap-drop", run)
        self.assertIn("no-new-privileges", run)
        self.assertEqual(sum("run" in command for command in commands), 1)
        self.assertEqual(len(exec_commands), 2)
        self.assertEqual(first.stdout, "sandbox output")
        self.assertEqual(second.stdout, "sandbox output")
        self.assertTrue(any("rm" in command for command in commands))
        self.assertTrue(
            all(environment == {} for _, environment, _ in transport.commands)
        )

    async def test_existing_non_internal_network_fails_closed(self) -> None:
        sandbox = DockerSandbox(
            DockerSandboxConfig(image="image"),
            FakeDockerTransport(network_exists=True, network_internal=False),
        )
        with self.assertRaises(RuntimeError):
            await sandbox.execute(SandboxRequest(("true",)))

    def test_bootstrap_constructs_docker_without_unsafe_local_override(self) -> None:
        sandbox = build_mission_sandbox(
            SandboxConfig(provider="docker", image="image"), {}
        )
        self.assertIsInstance(sandbox, DockerSandbox)
