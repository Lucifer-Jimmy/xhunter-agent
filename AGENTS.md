# AGENTS.md — xhunter-agent

> 本文件是 AI 编码代理与人类协作者在本仓库工作的**行为准则**。
> `spec.md` 是**架构论证的来源**；本文件是**当前生效的工程决议**。
> **二者冲突时：以本文件 §2 决议表为准。** `spec.md` 的已知缺陷见 §10。

---

## 1. 项目是什么

**xhunter-agent** = 一个框架无关、模型无关、执行环境无关、存储无关的**模块化安全 Agent 平台**。

- **不是**"一个基于 LangGraph 的安全 Agent"。也**不是**"再造一个 Claude Code"。
- 第一个业务领域（Domain Pack）：**CTF 竞赛求解**。
- 使用场景：**授权环境下的安全研究与 CTF 比赛**。所有能力面向自有/授权靶场与赛题环境。
- 当前阶段：**Modular Monolith** —— 逻辑高度解耦，物理部署集中。不上微服务。

### 项目的真正价值主张

> **每一步都可审计、可门控、可恢复。**

现成的 Coding Agent CLI（Claude Code / Codex / OpenCode）最值钱的能力是**大代码库精准多文件编辑 + 长上下文管理 + 提示词工程**——这恰好是 CTF **最不需要**的。而 CTF 需要的「每个 tool call 被确定性策略门控 + 全量结构化取证 + 长任务崩溃续跑」，现成 CLI **给不了**（Codex 官方原话：tool hooks 是 *"a useful guardrail, not a complete enforcement boundary"*）。

**这就是自研 Agent Runtime 的唯一正当理由。** 不要在别的方向上跟 Claude Code 竞争。

### 命名（已裁决）

| 项 | 值 |
|---|---|
| 仓库名 / 产品名 | `xhunter-agent` |
| Python 包名 | `xhunter`（`src/xhunter/`） |
| CLI 命令 | `xhunter` |
| 环境变量前缀 | `XHUNTER_` |

> `spec.md` 全文使用 `SecAgent` / `secagent`。**阅读时按 `SecAgent` → `xhunter-agent`、`secagent.*` → `xhunter.*` 映射。** 禁止在新代码中出现 `secagent` 标识符。

### 当前仓库状态

**Greenfield。除 `spec.md` / `LICENSE` / `.gitignore` / 本文件外没有任何代码。**

---

## 2. 工程决议表（已裁决，不再讨论）

这些决议**覆盖** `spec.md` 中的相反描述。改动任一条必须先与用户确认。

