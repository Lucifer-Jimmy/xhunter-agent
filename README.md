# xhunter-agent

`xhunter-agent` is a modular, auditable security agent platform for authorized
research and CTF environments.

The current implementation starts with the dependency-free W1 kernel,
contracts, and in-memory adapters. Production execution will use a Docker/OCI
sandbox; `LocalSandbox` is reserved for tests.

## Local development

`LocalSandbox` executes commands directly on the host and provides no process,
filesystem, or network isolation. Real mission bootstrap therefore fails
closed unless local development is explicitly enabled:

```sh
XHUNTER_ALLOW_UNSAFE_LOCAL_SANDBOX=1
```

Do not use that setting for untrusted challenge files or production missions.
The future production adapter will target the broadly supported Docker/OCI API
and remain replaceable through the `Sandbox` contract.

Validate configuration with:

```sh
uv run xhunter --config examples/xhunter.toml doctor
```

## Extensions

- Skills are inert repository-owned `skill.toml` and `SKILL.md` directories.
- Built-in Tools implement Tool API v1 and execute only through `Sandbox`.
- Repository-owned plugins register Tools and return a disposer from `start()`.
- External tools use MCP transports; arbitrary third-party Python code is not
  dynamically imported into the Host process.

See `examples/skills/ctf-web-enumeration/` and `examples/plugin-echo/`.
