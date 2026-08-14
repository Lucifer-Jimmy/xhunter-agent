# SecAgent 模块化与高解耦架构规范 v0.2

## 1. 架构目标

SecAgent 必须满足以下工程目标：

1. **高度解耦**
2. **模块化**
3. **高代码复用**
4. **接口优先**
5. **实现可替换**
6. **能力可插拔**
7. **领域可扩展**
8. **框架无关**
9. **支持独立测试**
10. **支持未来拆分为分布式架构，但第一阶段保持 Modular Monolith**

最终希望做到：

```text
替换 LangGraph
        ↓
不修改 Planner / Worker / Task / Evidence

替换 Docker
        ↓
不修改 Tool Runtime / Agent Runtime

替换 PostgreSQL
        ↓
不修改业务逻辑

新增 CodeQL
        ↓
只增加一个 Tool Plugin

新增 Pwn CTF
        ↓
只增加一个 Domain Plugin

新增白盒 Java 审计
        ↓
只增加 Java Whitebox Domain Pack
```

---

# 2. 核心架构原则

系统采用：

> **Hexagonal Architecture + Ports & Adapters + Plugin Architecture + Event-Driven Communication**

总体结构：

```text
                     ┌──────────────────────┐
                     │     Application      │
                     │ CLI / API / Web      │
                     └──────────┬───────────┘
                                │
                                ▼
                ┌───────────────────────────┐
                │     SecAgent Kernel       │
                │                           │
                │ Mission                   │
                │ Task                      │
                │ Agent                     │
                │ Fact                      │
                │ Hypothesis                │
                │ Evidence                  │
                │ Finding                   │
                │ Artifact                  │
                └─────────────┬─────────────┘
                              │
                             Ports
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
   Orchestration Port   Execution Ports     Storage Ports
          │                   │                   │
          ▼                   ▼                   ▼
      LangGraph            Docker             PostgreSQL
      Adapter              Adapter            Adapter

          │
          ├────────────────────────────────────────────┐
          │                                            │
          ▼                                            ▼
   Dynamic Plugin System                         Domain Packs
          │                                            │
    ┌─────┼──────┐                        ┌────────────┼────────────┐
    ▼     ▼      ▼                        ▼            ▼            ▼
   HTTP Browser CodeQL                   CTF       Blackbox      Whitebox
```

核心原则：

> **Core 定义“系统需要什么能力”，Adapter 决定“这个能力具体怎么实现”。**

---

# 3. 最重要的依赖规则

整个项目必须严格遵循 Dependency Rule：

```text
                 Application
                     ↓
                  Services
                     ↓
                  Kernel
                     ↑
                   Ports
                     ↑
                  Adapters
```

注意 Adapter 的依赖方向：

```text
LangGraph
   ↓
WorkflowEngine Port
```

而不是：

```text
Core
 ↓
LangGraph
```

即：

```python
# 错误

from langgraph.graph import StateGraph

class MissionManager:
    ...
```

禁止。

应该：

```python
class WorkflowEngine(Protocol):

    async def run(
        self,
        mission: MissionContext,
    ) -> WorkflowResult:
        ...
```

然后：

```python
class LangGraphWorkflowEngine(WorkflowEngine):
    ...
```

---

# 4. Core 禁止依赖具体框架

以下内容禁止出现在 `core/`：

```text
langgraph
langchain
openai
anthropic
playwright
docker
sqlalchemy
redis
httpx
codeql
semgrep
```

Core 可以依赖：

```text
Python Standard Library

typing

dataclasses

必要情况下 Pydantic
```

推荐核心 Domain Entity 尽可能使用：

```python
dataclass
Enum
Protocol
```

减少框架污染。

---

# 5. 重新划分项目目录

上一版本：

```text
secagent/
├── graph/
├── tools/
├── storage/
...
```

改为：

```text
secagent/
│
├── kernel/
│
├── contracts/
│
├── services/
│
├── orchestration/
│
├── runtime/
│
├── plugins/
│
├── domains/
│
├── adapters/
│
├── application/
│
└── tests/
```

详细：

```text
src/secagent/
│
├── kernel/
│   ├── mission/
│   ├── task/
│   ├── agent/
│   ├── evidence/
│   ├── finding/
│   ├── artifact/
│   ├── world/
│   └── events/
│
├── contracts/
│   ├── model.py
│   ├── tool.py
│   ├── sandbox.py
│   ├── storage.py
│   ├── workflow.py
│   ├── artifact.py
│   ├── event_bus.py
│   ├── context.py
│   └── plugin.py
│
├── services/
│   ├── mission_service.py
│   ├── task_service.py
│   ├── planner_service.py
│   ├── verification_service.py
│   ├── context_service.py
│   └── agent_service.py
│
├── orchestration/
│   ├── planner/
│   ├── scheduler/
│   ├── dispatcher/
│   └── policies/
│
├── runtime/
│   ├── agent/
│   ├── tool/
│   ├── plugin/
│   └── capability/
│
├── domains/
│   ├── ctf/
│   ├── blackbox/
│   └── whitebox/
│
├── plugins/
│   ├── builtin/
│   │   ├── http/
│   │   ├── shell/
│   │   ├── filesystem/
│   │   ├── python/
│   │   └── browser/
│   └── registry.py
│
├── adapters/
│   ├── workflow/
│   │   └── langgraph/
│   ├── models/
│   │   ├── openai/
│   │   ├── anthropic/
│   │   └── openrouter/
│   ├── sandbox/
│   │   └── docker/
│   ├── storage/
│   │   ├── postgres/
│   │   └── memory/
│   ├── artifacts/
│   │   ├── local/
│   │   └── s3/
│   └── browser/
│       └── playwright/
│
└── application/
    ├── bootstrap.py
    ├── cli/
    └── api/
```

---

# 6. Kernel

`kernel/` 是整个项目最稳定的一层。

它只回答：

> SecAgent 世界里有什么对象？

例如：

```text
Mission
Task
Agent
Observation
Fact
Hypothesis
Evidence
Finding
Artifact
Capability
```

Kernel 不知道：

```text
LangGraph 是什么
OpenAI 是什么
Docker 是什么
PostgreSQL 是什么
Playwright 是什么
```