| # | 决议 | 覆盖 spec.md | 理由 |
|---|---|---|---|
| **D1** | **Sandbox = Docker / OCI**。`sandbox.runtime` 留成配置（`runc` → `gVisor` → `kata`）。另实现零依赖 `LocalSandbox`（subprocess）供单测。**Firecracker 降级为「未来 Adapter」** | 技术栈表「Firecracker microVM，唯一实现」 | 一个 Mission 只 boot 一次 sandbox，Firecracker 的 125ms 冷启动优势用不上；镜像层共享（多 Kali 实例）、赛题以 Docker 镜像分发、`docker network --internal` 天然是 ScopePolicy 执行点 |
| **D2** | **arm64/x86_64 靠 `DOCKER_HOST` 解**。容器宿主永远是 Linux，位置由配置决定 | — | 开发机是 Apple Silicon，CTF pwn/reverse 是 x86_64 ELF。**换任何 sandbox 都无解**，唯一出路是宿主换机器，架构零改动 |
| **D3** | **砍掉 `WorkflowEngine` Port，换成 `CheckpointStore` Port**。Mission 主循环显式写在 `MissionService` | §9、§44、§61、§70 STEP10 | LangGraph 唯一难自研的是**持久化**，不是编排。已有 Planner+Scheduler+AgentExecutor，第四个编排概念必然职责重叠 |
| **D4** | **第一阶段只落 8 个承重 Port**：`ModelProvider` `Tool` `Sandbox` `ArtifactStore` `Repository` `EventBus` `PolicyEngine` `AgentExecutor`（+ D3 的 `CheckpointStore`）。其余写成**形状正确的普通类**（无副作用 + 构造注入） | §60「22 个核心接口」 | 单人团队一次定义 22 个 Port，前两周产出 100% 是脚手架和只有一个实现的 Contract Test。形状对了，提取 Protocol 成本近乎为零 |
| **D5** | **`ToolDispatcher` = 中间件链（waterfall 语义）**，不是硬编码直线调用 | §56 | PolicyEngine / BudgetController / Evidence / Tracing 全部变成可插拔中间件，且**deny 时短路，物理上绕不过**。见 §5 |
| **D6** | **自研 ReAct AgentExecutor 为主**（~500 行）。`ExternalCliExecutor` **只留 Port 不实现** | §25 | Agent loop 本身不难；差距在编辑工具/上下文压缩/提示词，而 CTF 大部分不需要。自研换来完整控制权 |
| **D7** | 若将来启用外部 CLI 后端 → **Codex CLI**（Apache-2.0 + Python SDK + 正式 `PreToolUse` deny 契约 + `--output-schema` + OpenAI 兼容自定义 provider） | — | 唯一同时满足「模型无关」+「强拦截」+「Python 生态」。备选 OpenCode（MIT，模型最自由） |
| **D8** | **Plugin 只支持仓库内置**（entry points / 显式注册表）。外部工具一律走 **MCP（进程隔离）**。不支持第三方任意代码热插拔 | §16–§19 隐含的开放插件模型 | 第三方 Python 代码在 Host 进程执行 = 绕过 PolicyEngine + Sandbox 整套隔离。安全平台不能有这个洞 |
| **D9** | **DeepSeek V4 作为主力 ModelProvider**（`deepseek-v4-pro` / `deepseek-v4-flash`，OpenAI 兼容端点） | §61「OpenAICompatibleAdapter」（兼容，无冲突） | SWE-Verified 80.6 ≈ Opus-4.6，但 cache-hit input 便宜 100×+、output 便宜 10–30×。CTF 一道题几十上百轮 tool call，成本是数量级差异 |
| **D10** | **不采用 DeepSeek Harness / Cordis 作为底座**，但抄它三个设计（见 §6） | — | 1 天前发布的 developer preview（明确警告 breaking changes）+ Node/TS 生态 + 底层压着 3k★ 第三方框架（DeepSeek 自己只敢 vendor 内嵌）+ **沙箱只管文件不管网络**，而 CTF 最需要出网管控 |
| **D11** | **Worker↔控制面通信：容器内 Python supervisor 反连宿主** | — | 反连使容器无需暴露端口，天然适配远程/多机，也是未来拆分布式的路径。但不引入 Go 语言栈 |
| **D12** | **第二周必须有一道真实 CTF 题端到端跑通** | §70 的 13 步顺序 | spec 的 STEP 1–4 全是脚手架，按字面执行会两周不碰真实赛题。用真题反向验证接口设计，比任何 DoD 清单有效 |
| **D13** | **执行面唯一：所有 Tool 一律在 Sandbox 内执行**，Host 进程不得成为代码执行面或靶标出网面。**门控分两层**：语义层 = `policy` 中间件（Tool 之前，fail-closed）；物理层 = Sandbox 隔离（`--network internal` / 无凭据 / 只读挂载）。**两层都必须有，不得互相替代** | §66 架构图把 Policy 单独画在 Tool→Sandbox 之间（见 §10 缺陷 8） | Sandbox 只知道「exec 了一条命令」，不知道「这条命令在打 CTF 平台本身」——物理隔离拦不住 G4 的语义策略；反过来，中间件是进程内代码，Tool 一旦在 Host 跑就有无数条绕过路径（`os.system` / 第三方库出网 / MCP 子进程）。**任何一层单独存在都不够。** 详见 §3.9 |

---

## 3. 不可违反的铁律（Hard Rules）

违反下列任何一条 = 该次改动不可合并，必须重做。

### 3.1 依赖方向

```
application  →  services  →  kernel
                    ↓            ↑
                 domains      contracts
                    ↓            ↑
                 runtime      adapters（实现 contracts，被 application 组装）
```

- `kernel/` 与 `contracts/` **不允许 import 任何外部框架**。
- `adapters/` 依赖 `contracts/`，**反向绝对禁止**。
- 任何 Domain **不得 import 另一个 Domain 的内部实现**。
- 跨模块只允许依赖 **Public API**（`__init__.py` 导出），禁止 `from x.internal.y import _z`。

### 3.2 `kernel/` 与 `contracts/` 禁止出现的 import

```
langgraph  langchain  openai  anthropic  playwright  docker  firecracker
sqlalchemy  alembic  redis  httpx  fastapi  typer  langsmith  mcp
codeql  semgrep  deepseek
```

允许：标准库、`typing`、`dataclasses`、`enum`。`contracts/` 的 DTO 允许 Pydantic v2（**仅边界，不进 kernel**）。

### 3.3 跨模块只允许传递三类数据

| 允许 | 例子 |
|---|---|
| Domain Entity | `Mission` `Task` `Evidence` `Finding` |
| DTO | `ToolRequest` `ToolResult` `ModelRequest` `ModelResponse` |
| Event | `TaskCompleted` `EvidenceCreated` `ToolCompleted` |

**禁止跨模块传递**：`SQLAlchemy Session` / ORM Entity、`Playwright Page`、Sandbox 客户端对象、Docker client、厂商 SDK 原始 Response。
DB Model → **必须经 Adapter Mapper** → Domain Entity。

