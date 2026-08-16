import sys

import pytest

from xhunter.adapters.memory import FakeSandbox
from xhunter.adapters.sandbox import LocalSandbox
from xhunter.contracts.sandbox import SandboxRequest, SandboxResult


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["fake", "local"])
async def test_sandbox_contract(provider: str) -> None:
    sandbox = (
        FakeSandbox(SandboxResult(0, stdout="contract\n"))
        if provider == "fake"
        else LocalSandbox({})
    )
    request = (
        SandboxRequest(("unused",))
        if provider == "fake"
        else SandboxRequest((sys.executable, "-I", "-c", "print('contract')"))
    )
    result = await sandbox.execute(request)
    await sandbox.close()
    assert result.exit_code == 0
    assert result.stdout.strip() == "contract"