---

# 7. Contracts

`contracts/` 是整个系统最重要的模块之一。

所有跨模块调用必须优先通过 Contract。

Contract 不包含具体实现。

例如：

```python
from typing import Protocol


class ModelProvider(Protocol):

    async def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        ...
```

OpenAI：

```python
class OpenAIModelProvider(ModelProvider):

    async def generate(self, request):
        ...
```

Anthropic：

```python
class AnthropicModelProvider(ModelProvider):

    async def generate(self, request):
        ...
```

业务代码永远只接受：

```python
ModelProvider
```

---

# 8. Model Port

统一接口：

```python
class ModelProvider(Protocol):

    async def generate(
        self,
        request: ModelRequest,
    ) -> ModelResponse:
        ...
```

DTO：

```python
@dataclass
class ModelRequest:
    system_prompt: str
    messages: list[Message]
    tools: list[ToolSpec]
    output_schema: dict | None = None


@dataclass
class ModelResponse:
    content: str | None
    tool_calls: list[ToolCall]
    usage: Usage
    finish_reason: str
```

禁止上层代码接触：

```text
OpenAI SDK Response

Anthropic ContentBlock

Gemini SDK types
```

Adapter 必须完成转换。

---

# 9. WorkflowEngine Port

这是 v0.2 最重要的修改。

LangGraph 不再属于核心层。

定义：

```python
class WorkflowEngine(Protocol):

    async def execute(
        self,
        workflow: WorkflowDefinition,
        context: WorkflowContext,
    ) -> WorkflowResult:
        ...
```

实现：

```text
WorkflowEngine
     │
     ├── LangGraphWorkflowEngine
     │
     ├── LocalWorkflowEngine
     │
     └── FutureCustomWorkflowEngine
```

因此：

```text
SecAgent
```

不是：

```text
LangGraph Application
```

而是：

```text
LangGraph
=
SecAgent 的一个 Workflow Adapter
```

---

# 10. Sandbox Port

定义：

```python
class Sandbox(Protocol):

    async def start(self, spec: SandboxSpec) -> SandboxSession:
        ...

    async def execute(
        self,
        session_id: str,
        command: Command,
    ) -> ExecutionResult:
        ...

    async def stop(self, session_id: str) -> None:
        ...
```

Adapter：

```text
DockerSandbox
LocalSandbox       # 仅测试
FutureFirecrackerSandbox
FutureKubernetesSandbox
```

于是将来：

```text
Docker → Firecracker
```

只需要换配置：

```yaml
sandbox:
  provider: firecracker
```

Agent 完全无需修改。

---

# 11. Repository Port

不要让 Service 依赖 SQLAlchemy。

例如：

```python
class TaskRepository(Protocol):

    async def get(self, task_id: TaskId) -> Task:
        ...

    async def save(self, task: Task) -> None:
        ...

    async def list_pending(
        self,
        mission_id: MissionId,
    ) -> list[Task]:
        ...
```

然后：

```text
TaskRepository
    │
    ├── PostgresTaskRepository
    ├── MemoryTaskRepository
    └── FutureDistributedRepository
```

测试：

```python
repository = MemoryTaskRepository()
```

生产：

```python
repository = PostgresTaskRepository(...)
```

---

# 12. Artifact Store Port

```python
class ArtifactStore(Protocol):

    async def put(
        self,
        content: bytes,
        metadata: ArtifactMetadata,
    ) -> ArtifactRef:
        ...

    async def get(
        self,
        artifact_id: ArtifactId,
    ) -> bytes:
        ...
```

实现：

```text
LocalArtifactStore

S3ArtifactStore

MinIOArtifactStore
```

---

# 13. Tool 必须是插件接口

Tool 不再只是：

```python
def http_request(...):
```

而必须实现统一 Capability Contract：

```python
class Tool(Protocol):

    @property
    def spec(self) -> ToolSpec:
        ...

    async def execute(
        self,
        context: ToolContext,
        arguments: dict,
    ) -> ToolResult:
        ...
```

---

# 14. ToolSpec

```python
@dataclass
class ToolSpec:

    name: str

    version: str

    description: str

    input_schema: dict

    capabilities: set[str]

    risk_level: RiskLevel
```

HTTP：

```text
name:
    http.request

capabilities:
    network.http
```

Shell：

```text
name:
    shell.execute

capabilities:
    process.execute
```

CodeQL：

```text
name:
    codeql.query

capabilities:
    code.static_analysis
    code.taint_analysis
```

---

# 15. Capability System

Agent 不应该直接绑定 Tool 名称。

错误：

```yaml
tools:
  - curl
  - ffuf
  - sqlmap
```

推荐：

```yaml
required_capabilities:
  - network.http
  - web.discovery
```

Capability Registry 决定：

```text
network.http
     ↓
http.request

web.discovery
     ↓
ffuf.scan
```

未来替换实现：

```text
ffuf
 ↓
custom_web_discovery
```

Agent Workflow 无需改变。

---

# 16. Tool Plugin

任何第三方能力应该可以通过 Plugin 安装。

Plugin：

```python
class Plugin(Protocol):

    @property
    def manifest(self) -> PluginManifest:
        ...

    def register(
        self,
        registry: CapabilityRegistry,
    ) -> None:
        ...
```

---

# 17. Plugin Manifest

例如：

```yaml
id: secagent.tool.codeql

name: CodeQL Integration

version: 1.0.0

api_version: 1

provides:
  - code.static_analysis
  - code.taint_analysis

requires:
  - shell.execute

config_schema:
  executable:
    type: string
```

---

# 18. Plugin 生命周期

```text
discover
   ↓
validate manifest
   ↓
check API compatibility
   ↓
resolve dependencies
   ↓
initialize
   ↓
register capabilities
   ↓
ready
   ↓
shutdown
```

插件初始化失败：

```text
不得导致整个 SecAgent 无法启动
```

除非该插件属于 Mission 的 mandatory dependency。

---

# 19. Plugin API 必须版本化

定义：

```text
SecAgent Plugin API v1
```

Plugin Manifest：

```yaml
api_version: 1
```