### 3.4 职责边界

- **Planner** 只产出 `PlanningDecision`，**不写数据库、不执行 Tool**。副作用一律由 `PlanningService` 执行（validate → dedup → persist → emit event）。
- **LLM 模块不产生副作用**。LLM 只输出 Decision / Proposal / Hypothesis；validate / authorize / persist / dispatch 由 Application Service 负责。
- **Planner 与 Scheduler 禁止合并**。Planner 决定「做什么」，Scheduler 决定「何时执行、执行多少」。
- **Agent 不直接创建 Tool，也不直接访问 Sandbox**。必须走 `ToolDispatcher` 中间件链。
- **Tool 不在 Host 进程执行**。Tool 实现只负责「构造请求 DTO → 交给 Sandbox 执行 → 解析结果」。详见 §3.9（D13）。
- **Agent 不绑定 Tool 名称**，只声明 `required_capabilities`（如 `network.http`），由 Capability Registry 解析到具体 Tool。
- **Domain 不得绕过 PolicyEngine**。Scope / 网络 / 预算 / 风险判定必须是确定性 Policy，不能由 LLM「自己判断」。
- **Worker 不自己查数据库构造 Context**，统一走 `ContextProvider`。

### 3.5 扩展方式

> **Add, not Modify.** Open for extension, closed for modification.

- 新增 Tool = 新增一个内置 Plugin（Tool Contract + manifest + capability + 注册）。**不改 Core / Planner / Scheduler / Runtime / 任何 Domain。**
- 新增模型厂商 = 新增 `adapters/models/<vendor>/` + 改配置。**业务代码零修改。**
- 新增领域 = 新增一个 Domain Pack。**不改 Runtime。**

### 3.6 组合优于继承

禁止 `BaseAgent → WebAgent → SSRFWebAgent → SpringSSRFWebAgent` 这类继承树。
Agent = `Role + Skills + Capabilities + Policies + Context` 的**组合配置**。

### 3.7 Skill ≠ Capability

- **Skill** = 知识 / 策略 / 工作方法 / 提示（"SSRF 该怎么查"）。**没有 Runtime。**
- **Capability** = Agent 实际能做的事（"能发 HTTP 请求"）。
两者不得混淆、不得合并。

### 3.8 注册必须可逆（新增，spec 缺失）

任何注册行为（Tool schema、prompt 片段、事件监听、Capability、Adapter）**必须返回 disposer**，或由框架辅助方法自动登记。

Plugin teardown / Mission 回收 / Domain 卸载时按注册逆序释放。**"注册了但撤不掉"视为资源泄漏 bug。**

### 3.9 执行面唯一 —— 所有 Tool 在 Sandbox 内执行（D13）

**Host 进程只是控制面。它不执行赛题代码，不向靶标出网。**

#### 三条硬约束

1. **任何面向靶标的动作**（发 HTTP、跑 shell、执行 Python、读写工作区、驱动浏览器、跑 pwn 脚本）**必须由 Sandbox 执行**。
   Tool 实现 = 纯函数式的三段：`构造 SandboxRequest` → `await sandbox.exec(...)` → `解析成 ToolResult`。
   **Tool 里出现 `subprocess` / `os.system` / `httpx.get(target)` / `socket` = 该 PR 直接拒绝。**
2. **出网只有一条路**：容器网络。默认 `docker network --internal`；放行赛题目标由 PolicyEngine 生成的规则决定（G4）。
   Host 侧唯一允许的出网是**控制面出网**（LLM API、可选云 Tracer），且不得复用于 Tool。
3. **凭据不进 Sandbox**：LLM API Key / DB DSN / 云 Tracer Token 一律留在 Host。容器内 supervisor（D11）只通过反连通道收指令，不持有任何平台凭据。

#### 内置 Tool 的落地形态

| Tool | 执行位置 | 说明 |
|---|---|---|
| `shell` / `python` | Sandbox | 直接 exec |
| `http` | **Sandbox** | 由容器内 supervisor 发起请求（httpx / curl），**不在 Host 用 httpx 打靶** |
| `filesystem` | Sandbox | 工作区是容器内挂载卷 |
| `browser` | Sandbox | Playwright 跑在带浏览器的镜像里，**不在 Host 起 Chromium** |
| MCP 外部工具 | Sandbox 或独立受限容器 | D8 的进程隔离 + D13 的网络隔离，二者叠加 |

#### 例外白名单（仅此三类，新增例外必须改本文件）

允许在 Host 执行的，只有**不执行外部代码、不向靶标出网**的纯数据操作：

1. **ArtifactStore 落盘 / 读取**（内容寻址写文件，输入是已脱敏的字节流）
2. **Repository / CheckpointStore 读写**（DB，属控制面）
3. **ModelProvider 调用**（出网目标是 LLM API，不是靶标）

