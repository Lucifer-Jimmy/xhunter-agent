# xhunter-agent

`xhunter-agent` is a modular, auditable security agent platform for authorized
research and CTF environments.

The current local MVP includes the ReAct runtime, deterministic middleware
gates, Skills, Tool Plugin API v1, sandbox-backed MCP, five built-in Tools, a
CTF Domain Pack, persistent local repositories, audit tracing, budgets, leases,
checkpoint recovery, and Docker/OCI plus unsafe-local Sandbox adapters.

## Local development

`LocalSandbox` executes commands directly on the host and provides no process,
filesystem, or network isolation. Real mission bootstrap therefore fails
closed unless local development is explicitly enabled:

```sh
XHUNTER_ALLOW_UNSAFE_LOCAL_SANDBOX=1
```

Do not use that setting for untrusted challenge files or production missions.
For isolated execution, configure `sandbox.provider = "docker"`; the adapter
uses the broadly supported Docker/OCI CLI contract and supports remote
`DOCKER_HOST` through configuration.

Validate configuration with:

```sh
uv run xhunter --config examples/xhunter.toml doctor
```

Run one local Agent task with an explicit unsafe-local acknowledgement:

```sh
export XHUNTER_ALLOW_UNSAFE_LOCAL_SANDBOX=1
export XHUNTER_MODEL_API_KEY=your-control-plane-model-key
uv run xhunter --config examples/xhunter.toml run-agent \
  --prompt "Inspect the authorized target" \
  --capability network.http \
  --skill examples/skills/ctf-web-enumeration
```

`run-agent` is for trusted local development only. Tool calls still pass through
capability resolution, model/tool budgets, ScopePolicy, evidence capture, and
the configured Sandbox adapter.

Run a complete CTF Mission through the Domain, MissionService, Agent, Verifier,
Evidence, and Checkpoint layers:

```sh
uv run xhunter --config examples/xhunter.toml run-ctf \
  --name "Authorized Web Challenge" \
  --category web \
  --target challenge.local \
  --description "目标是一个登录系统。分析认证流程和输入点，找到并返回 flag。"
```

For a longer challenge statement, use
`--description-file /path/to/challenge.md` instead of placing the full natural
language description on the command line. Target, category, and flag pattern
remain deterministic security constraints rather than model-inferred values.

The target must be declared both by the CTF challenge and in the configured
`policy.allowed_targets`; challenge input never expands the policy whitelist.

Inspect and recover persisted work without starting a model or Sandbox:

```sh
uv run xhunter --config examples/xhunter.toml status --mission-id <mission-id>
uv run xhunter --config examples/xhunter.toml recover-task --task-id <task-id> --retry
```

After explicitly resolving an unknown Tool outcome to `retry`, resume pending
CTF work with the same flag pattern used by the challenge:

```sh
uv run xhunter --config examples/xhunter.toml resume-ctf \
  --mission-id <mission-id> \
  --flag-pattern 'flag\{[^}]+\}'
```

Unknown outcomes are never retried automatically because the original Tool may
already have produced a side effect.

## Extensions

- Skills are inert repository-owned `skill.toml` and `SKILL.md` directories.
- Built-in Tools implement Tool API v1 and execute only through `Sandbox`.
- Repository-owned plugins register Tools and return a disposer from `start()`.
- External tools use MCP transports; arbitrary third-party Python code is not
  dynamically imported into the Host process.

`McpServerManager` discovers MCP Tool schemas, maps them to
`mcp.<server>.<tool>` capabilities, and unregisters them during teardown. The
repository includes Fake and Sandbox stdio transports. The Sandbox transport
starts the MCP server inside the configured execution plane; xhunter does not
spawn MCP server processes directly on the Host.

## Current boundaries

- Local mode is intentionally unsafe and requires an explicit environment flag.
- Docker command construction is contract-tested, but a live engine/network
  integration run still requires an available Docker host and xhunter image.
- PostgreSQL/UoW and the long-lived supervisor transport remain the next
  production-scale adapters; the local MVP uses atomic JSON repositories and a
  per-request sandbox MCP bridge.
- A real DeepSeek/OpenAI-compatible run requires `XHUNTER_MODEL_API_KEY` and
  endpoint access. Tests use deterministic fake transports and do not call a
  model service.

See `examples/skills/ctf-web-enumeration/` and `examples/plugin-echo/`.