未来破坏性修改：

```text
api_version: 2
```

Core 可以保留：

```text
v1 compatibility layer
```

避免每次升级导致所有插件全部重写。

---

# 20. Domain 也必须插件化

最重要的模块化边界：

```text
SecAgent Core

≠

CTF
```

应该：

```text
Core
 │
 ├── CTF Domain Pack
 ├── Blackbox Domain Pack
 └── Whitebox Domain Pack
```

---

# 21. Domain Pack Contract

```python
class DomainPack(Protocol):

    @property
    def manifest(self) -> DomainManifest:
        ...

    def register(
        self,
        registry: DomainRegistry,
    ) -> None:
        ...
```

一个 Domain Pack 可以提供：

```text
Workflow definitions

Planner policies

Context providers

Verification policies

Domain entities

Skills

Tool recommendations

Termination conditions
```

---

# 22. CTF Domain Pack

例如：

```text
domains/ctf/
│
├── manifest.py
│
├── workflow.py
│
├── planner.py
│
├── verifier.py
│
├── context.py
│
├── entities/
│
├── policies/
│
└── skills/
```

其职责只是定义：

```text
CTF 任务应该如何规划
CTF 世界模型增加哪些类型
如何判定 Flag
CTF Worker 应获得什么上下文
```

不重新实现：

```text
Agent Runtime
Tool Runtime
Artifact Store
Sandbox
Scheduler
Model Gateway
```

---

# 23. CTF 子领域继续模块化

未来：

```text
CTF Domain
│
├── web
├── crypto
├── pwn
├── reverse
└── misc
```

但不要定义五套 Agent Runtime。

而应：

```text
CTF Web Pack
=
Skills + Capabilities + Policies

CTF Pwn Pack
=
Skills + Capabilities + Policies
```

---

# 24. Whitebox 高度复用

未来白盒：

```text
Whitebox Domain
    │
    ├── Generic Code Analysis
    │
    ├── Java Pack
    ├── Python Pack
    ├── Go Pack
    └── JavaScript Pack
```

Generic 层处理：

```text
Repository
File
Symbol
Function
Source
Sink
DataFlow
Finding
```

Java Pack 只处理：

```text
Spring
Servlet
JVM
Maven
Gradle
CodeQL Java
Java-specific patterns
```

这样：

```text
Java
Go
Python
```

复用：

```text
Candidate pipeline
Verifier
Evidence
Finding
Artifact
Agent Runtime
Task Graph
```

---

# 25. Agent Runtime 也必须可替换

定义：

```python
class AgentExecutor(Protocol):

    async def execute(
        self,
        task: AgentTask,
        context: AgentContext,
        config: AgentConfig,
    ) -> AgentResult:
        ...
```

实现：

```text
ReActAgentExecutor

PiStyleAgentExecutor

FutureTreeSearchExecutor

FutureCodeAgentExecutor
```

Planner 不关心 Worker 内部采用：

```text
ReAct

Plan-and-Execute

Tree Search

Code Agent
```

---

# 26. Agent 与 Planner 解耦

Planner 输出：

```text
Task
```

而不是：

```text
Agent Prompt
```

Scheduler：

```text
Task
 ↓
AgentProfileResolver
 ↓
AgentSpecification
 ↓
AgentExecutor
```

因此：

```text
Planner
```

不知道：

```text
Worker 用什么模型
Worker 用什么 Agent Loop
Worker 有多少 Tool
```

---

# 27. AgentProfile

定义：

```yaml
AgentProfile:

  role:

  preferred_capabilities:

  context_policy:

  execution_policy:

  model_policy:

  budget_policy:
```

Planner 只可以指定：

```text
需求
```

Runtime 决定：

```text
怎么执行
```

---

# 28. Planner 自身也可替换

定义：

```python
class Planner(Protocol):

    async def plan(
        self,
        context: PlanningContext,
    ) -> PlanningDecision:
        ...
```

可以存在：

```text
LLMPlanner

RulePlanner

HybridPlanner

CTFPlannerDecorator
```

这样后续实验：

```text
GPT Planner

Claude Planner

Tree Search Planner
```

不影响系统其他模块。

---

# 29. Scheduler 必须独立

Planner：

```text
决定应该做什么
```

Scheduler：

```text
决定什么时候执行以及执行多少
```

两个模块禁止合并。

Scheduler 接口：

```python
class Scheduler(Protocol):

    async def schedule(
        self,
        tasks: list[Task],
        resources: ResourceState,
    ) -> SchedulingDecision:
        ...
```

以后可以替换：

```text
SimplePriorityScheduler

CostAwareScheduler

RiskAwareScheduler

DistributedScheduler
```

---

# 30. Verifier 必须独立

定义：

```python
class Verifier(Protocol):

    async def verify(
        self,
        candidate: CandidateFinding,
        context: VerificationContext,
    ) -> VerificationResult:
        ...
```

Domain 可以注册不同：

```text
CTFFlagVerifier

BlackboxVulnerabilityVerifier

WhiteboxExploitabilityVerifier
```

但统一返回：

```text
VerificationResult
```

---

# 31. Context Provider 独立

不要让 Worker 自己查询数据库构建 Context。

统一：

```python
class ContextProvider(Protocol):

    async def build(
        self,
        request: ContextRequest,
    ) -> AgentContext:
        ...
```

未来实现：

```text
RuleBasedContextProvider

GraphContextProvider

SemanticContextProvider

HybridContextProvider
```

Agent Runtime 完全不知道数据来自哪里。

---

# 32. Blackboard 本质上也是接口

不要直接写一个巨大的 Blackboard 类。

定义：

```python
class WorldModel(Protocol):

    async def add_fact(...):
        ...

    async def query_facts(...):
        ...

    async def add_hypothesis(...):
        ...

    async def get_related(...):
        ...
```

实现：

```text
RelationalWorldModel

GraphWorldModel

HybridWorldModel
```

因此以后：

```text
PostgreSQL
   ↓
Neo4j
```

不影响 Agent。

---

# 33. Event Bus

模块之间尽量避免直接互相调用。

例如 Tool 完成后：

不要：