判定口诀：**「它会不会执行赛题给的东西？会不会连到靶标？」两个都否，才允许留在 Host。**

#### LocalSandbox 的使用边界

`LocalSandbox`（subprocess）**只允许用于单元测试与 Contract Test**。
Bootstrap 在装配真实 Mission 时若读到 `sandbox.provider=local`，**必须 fail-closed 拒绝启动**，除非同时显式设置 `XHUNTER_ALLOW_UNSAFE_LOCAL_SANDBOX=1`（该开关仅供本地调试，CI 中禁止出现）。


---

## 4. 目录结构（`src/xhunter/`）

```
kernel/         mission task agent evidence finding artifact world events
contracts/      model tool sandbox storage checkpoint artifact event_bus context policy plugin
services/       mission_ task_ planner_ verification_ context_ agent_service
orchestration/  planner/ scheduler/ dispatcher/ policies/
runtime/        agent/ tool/ plugin/ capability/
domains/        ctf/ (blackbox/ whitebox/ 暂不实现)
plugins/        builtin/{http,shell,filesystem,python,browser}/ registry.py
adapters/       models/ sandbox/ storage/ artifacts/ checkpoint/ browser/ tracing/
application/    bootstrap.py cli/ api/
tests/          unit/ contract/ integration/
examples/       plugin-echo/ domain-noop/   ← 供 CI 验证「新增不改 Core」
```

与 `spec.md` §5 的差异：
- **删除** `adapters/workflow/`（D3）
- **新增** `adapters/checkpoint/`、`adapters/tracing/`、`contracts/checkpoint.py`、`contracts/policy.py`
- **新增** `examples/`（DoD 机械化验证用，见 §11）

稳定性梯度（越靠上越不该改）：
`Contracts ██████████ > Kernel ██████████ > Runtime ████████ > Orchestration ███████ > Domains █████ > Plugins ████ > Skills ███`

组织代码时按未来 Monorepo 边界划分（`spec.md` §46），但**早期保持单 Python package**。

---

## 5. ToolDispatcher = 中间件链（D5，核心设计）

**这是全项目最重要的一个设计决策。** PolicyEngine 不是被调用的一个函数，而是链上的一环——deny 时直接 return，Tool 根本没有机会执行。

```python
# contracts/tool.py
ToolMiddleware = Callable[
    [ToolRequest, Callable[[ToolRequest], Awaitable[ToolResult]]],
    Awaitable[ToolResult],
]

# orchestration/dispatcher/chain.py
async def dispatch(req: ToolRequest, chain: Sequence[ToolMiddleware]) -> ToolResult:
    async def step(i: int, r: ToolRequest) -> ToolResult:
        if i == len(chain):
            return await _execute(r)
        return await chain[i](r, lambda nr: step(i + 1, nr))
    return await step(0, req)
```

策略中间件——**拿到决策权时短路，不调 `next`**：

```python
async def policy_mw(req, next):
    decision = await engine.authorize(req.to_action(), ctx)
    if decision.denied:
        return ToolResult.rejected(decision.reason)   # Tool 不执行
    return await next(req)
```

观察类中间件（Evidence / Tracing / Metrics）**必须 delegate**，永不短路。

**链的默认顺序**（可配置）：

```
capability_resolve → budget → policy → rate_limit → tracing → evidence_capture → [Tool → Sandbox] → artifact_spill
                              ↑ 语义层门控                                          ↑ 物理层隔离
```

**双层门控（D13，不得省略任何一层）**：

| 层 | 位置 | 拦得住什么 | 拦不住什么 |
|---|---|---|---|
| **语义层** `policy` 中间件 | Tool **之前** | 「这个 URL 是 CTF 平台本身」「flag 提交超频」「越权目标」——因为此时还看得见 capability / 参数 / 目标语义 | Tool 内部自己起进程绕过中间件 |
| **物理层** Sandbox | Tool 执行时 | 出网范围、文件范围、凭据可见性——进程级强制，代码写错也绕不过 | 语义判断。Sandbox 只看到「exec 了一条命令」 |

**terminal executor 唯一**：中间件链的链尾 `_execute(r)` **只能**把请求交给 `Sandbox` Port。链尾禁止出现任何直接 I/O。任何"顺手在 Host 跑一下"的实现视为架构违规，见 §3.9。

**规则**：
- 拦截 / 策略 → 用中间件。直接能力调用 → 用服务方法。
- 每个中间件**单一职责**，不许一个中间件干两件事。
- 中间件顺序是**公开约定**，改顺序等同于改行为，必须在 PR 描述中说明。

---

## 6. 从外部项目借鉴的三个设计（D10）

调研了 DeepSeek Harness（`deepseek-ai/deepseek-harness`，MIT，TS）及其底层 Cordis（`cordiverse/cordis`，MIT，2022 起源于 Koishi 生态）。**不采用它们作为底座，但采纳三个设计：**