```text
ToolRuntime
   ↓
EvidenceManager
   ↓
Logger
   ↓
Metrics
```

改为：

```text
ToolRuntime
   ↓
ToolCompletedEvent
   ↓
EventBus
   ├── ArtifactHandler
   ├── ObservabilityHandler
   ├── MetricsHandler
   └── FutureAuditHandler
```

定义：

```python
class EventBus(Protocol):

    async def publish(self, event: DomainEvent) -> None:
        ...

    def subscribe(
        self,
        event_type,
        handler,
    ) -> None:
        ...
```

---

# 34. 第一版 EventBus 不需要 Kafka

第一版：

```text
InProcessEventBus
```

即可。

未来：

```text
Redis Streams

NATS

Kafka
```

只需要 Adapter。

架构不改变。

---

# 35. 读写模型分离

推荐逐渐采用轻量 CQRS 思路。

修改状态：

```text
Command
```

查询状态：

```text
Query
```

例如：

```text
CreateTaskCommand

CompleteTaskCommand

AddEvidenceCommand
```

和：

```text
GetRelevantFactsQuery

ListPendingTasksQuery

GetMissionSummaryQuery
```

不必一开始建立完整 CQRS Framework。

但接口设计应区分：

```text
Mutation
```

和：

```text
Query
```

---

# 36. 模块之间禁止共享 ORM Entity

这是很容易踩的坑。

禁止：

```text
SQLAlchemyTask
```

一路传到：

```text
Planner
Agent
Verifier
```

必须：

```text
Database Model
     ↓ Adapter Mapper
Domain Task
```

因此：

```text
PostgreSQL implementation
```

永远不会污染：

```text
Domain
```

---

# 37. 跨模块只允许三类数据

模块之间传递：

### Domain Entity

```text
Task
Mission
Evidence
```

### DTO

```text
ToolRequest
ToolResult
ModelRequest
```

### Event

```text
TaskCompleted
EvidenceCreated
```

禁止传递：

```text
SQLAlchemy Session

Playwright Page

Docker Client

LangGraph State

OpenAI Response
```

---

# 38. Composition over Inheritance

禁止构建：

```text
BaseAgent
  ↓
WebAgent
  ↓
SSRFWebAgent
  ↓
SpringSSRFWebAgent
```

最终会形成巨大继承树。

推荐：

```text
Agent
+
Role
+
Skill
+
Capability
+
Policy
+
Context
```

组合：

```yaml
role:
  web-security-researcher

skills:
  - web
  - ssrf

capabilities:
  - network.http
  - browser.automation

policies:
  - ctf
```

---

# 39. Skill 也是模块

Skill 不应该拥有 Runtime。

Skill 是：

```text
知识
策略
工作方法
提示
工具使用建议
```

定义：

```python
class SkillProvider(Protocol):

    def get_skill(
        self,
        skill_id: str,
    ) -> Skill:
        ...
```

例如：

```text
skills/
├── web/
│   ├── endpoint-discovery
│   ├── auth-testing
│   └── request-analysis
│
├── code/
│   ├── taint-analysis
│   └── call-chain-analysis
│
└── ctf/
    ├── web-general
    └── challenge-analysis
```

Skill 可跨 Domain 复用。

---

# 40. Capability 与 Skill 必须分开

例如：

```text
Skill:
SSRF Analysis
```

描述：

```text
应该检查哪些行为
如何判断现象
如何组织测试
```

而：

```text
Capability:
network.http
```

表示：

```text
Agent 实际能够发 HTTP 请求
```

不要混淆。

---

# 41. Policy 独立模块

Policy 负责：

```text
允许什么

禁止什么

预算

Scope

Rate Limit

Concurrency

Risk Control
```

接口：

```python
class PolicyEngine(Protocol):

    async def authorize(
        self,
        action: Action,
        context: PolicyContext,
    ) -> PolicyDecision:
        ...
```

Tool Runtime：

```text
Agent
 ↓
ToolRuntime
 ↓
PolicyEngine
 ↓
execute / reject
```

---

# 42. Domain 不得绕过 Policy Engine

尤其未来 Blackbox：

```text
Agent
```

不能自己判断：

```text
“这个 IP 应该在 scope。”
```

必须：

```text
ScopePolicy
```

确定性判断。

---

# 43. Bootstrap / Dependency Injection

所有具体实现只允许在 Application Bootstrap 组合。

例如：

```python
def build_application(config):

    model = OpenAIModelAdapter(...)

    sandbox = DockerSandboxAdapter(...)

    repositories = PostgresRepositories(...)

    workflow = LangGraphWorkflowAdapter(...)

    artifacts = LocalArtifactAdapter(...)

    return SecAgentApplication(
        model=model,
        sandbox=sandbox,
        workflow=workflow,
        repositories=repositories,
        artifacts=artifacts,
    )
```

Core 里面禁止：

```python
OpenAIModelAdapter(...)
```

禁止：

```python
DockerSandbox(...)
```

---

# 44. Configuration 驱动 Adapter 选择

例如：

```yaml
workflow:
  provider: langgraph

model:
  provider: openai
  model: xxx

sandbox:
  provider: docker

storage:
  provider: postgres

artifacts:
  provider: local
```

将来：

```yaml
workflow:
  provider: custom

sandbox:
  provider: firecracker

artifacts:
  provider: s3
```

无需修改业务代码。

---

# 45. 推荐采用 Modular Monolith

第一阶段不要为了“解耦”直接上微服务。

应该：

```text
One Repository
One Deployment
Multiple Strong Modules
Stable Interfaces
```

即：

> **逻辑高度解耦，物理部署暂时集中。**

这是目前成本最低且最适合快速迭代的方案。

未来：

```text
Tool Runtime
```

如果压力大，可以独立成为 Service。

```text
Agent Runtime
```

可以成为 Worker Cluster。

```text
Artifact Store
```

可以变成 Object Storage。

由于接口已经存在，不需要重新设计 Core。

---

# 46. 推荐 Monorepo 多 Package 结构

项目进一步成熟后建议：