| 借鉴 | 来源 | 落到本项目 |
|---|---|---|
| **waterfall 环绕中间件** | Cordis `ctx.waterfall` | → D5 / §5。"策略监听器拥有决策权时短路，观察者必须委托" |
| **事件溯源会话日志** | Harness `SessionEvent` append-only JSONL，含 `tool/call` + `tool/result` 全量载荷，可 replay | → **Evidence 捕获 + 崩溃恢复用同一套机制**。比"查库重建状态"干净得多 |
| **可逆注册（disposer）** | Cordis `ctx.effect()` | → §3.8 铁律 |

**明确不采纳的**：Cordis 的 runtime DI 容器（与 §7「不引入 DI 框架」冲突，且 TS-only 无 Python 对应物）。

---

## 7. 技术栈（第一阶段）

| 领域 | 选型 |
|---|---|
| 语言 / 包管理 | Python 3.12+ / **uv** + `pyproject.toml`（optional groups: `core` / `full`） |
| Kernel | `dataclass` + `Enum` + `typing.Protocol` |
| Contracts DTO | Pydantic v2（仅边界） |
| DI | Constructor Injection + Composition Root（**不引入 DI 框架**） |
| Agent Loop | **自研 ReAct**（D6）。`ExternalCliExecutor` 只留 Port |
| Tool 调度 | **中间件链**（D5） |
| 并发 | `asyncio.TaskGroup` + `Semaphore`（单机） |
| Model | `ModelProvider` Protocol ← OpenAI-compatible Adapter。**主力 `deepseek-v4-pro` / `-flash`**（D9） |
| Tool | `Tool` Protocol + ToolRegistry + CapabilityRegistry；外部工具经 **MCP Python SDK** 接入 |
| 内置 Tool | HTTP / Browser / Shell / Python / Filesystem —— **一律在 Sandbox 内执行**（D13 / §3.9）。httpx 与 Playwright 是**容器镜像的依赖，不是 Host 依赖** |
| **Sandbox** | `Sandbox` Protocol ← **`DockerSandbox`（唯一生产实现）**+ `LocalSandbox`（subprocess，**仅单测/Contract Test**，生产 fail-closed，见 §3.9）。`runtime` 可配 runc/gVisor/kata（D1） |
| 容器宿主 | 开发 macOS→**colima**；Pwn/Reverse→**x86_64 Linux 远程 `DOCKER_HOST`**（D2） |
| 镜像策略 | 按 Capability 分层：`base / web / pwn / re / crypto`。**不做单一巨型 Kali**。字典类只读 volume 挂载 |
| **Checkpoint** | `CheckpointStore` Protocol ← `PostgresCheckpointStore`（D3） |
| 存储 | PostgreSQL + SQLAlchemy 2.x + Alembic，Repository Protocol 隔离，**Unit-of-Work 管事务** |
| World Model | PostgreSQL + Repository（**不上 Neo4j**） |
| Artifact | Local Content-Addressed Storage + SHA-256（**不上 S3**） |
| Event Bus | In-Process Async EventBus（**不上 Kafka/NATS/Redis**） |
| Observability | `Tracer` Protocol ← **必须提供 `NoopTracer` + 本地 JSONL Tracer**；LangSmith 为可选 Adapter |
| API / CLI | FastAPI / Typer（共用 Application Service） |
| 配置 | Pydantic Settings + TOML/YAML；**Secret 走环境变量** |
| 测试 / 质量 | pytest + pytest-asyncio / **Ruff** / **Pyright** / **import-linter** / GitHub Actions |

**明确不做（当前阶段）**：Blackbox & Whitebox Domain、Semgrep、CodeQL、Tree-sitter/LSP、Neo4j、向量库、Redis、NATS/Kafka、OpenTelemetry、Web 前端、Firecracker、LangGraph。
CTF 专项工具（Sage / GDB / pwntools 等）**按真实需求逐个增加，不提前批量实现**。

> **LangSmith 注意**：CTF 现场常断网或网络受限，且 **Tool 输出含 flag 与靶机凭据**。默认必须是本地 Tracer，云端 trace 需显式开启且经脱敏（见 §9 G5）。

---

## 8. 开发顺序（覆盖 spec.md §70）

```
W1  Kernel 实体 + 8 个承重 Port + InMemory/Fake Adapter
    → 纯领域测试全绿，零外部依赖
W2  ToolDispatcher 中间件链 + PolicyEngine
    + DockerSandbox（最小版：exec / 文件 / --network internal）
    + 5 个内置 Tool（全部经 Sandbox 执行，D13）
    → ★ 第一道真实 CTF Web 题端到端跑通（D12 硬门槛）
W3  容器内 supervisor 反连（D11）+ 镜像分层 + Postgres Repository + 事件溯源会话日志
    → Evidence 捕获顺带完成
W4  CheckpointStore → 断点续跑；CTF Domain Pack 抽离
之后 Planner / Scheduler → Verifier → Benchmark
    → 需要时才接 ExternalCliExecutor（Codex）或 LangGraph checkpointer
```