```text
secagent/
│
├── packages/
│   ├── secagent-kernel/
│   ├── secagent-contracts/
│   ├── secagent-runtime/
│   ├── secagent-orchestration/
│   ├── secagent-plugin-sdk/
│   │
│   ├── secagent-adapter-langgraph/
│   ├── secagent-adapter-docker/
│   ├── secagent-adapter-postgres/
│   │
│   ├── secagent-domain-ctf/
│   ├── secagent-domain-blackbox/
│   └── secagent-domain-whitebox/
│
└── apps/
    ├── secagent-cli/
    └── secagent-server/
```

早期可以保持单 Python package。

但代码结构从一开始就按照这些边界设计。

---

# 47. 依赖关系

最终依赖 DAG 应满足：

```text
              contracts
                  ▲
                  │
                kernel
                  ▲
                  │
               services
              ▲    ▲
             /      \
            /        \
      domains       runtime
         ▲             ▲
         │             │
         └──────┬──────┘
                │
            application
                ▲
                │
             adapters
```

更准确地说：

Adapter：

```text
implements Contracts
```

Domain：

```text
depends on Kernel + Contracts
```

Application：

```text
负责组合所有模块
```

任何 Domain：

```text
不得 import 另一个 Domain 的内部实现。
```

---

# 48. Public API 与 Internal API

每个模块必须明确：

```text
public/
internal/
```

或者通过 Python `__init__.py` 控制导出。

例如：

```text
secagent.runtime
```

允许：

```python
from secagent.runtime import AgentExecutor
```

禁止：

```python
from secagent.runtime.internal.react.loop import _run_step
```

跨模块只能依赖 Public API。

---

# 49. Contract Tests

每一个 Adapter 必须通过同一套 Contract Test。

例如所有 ArtifactStore：

```text
LocalArtifactStore
S3ArtifactStore
MemoryArtifactStore
```

必须通过：

```text
ArtifactStoreContractTest
```

验证：

```text
put
get
missing artifact
metadata
error behavior
```

同理：

```text
ModelProviderContractTest

SandboxContractTest

RepositoryContractTest

WorkflowEngineContractTest
```

---

# 50. Plugin Contract Tests

每个 Plugin CI 至少验证：

```text
Manifest 合法

API Version 兼容

Capability 注册成功

Tool Schema 合法

ToolResult 合法

启动/关闭正常
```

---

# 51. API Stability

接口按：

```text
major.minor
```

管理。

例如：

```text
Tool API v1

Domain API v1

Plugin API v1
```

原则：

Minor：

```text
只能添加兼容字段。
```

Major：

```text
允许破坏性修改。
```

---

# 52. 数据结构优先稳定

整个系统真正应该长期稳定的不是：

```text
Agent Prompt
```

也不是：

```text
LangGraph Node
```

而是：

```text
Mission
Task
Observation
Fact
Hypothesis
Evidence
Finding
Artifact
ToolResult
```

这些属于：

> SecAgent Core Language。

---

# 53. 不要让 LangGraph State 成为领域模型

错误：

```python
class SecurityGraphState(TypedDict):
    findings: ...
    http_sessions: ...
    tasks: ...
    ...
```

然后所有业务直接依赖这个 State。

正确：

```text
LangGraph State
```

只是：

```text
Domain Model
```

的 orchestration projection。

例如：

```python
class LangGraphState(TypedDict):

    mission_id: str

    pending_task_ids: list[str]

    active_task_ids: list[str]

    recent_event_ids: list[str]
```

真正数据：

```text
Repository / WorldModel
```

保存。

这样换掉 LangGraph 不会丢掉系统架构。

---

# 54. Blackboard 也不要变成 God Object

不要：

```python
blackboard.do_everything()
```

推荐拆成：

```text
FactStore

HypothesisStore

EvidenceStore

FindingStore

WorldQueryService
```

Blackboard 只是逻辑概念。

---

# 55. Runtime 分层

Agent Runtime 内部建议：

```text
AgentExecutor
     │
     ▼
AgentLoop
     │
     ├── ModelProvider
     │
     ├── ContextProvider
     │
     ├── ToolDispatcher
     │
     └── BudgetController
```

这些模块全部通过接口连接。

---

# 56. Tool Runtime 分层

```text
ToolDispatcher
      ↓
CapabilityResolver
      ↓
PolicyEngine
      ↓
Tool
      ↓
Sandbox
      ↓
ResultProcessor
      ↓
ArtifactStore
```

每层都可以独立测试。

---

# 57. Planner 不直接操作数据库

流程：

```text
Planner
    ↓
PlanningContext
    ↓
PlanningDecision
    ↓
PlanningService
    ↓
TaskRepository
```

Planner 只做智能决策。

Service 负责产生真实副作用。

这可以避免 LLM 模块污染核心事务逻辑。

---

# 58. LLM 模块原则上不产生副作用

LLM 输出：

```text
Decision
Proposal
Hypothesis
TaskProposal
```

Application Service：

```text
validate
authorize
persist
dispatch
```

因此：

```text
LLM
```

永远不是：

```text
数据库事务管理器
任务调度器
安全策略执行器
```

---

# 59. Command Side

例如 Planner 返回：

```python
PlanningDecision(
    create_tasks=[...]
)
```

由：

```text
PlanningService
```

负责：

```text
validate
deduplicate
store
emit event
```

这样 Planner 可以随意替换。

---

# 60. 推荐的核心接口集合

第一版优先稳定以下接口：

```text
ModelProvider

WorkflowEngine

Planner

Scheduler

AgentExecutor

ContextProvider

Tool

ToolRegistry

CapabilityRegistry

Sandbox

PolicyEngine

ArtifactStore

EventBus

MissionRepository

TaskRepository

FactRepository

HypothesisRepository

EvidenceRepository

FindingRepository

Verifier

DomainPack

Plugin
```

不要一次定义 100 个接口。

从这批核心接口开始。

---

# 61. MVP 中的具体实现

v0.1：

```text
ModelProvider
    └── OpenAICompatibleAdapter

WorkflowEngine
    └── LangGraphAdapter

AgentExecutor
    └── ReActAgentExecutor

Sandbox
    └── DockerSandbox

ArtifactStore
    └── LocalArtifactStore

Repository
    └── PostgresRepository

EventBus
    └── InProcessEventBus

ContextProvider
    └── RuleBasedContextProvider

Scheduler
    └── PriorityScheduler

Planner
    └── LLMPlanner
```

重点：

> **只有一个实现没有问题，但必须先有接口。**

---

# 62. 新增一个 Tool 的理想过程

例如未来增加：

```text
Semgrep
```

开发者只需要：

```text
1. 新建 plugin
2. 实现 Tool Contract
3. 定义 manifest
4. 声明 capability
5. 注册 plugin
```

无需修改：

```text
Planner

Agent Runtime

Scheduler

LangGraph Workflow

CTF Domain

Blackbox Domain

Whitebox Domain
```

---

# 63. 新增一个模型 Provider

增加 Gemini：

```text
adapters/models/gemini/
```

实现：

```text
ModelProvider
```

配置：

```yaml
model:
  provider: gemini
```

完成。

业务代码零修改。

---

# 64. 新增白盒 Java Domain

只需要：

```text
domains/whitebox/java/
```

注册：

```text
Java Project Analyzer

Java Skills

Java Source/Sink Rules

Java Context Provider Extension

Java Candidate Generator
```

复用：

```text
Task

Agent Runtime

Scheduler

Evidence

Verifier Pipeline

Artifact

Tool Runtime
```

---

# 65. 模块化设计最终达到的效果

理想情况下：

```text
Core Kernel
```

应该极少变化。

变化最多的是：

```text
Plugins
Domains
Skills
Adapters
Policies
```

稳定程度：

```text
Contracts       ██████████

Kernel          ██████████

Runtime         ████████

Orchestration   ███████

Domains         █████

Plugins         ████

Skills          ███
```

越靠上层，越允许快速迭代。

---

# 66. 最终核心架构

```text
                        Application
                            │
                            ▼
                    Mission Service
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
          Planner       Scheduler      Verifier
              │             │             │
              └─────────────┼─────────────┘
                            │
                        Contracts
                            │
                ┌───────────┼───────────┐
                │           │           │
                ▼           ▼           ▼
             Runtime      World       Storage
                │
                ▼
            AgentExecutor
                │
      ┌─────────┼──────────┐
      ▼         ▼          ▼
    Model     Context      Tools
                           │
                      Capability
                       Registry
                           │
                ┌──────────┼──────────┐
                ▼          ▼          ▼
              HTTP       Browser    CodeQL
                │          │          │
                └──────────┼──────────┘
                           ▼
                         Policy
                           │
                           ▼
                        Sandbox
```

外围：

```text
          Domain Plugin System

      ┌──────────┼───────────┐
      ▼          ▼           ▼
     CTF      Blackbox    Whitebox
```

底层 Adapter：

```text
         Adapter Layer

LangGraph
OpenAI
Anthropic
Docker
Playwright
PostgreSQL
S3
Redis
...
```

---

# 67. 项目最终定义

SecAgent 不应该是：

```text
一个基于 LangGraph 的安全 Agent
```

而应该是：

> **一个框架无关、模型无关、执行环境无关、存储无关，通过稳定 Contracts 将 Planner、Agent、Tool、Workflow、Domain 和 Infrastructure 组合起来的模块化安全 Agent Platform。**

LangGraph 只是：

```text
Workflow Adapter
```

Pi-style Loop 只是：

```text
AgentExecutor Implementation
```

Docker 只是：

```text
Sandbox Adapter
```

Playwright 只是：

```text
Browser Capability Provider
```

PostgreSQL 只是：

```text
Repository Adapter
```

CTF / Blackbox / Whitebox 是：

```text
Domain Packs
```

HTTP / CodeQL / Semgrep / GDB / Sage 是：

```text
Capability Plugins
```

这才是整个项目应该长期稳定下来的架构边界。

---

# 68. 第一条架构验收规则

以后开发任何模块之前，都先问：

> **如果明天我要替换它，哪些代码必须跟着修改？**

理想结果：

```text
替换 Implementation
        ↓
只修改 Bootstrap / Configuration
```

如果发现：

```text
替换 Docker
↓
需要修改 Agent

替换 LangGraph
↓
需要修改 Planner

增加 CodeQL
↓
需要修改 Core

增加 CTF Pwn
↓
需要修改 Scheduler
```

说明模块边界设计失败。

---

# 69. 第二条架构验收规则

新增业务能力时：

> **应该尽可能是 Add，而不是 Modify。**

例如：

```text
Add:
    secagent-plugin-codeql

而不是：

Modify:
    core
    runtime
    planner
    scheduler
    graph
```

核心遵循：

> Open for extension, closed for modification.

---

# 70. 第一阶段实际开发顺序调整

新的顺序应该是：

```text
STEP 1
Kernel Domain Models
        ↓
STEP 2
Contracts
        ↓
STEP 3
In-Memory Adapters
        ↓
STEP 4
Application Services
        ↓
STEP 5
Tool Runtime
        ↓
STEP 6
Agent Runtime
        ↓
STEP 7
Docker / PostgreSQL Adapters
        ↓
STEP 8
CTF Domain Pack
        ↓
STEP 9
Planner / Scheduler
        ↓
STEP 10
LangGraph Adapter
        ↓
STEP 11
Dynamic Agents
        ↓
STEP 12
Verifier
        ↓
STEP 13
Benchmark
```

这里有一个很重要的变化：

> **不要第一天就引入 LangGraph。**

先使用：

```text
InMemoryRepository

LocalWorkflowEngine

FakeModelProvider

FakeSandbox
```

把 Contracts 和 Core 跑通。

之后 LangGraph 作为 Adapter 接进来。

如果接 LangGraph 时发现需要大幅修改 Core：

> 说明接口设计有问题。

---

# 71. v0.2 架构 Definition of Done

架构层必须通过以下测试：