**纪律**：
- **接口优先**：先在 `contracts/` 定义 Protocol，再写实现。
- **只有一个实现没问题，但必须先有接口。**
- **不要为了铺 Port 而推迟真实赛题。** 第二周跑不通真题 = 接口设计有问题，停下来重新设计。
- **DockerSandbox 从 W3 提前到 W2 是 D13 的必然推论**：D12 要求 W2 跑通真题，而真题的每一次 exec 都必须落在 Sandbox 内，不能用 `LocalSandbox` 顶替（§3.9）。W2 只做最小版，镜像分层与 supervisor 反连留在 W3。

---

## 9. 必须补齐的六个空白（spec.md 完全没写）

按「跑起来之后最先炸」排序。**实现相关模块时必须同时落地对应项。**

| ID | 空白 | 要求 | 归属 |
|---|---|---|---|
| **G1** | **预算 / 成本控制** | `BudgetController` 作为中间件；per-Mission / per-Task 的 token、金额、tool-call 次数、wall-clock 硬上限；超限 fail-closed。**LLM agent 必然死循环烧 token，这是 CTF agent 头号失败模式** | W2，中间件链 |
| **G2** | **崩溃恢复** | Task 状态机（含 `TOOL_OUTCOME_UNKNOWN`）；in-flight 任务回收；Sandbox 会话回收；lease/heartbeat。**进程一挂不能留下永远 `running` 的僵尸 Task** | W4，CheckpointStore |
| **G3** | **事务与并发边界** | Unit-of-Work：Repository 不管事务，Service 层 `async with uow:`；Session 严禁跨模块；WorldModel 并发写用乐观锁。**多 Agent 并发写是最先炸的地方** | W3，Postgres |
| **G4** | **CTF Scope / 出网策略（双层，D13）** | **语义层**：`policy` 中间件在 Tool 之前判定——赛题目标白名单、**禁打 CTF 平台本身**、flag 提交限速、越权目标拒绝，fail-closed。**物理层**：Sandbox 默认 `docker network --internal`，仅按 Policy 生成的规则放行赛题目标；Host 不为 Tool 出网。**两层缺一不可**：中间件拦语义，容器拦物理。**「授权环境」四个字必须有技术落地** | W2，PolicyEngine + DockerSandbox |
| **G5** | **Flag / 凭据脱敏** | Tool 输出 → PG / Artifact / Tracer 三条路径全部经脱敏管道；flag 值只存引用不存明文；云端 trace 默认关闭 | W3，Evidence 中间件 |
| **G6** | **EventBus 失败语义** | handler 抛异常不得拖垮 Mission；明确事件是否持久化、是否重放、handler 幂等要求 | W1，EventBus |

---

## 10. spec.md 已知缺陷（阅读时自行修正，勿照抄）