- [ ] Kernel 不 import LangGraph。
- [ ] Kernel 不 import OpenAI SDK。
- [ ] Kernel 不 import Docker。
- [ ] Kernel 不 import SQLAlchemy。
- [ ] Runtime 不直接依赖具体 Model Provider。
- [ ] Planner 不直接访问数据库。
- [ ] Agent 不直接创建 Tool。
- [ ] Agent 不直接访问 Sandbox。
- [ ] Domain 不直接依赖 Adapter。
- [ ] Tool 必须通过 Plugin / Registry 注册。
- [ ] Capability 与 Tool 解耦。
- [ ] Repository 可切换 InMemory/PostgreSQL。
- [ ] ArtifactStore 可切换 Local/S3。
- [ ] Sandbox 可切换 Fake/Docker。
- [ ] Model Provider 可替换。
- [ ] Workflow Engine 可替换。
- [ ] 所有 Adapter 有 Contract Test。
- [ ] CTF 可以作为独立 Domain Pack 加载。
- [ ] 删除 CTF Domain 后 Core 仍可正常启动。
- [ ] 新增 Tool Plugin 不需要修改 Core。
- [ ] 新增 Domain Pack 不需要修改 Runtime。
- [ ] LangGraph 被移除后 Core 单元测试仍全部通过。

最后这一条非常重要：

> **SecAgent Core 必须可以在完全没有安装 LangGraph、Docker、Playwright、PostgreSQL SDK 的情况下运行其全部纯领域测试。**

|层 / 模块|第一阶段技术栈 / 组件|状态|核心职责|设计约束|
|---|---|--:|---|---|
|**主开发语言**|**Python 3.12+**|✅ 实现|Core、Agent Runtime、Workflow、Tool、API|整体尽量统一 Python|
|**项目管理**|**uv + `pyproject.toml`**|✅ 实现|依赖、虚拟环境、Workspace|为后续 Monorepo 预留|
|**Kernel**|`dataclasses` + `Enum` + `typing.Protocol`|✅ 实现|Mission、Task、Agent、Evidence、Finding 等核心领域对象|不依赖 LangGraph、LangSmith、Firecracker 等具体实现|
|**Contracts / DTO**|**Pydantic v2**|✅ 实现|Model、Tool、Planner 等模块边界 Schema|只用于边界，不侵入 Kernel|
|**依赖注入**|Constructor Injection + Composition Root|✅ 实现|Adapter、Runtime、Service 组装|暂不引入 DI Framework|
|**Workflow Contract**|自定义 `WorkflowEngine Protocol`|✅ 实现|抽象工作流编排能力|Core 不直接依赖 LangGraph|
|**Workflow Adapter**|**LangGraph v1**|✅ 实现|Planner → Task → Agent → Verify → Replan 工作流、状态机、分支等；LangGraph 当前定位就是低层、有状态 Agent orchestration runtime。([Docs by LangChain](https://docs.langchain.com/oss/python/langgraph/overview?utm_source=chatgpt.com "LangGraph overview - Docs by LangChain"))|只作为 Adapter|
|**Agent Executor Contract**|自定义 `AgentExecutor Protocol`|✅ 实现|抽象 Agent 执行方式|Workflow 不感知 Agent Loop 细节|
|**Agent Runtime**|**自研 Pi-style / ReAct Agent Loop**|✅ 实现|Model → Tool → Observation → Model 自主循环|保持轻量，不额外引入大型 Agent Framework|
|**Multi-Agent 调度**|`asyncio.TaskGroup` + `Semaphore`|✅ 实现|Dynamic Agent 并发执行|第一阶段只做单机异步并发|
|**Planner**|自定义 `Planner Protocol` + LLM Planner|✅ 实现|分析状态、产生 Hypothesis、创建 Task|Planner 只产生 Decision，不直接执行 Tool|
|**Scheduler**|自定义 Priority Scheduler|✅ 实现|Task 优先级、依赖、并发资源管理|与 Planner 分离|
|**Model Contract**|自定义 `ModelProvider Protocol`|✅ 实现|屏蔽模型厂商差异|Agent 不直接调用厂商 SDK|
|**Model Adapter**|**OpenAI-compatible Adapter**|✅ 第一版|LLM 调用|后续再按需要增加其他 Provider|
|**Tool Contract**|自定义 `Tool Protocol`|✅ 实现|统一 Tool 输入、输出、Schema|所有工具必须符合统一 Contract|
|**Tool Registry**|自定义 `ToolRegistry`|✅ 实现|Tool 注册、查询和管理|不需要复杂 Service Discovery|
|**Capability Registry**|简单 Capability → Tool 映射|✅ 实现|Agent 能力与具体工具解耦|第一版使用简单 Registry|
|**MCP Adapter**|**官方 MCP Python SDK**|✅ 实现|将外部 MCP Server 的 Tool 接入 SecAgent；官方 Python SDK 当前稳定线支持构建 MCP Client/Server。([MCP Python SDK](https://py.sdk.modelcontextprotocol.io/?utm_source=chatgpt.com "MCP Python SDK"))|MCP 是外部协议，不作为 SecAgent 内部 Tool Contract|
|**HTTP Tool**|**httpx AsyncClient**|✅ Tool|原始 HTTP Request / Response、Cookie、Header|Web 通用基础能力|
|**Browser Tool**|**Playwright Python + Chromium**|✅ Tool|DOM、JavaScript、Cookie、页面交互|封装成 Tool，不暴露 Playwright 对象|
|**Shell Tool**|自定义 Shell Tool|✅ Tool|命令执行|所有命令必须在 Firecracker microVM 内执行|
|**Python Tool**|Python Runtime Tool|✅ Tool|Python 脚本、数据处理、临时代码执行|在 Firecracker 内执行|
|**Filesystem Tool**|自定义 File Tool|✅ Tool|读取、写入、搜索 Workspace 文件|限制在 Mission Workspace|
|**Artifact Tool**|`read_artifact / write_artifact`|✅ Tool|大型结果、文件、HTTP Body、日志等访问|避免大文本长期进入 Agent Context|
|**Sandbox Contract**|自定义 `Sandbox Protocol`|✅ 实现|microVM 生命周期、Command Execution、Workspace|Agent 不直接操作 Firecracker|
|**Sandbox**|**Firecracker microVM**|✅ 唯一实现|Agent Tool、Shell、不可信代码隔离执行|Firecracker 基于 KVM 创建 microVM，运行 Host 需 Linux + KVM，支持 x86_64/aarch64 Linux。([GitHub](https://github.com/firecracker-microvm/firecracker/blob/main/docs/getting-started.md?utm_source=chatgpt.com "firecracker/docs/getting-started.md at main"))|
|**Firecracker Manager**|自研 Python Firecracker Adapter|✅ 实现|创建、启动、停止、回收 microVM|封装 Firecracker API，不泄露给上层|
|**Guest OS**|Minimal Linux RootFS|✅ 实现|Agent 实际命令执行环境|维护统一基础镜像|
|**Workspace**|Host Workspace + microVM 映射/同步层|✅ 实现|Mission 文件、脚本、下载结果保存|每个 Mission 独立|
|**Policy Engine**|自定义轻量 `PolicyEngine`|✅ 基础实现|Tool 权限、网络访问、预算、风险控制|只做基础 Policy，复杂 Scope Policy 后置|
|**数据库**|**PostgreSQL**|✅ 实现|Mission、Task、Agent、Fact、Hypothesis、Evidence、Finding|第一阶段只使用一个主数据库|
|**ORM**|**SQLAlchemy 2.x**|✅ 实现|PostgreSQL Adapter|ORM Entity 不进入 Domain|
|**Migration**|**Alembic**|✅ 实现|数据库 Migration|随 Schema 演进|
|**Repository Contract**|自定义 Repository Protocol|✅ 实现|隔离业务层与 PostgreSQL|Service 只依赖接口|
|**World Model / Blackboard**|PostgreSQL + Repository|✅ 实现|Fact、Hypothesis、Evidence、Finding 共享状态|第一阶段不上 Neo4j|
|**Evidence Graph**|PostgreSQL 关系表|✅ 基础实现|Finding ↔ Evidence ↔ Hypothesis 关系|不单独引入 Graph DB|
|**Artifact Store Contract**|自定义 `ArtifactStore Protocol`|✅ 实现|文件与大型输出存储接口|与业务层解耦|
|**Artifact Store**|**Local Content-Addressed Storage + SHA-256**|✅ 第一版|HTTP Body、Tool Output、脚本、截图、附件|暂不上 S3 / MinIO|
|**Event Bus**|In-Process Async EventBus|✅ 基础实现|Task、Agent、Tool、Evidence 生命周期事件|暂不上 Kafka / NATS / Redis Queue|
|**Context Provider**|自定义 Rule-based Context Builder|✅ 实现|从 World Model / Artifact 构造 Agent Context|第一版不做复杂 RAG|
|**Context Compression**|LLM Summary + Structured Facts|✅ 基础实现|控制长任务 Context 长度|Fact / Evidence 不依赖 Conversation 保存|
|**Agent Observability Contract**|自定义 `Observability / Tracer Protocol`|✅ 实现|隔离业务代码与具体监控产品|Runtime 不直接绑定 LangSmith|
|**Agent Observability Adapter**|**LangSmith**|✅ 唯一实现|Agent、Model、Tool、Workflow trace、调试与运行监控；LangSmith 原生支持 LangGraph tracing，并可跟踪完整 Agent 调用链。([Docs by LangChain](https://docs.langchain.com/langsmith/trace-with-langgraph?utm_source=chatgpt.com "Trace LangGraph applications - Docs by LangChain"))|通过 `LangSmithAdapter` 接入|
|**LangSmith Trace 粒度**|Mission → Planner → Task → Agent → Model → Tool → Verifier|✅ 实现|定位 Agent 决策、失败、延迟、Token/成本|保留 Mission / Task / Agent metadata|
|**Application Service**|自定义 Service Layer|✅ 实现|Mission 管理、Task 管理、Agent 生命周期|API / CLI 共用|
|**API**|**FastAPI**|✅ 实现|Mission、Task、Agent、Artifact API|API 层不直接操作 Adapter|
|**CLI**|**Typer**|✅ 实现|本地运行、Debug、Mission 管理|共用 Application Service|
|**Configuration**|Pydantic Settings + TOML/YAML|✅ 实现|Model、Firecracker、LangSmith 等配置|Secret 使用环境变量|
|**测试**|**pytest + pytest-asyncio**|✅ 实现|Unit、Contract、Integration|Contract Test 为重点|
|**Lint / Format**|**Ruff**|✅ 实现|Lint + Formatting|CI 强制|
|**Type Check**|**Pyright**|✅ 实现|强类型检查|Contracts / Protocol 重点检查|
|**CI**|GitHub Actions|✅ 基础实现|Ruff、Pyright、pytest、dependency rule|防止模块重新耦合|
|**CTF Domain Pack**|自定义 CTF Domain|✅ 第一业务 Domain|定义 CTF Workflow、Flag、Context、Planner Policy|复用全部 Core Runtime|
|**CTF 专项 Tool**|按真实需求逐步增加|🟡 按需|例如后续增加 Sage、GDB、pwntools 等|**不提前批量实现**|
|**Blackbox Domain**|—|⏸ 暂不实现|黑盒 SRC / 渗透测试|Core 稳定后再开发|
|**Whitebox Domain**|—|⏸ 暂不实现|白盒代码审计|Core 稳定后再开发|
|**Semgrep / SAST**|—|⏸ 暂不实现|白盒 Candidate Generation|当前阶段删除|
|**CodeQL**|—|⏸ 暂不实现|白盒 Dataflow / Taint|当前阶段删除|
|**Tree-sitter / LSP**|—|⏸ 暂不实现|代码结构与 Symbol Analysis|当前阶段删除|
|**Neo4j**|—|⏸ 暂不实现|大规模 Graph Query|当前 PostgreSQL 足够|
|**Vector Database**|—|⏸ 暂不实现|Semantic Retrieval|当前阶段不需要|
|**Redis**|—|⏸ 暂不实现|Cache / Queue|当前阶段不需要|
|**NATS / Kafka**|—|⏸ 暂不实现|分布式 Agent Worker|当前阶段不需要|
|**OpenTelemetry**|—|⏸ 暂不实现|通用 Observability|当前统一使用 LangSmith|
|**Web 前端**|—|⏸ 暂不实现|Dashboard / Graph UI|CLI + API 稳定后再做|