| # | 缺陷 | 处置 |
|---|---|---|
| 1 | **Docker vs Firecracker 自相矛盾**：§10/§43/§44/§61/§70/§71 写 Docker，末尾技术栈表写「Firecracker 唯一实现」 | 按 **D1**，用 Docker |
| 2 | **§47 依赖 DAG 箭头方向画反**，且未定义箭头语义 | 按本文件 §3.1 |
| 3 | **§60「22 个核心接口」漏了自己定义过的**：`SkillProvider`(§39) `WorldModel`(§32) `Tracer` `BudgetController`(§55) `AgentProfileResolver`(§26) | 按 **D4**，先落 8 个 |
| 4 | **§71 DoD 点名「暂不实现」的产品**：「ArtifactStore 可切换 Local/**S3**」但 S3 = ⏸ | 改为 Local/Memory |
| 5 | **§4 Core 禁止依赖清单不全**：缺 `langsmith` `mcp` `firecracker` `fastapi` `typer` `alembic` `deepseek` | 按本文件 §3.2 |
| 6 | Shell/Python Tool 写「必须在 Firecracker 内执行」 | 读作「必须在 Sandbox 内执行」 |
| 7 | 全文 `SecAgent` / `secagent` | 读作 `xhunter-agent` / `xhunter` |
| 8 | **§66 架构图 Policy 位置错误 + 层数不足**：Policy 被画在 `Tool → Sandbox` 之间，等价于「只有落到 Sandbox 的动作才受策略约束」。一旦某个 Tool 不经 Sandbox（Host 直发 HTTP、MCP 子进程、flag 提交），策略被完全绕过，**与 §9 G4 直接冲突** | 按 **D13** 双层门控：语义层 `policy` 中间件在 **Tool 之前**（§5）；物理层 Sandbox 作为**唯一执行面**（§3.9）。**不是二选一** |
| 9 | **§66 架构图缺三个承重组件**：`ToolDispatcher` 中间件链（D5）、`EventBus`（D4 承重 Port）、`CheckpointStore`（D3 新增）图上均无位置，连带 `BudgetController`(G1) / `evidence_capture`(G5) / `tracing` 无处安放 | 以本文件 §4 目录结构 + §5 中间件链为准 |
| 10 | **§66 Adapter 层仍列已裁掉的产品**：`LangGraph`（D3 砍掉 WorkflowEngine）、`S3`（→ Local/Memory）、`Redis`（§7 不上）、Tool 层的 `CodeQL`（§7 不做） | 按 §7 技术栈表与「明确不做」清单 |
| 11 | **§66 图中 `World` 是与 Runtime/Storage 平级的一等结构**，但 D4 的 8 个承重 Port 不含 `WorldModel` | 第一阶段 WorldModel 写成普通类（PostgreSQL + Repository），**不提前定义 Port** |

> **不要为了对齐而大改 spec.md。** 它是架构论证文档，价值在推理过程。工程决议以本文件为准。

---

## 11. 架构 Definition of Done

每次涉及架构的改动对照自检。**标注了工具的条目由 CI 机械化强制。**

### 机械可验证（CI 强制）

- [ ] Kernel / Contracts 不 import 任何外部框架 — **import-linter forbidden contract**
- [ ] 依赖方向符合 §3.1 分层 — **import-linter layers contract**
- [ ] Runtime 不直接依赖具体 Model Provider — **import-linter**
- [ ] Planner 不直接访问数据库 — **import-linter**
- [ ] Domain 不直接依赖 Adapter — **import-linter**
- [ ] Domain 之间不互相 import 内部实现 — **import-linter independence contract**
- [ ] **纯领域测试在只装 `core` 依赖组时全部通过**（无 docker / playwright / sqlalchemy / langsmith）— **uv optional group `core` 的 CI job**
- [ ] **`plugins/` 与 `runtime/tool/` 不 import `subprocess` / `httpx` / `socket` / `requests` / `playwright` / `docker`**（D13：Tool 只能经 `contracts.sandbox` 执行与出网。`adapters/models/` 的 httpx 属控制面出网，不在此约束内）— **import-linter forbidden contract**
- [ ] Ruff / Pyright 干净，**禁止 `# type: ignore` 掩盖设计问题** — CI

### 用例可验证（examples/ + CI 断言）

- [ ] **新增 Tool Plugin 不需要修改 Core** → `examples/plugin-echo/` 安装后 CI 断言 `git diff src/xhunter/{kernel,contracts,runtime,orchestration}` 为空
- [ ] **新增 Domain Pack 不需要修改 Runtime** → `examples/domain-noop/` 同上
- [ ] **删除 CTF Domain 后 Core 仍可正常启动** → CI 跑一次 `--without domain-ctf` 的 bootstrap

### 人工 Review

- [ ] Agent 不直接创建 Tool、不直接访问 Sandbox（必须走中间件链）
- [ ] **所有 Tool 的执行终点是 `Sandbox` Port**，例外仅限 §3.9 白名单三类（Artifact / Repository+Checkpoint / ModelProvider）
- [ ] **Host 侧无靶标出网**：Tool 相关代码不持有 HTTP client、不起进程、不开 socket
- [ ] Capability 与 Tool 解耦（Agent 只声明 capability）
- [ ] Repository 可切换 InMemory / PostgreSQL
- [ ] ArtifactStore 可切换 Local / Memory
- [ ] Sandbox 可切换 Local / Docker，且 **`provider=local` 在真实 Mission 下 bootstrap fail-closed**（§3.9）
- [ ] Model Provider 可替换（DeepSeek / OpenAI / Anthropic 仅改配置）
- [ ] 每个 Port 有 Contract Test，**所有 Adapter 跑同一套**
- [ ] 所有注册行为都有 disposer（§3.8）
- [ ] 新增中间件的顺序变更已在 PR 中说明

---

## 12. 测试要求

- **Contract Test 是重点**：每个 Port 一套共享测试套件（pytest ABC + fixture 参数化），**所有 Adapter 必须通过同一套**。
  `ArtifactStoreContractTest` / `ModelProviderContractTest` / `SandboxContractTest` / `RepositoryContractTest` / `CheckpointStoreContractTest`
- **Plugin CI 最少验证**：manifest 合法、API version 兼容、capability 注册成功、Tool Schema 合法、ToolResult 合法、启停正常、**disposer 生效**。
- **中间件链必须有单测**：验证 policy deny 时 Tool **确实没被调用**（而不是被调用后丢弃结果）。
- **执行面单测（D13）**：每个内置 Tool 注入一个「记录调用但不真执行」的 FakeSandbox，断言 **Tool 的所有副作用都经过 FakeSandbox**；同时断言进程内未发生 `subprocess` / 出网调用。
- **出网隔离集成测试**：`--network internal` 下访问非白名单地址必须失败；白名单目标必须可达。
- **纯领域测试必须能在未安装 Docker / Playwright / PostgreSQL SDK 的机器上全部通过。**

---

## 13. 写代码前先回答这个问题

> **如果明天我要替换它，哪些代码必须跟着修改？**

理想答案：**只改 Bootstrap / Configuration**。
如果答案是「要改 Agent / Planner / Scheduler / Core」——**模块边界设计失败，停下来重新设计。**

配套硬性要求：
- 所有具体实现只能在 `application/bootstrap.py` 组合。Core 内禁止出现任何具体 Adapter 构造。
- Adapter 选择由配置驱动（`model.provider` / `sandbox.provider` / `sandbox.runtime` / `storage.provider` / `artifacts.provider` / `checkpoint.provider` / `tracing.provider`）。
- 接口区分 Mutation 与 Query（轻量 CQRS）：`CreateTaskCommand` vs `ListPendingTasksQuery`。不必建完整 CQRS 框架。
- API 版本化：Tool API v1 / Domain API v1 / Plugin API v1。Minor 只能加兼容字段，破坏性变更升 Major。
- Plugin 初始化失败**不得导致整个平台无法启动**（除非它是该 Mission 的 mandatory dependency）。

---

## 14. 未决问题（改代码前必须确认，不要自行猜测）

| ID | 问题 | 状态 |
|---|---|---|
| **O1** | **是否有可用的 x86_64 Linux 主机**用于 Pwn/Reverse 的 `DOCKER_HOST`？有 → 直接配置；没有 → 第一阶段只做 Web/Crypto/Misc，Pwn 延后 | **待用户确认** |
| **O2** | `.gitignore` 当前是 **Node.js 模板**，与 Python + uv 项目不匹配（缺 `.venv/` `__pycache__/` `*.egg-info/` `.pytest_cache/` `.ruff_cache/`） | **待处理，可直接改** |
| **O3** | 本机容器引擎用哪个（colima / OrbStack / podman / Docker Desktop） | **待用户确认**（推荐 colima） |

遇到未决问题：**停下来问，不要选一个默认值往下写。**

---

## 15. 修改本文件的时机

改动以下任一内容，**必须同步更新本文件**：

- §2 决议表任一条
- 目录结构、承重 Port 集合、中间件链默认顺序
- 技术选型、开发顺序、DoD
- 任一铁律（§3）
- **§3.9 的执行面例外白名单**（新增任何允许在 Host 执行的东西）
- §9 六个空白的落地方案

---

## 16. spec.md 索引（按需精读，不要整篇灌入上下文）

| 主题 | 章节 |
|---|---|
| 架构目标 / 核心原则 | §1–2 |
| 依赖规则、Core 禁止依赖 | §3–4 |
| 目录结构 | §5 |
| Kernel / Contracts | §6–7 |
| 各 Port 定义（Model / Workflow⚠️D3 / Sandbox / Repository / Artifact） | §8–12 |
| Tool / ToolSpec / Capability / Plugin / Manifest / 生命周期 / 版本 | §13–19 |
| Domain Pack（含 CTF、Whitebox 复用策略） | §20–24 |
| Agent Runtime / Planner / Scheduler / Verifier / Context | §25–31 |
| WorldModel / EventBus / CQRS / ORM 隔离 / 跨模块数据 | §32–37 |
| 组合优于继承 / Skill / Capability / Policy | §38–42 |
| Bootstrap / 配置驱动 / Modular Monolith / Monorepo / 依赖 DAG⚠️缺陷2 | §43–47 |
| Public vs Internal API / Contract Test / Plugin Test / API 稳定性 | §48–51 |
| 数据结构稳定性 / LangGraph State 定位 / Blackboard 拆分 | §52–54 |
| Runtime & Tool Runtime 分层⚠️D5 | §55–56 |
| Planner 无副作用 / Command Side | §57–59 |
| 核心接口集合⚠️D4 | §60 |
| MVP 实现清单⚠️D1/D3 | §61 |
| 新增 Tool / Model / Domain 的标准流程 | §62–64 |
| 最终架构图与项目定义 | §65–67 ⚠️缺陷8–11 |
| 两条架构验收规则 | §68–69 |
| 开发顺序⚠️§8 覆盖 | §70 |
| 架构 DoD + 完整技术栈表⚠️多处覆盖 | §71 |

> ⚠️ = 该章节已被本文件 §2 决议或 §10 缺陷表覆盖，**勿照抄**。
