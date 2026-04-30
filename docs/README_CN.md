# 🐝 AgentSwarm

> An open-source, full-stack multi-agent operating system bridging infrastructure-level container orchestration with high-level business logic, natively optimized for Hermes.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Docker Swarm](https://img.shields.io/badge/Docker_Swarm-Ready-2496ED.svg?logo=docker)](https://docs.docker.com/engine/swarm/)
[![Hermes MCP](https://img.shields.io/badge/Hermes-MCP_Native-FF4B4B.svg)]()

AgentSwarm 是一个企业级多智能体协同操作系统。它将 **“组织级业务目标拆解”** 与 **“底层物理计算资源隔离”** 完美融合。基于 FastAPI、MongoDB 和 Docker Swarm 构建，原生深度支持 Hermes 大模型。

## ✨ 核心特性 (Key Features)

* **物理级沙箱隔离 (Container-Level Isolation)**：基于 Docker Swarm 动态分配 Agent 运行环境。每个 Agent 拥有独立的文件卷、网络边界与依赖环境，彻底告别“逻辑隔离”带来的跨域污染。
* **纯 AI 动态编排 (Auto-Orchestration)**：内置全局调度 Agent。告别静态 YAML 连线，系统可根据宏观目标（Goal）动态拆解任务（Issue），并实时申请拉起全新的 Worker 容器。
* **严格流水线与逆流回滚 (Strict Pipeline & Rollback)**：采用独占式沙箱访问权与增量快照机制。当逻辑审查 Agent 驳回内容时，系统自动物理回滚沙箱，并向生成 Agent 强行注入 `[CRITICAL FEEDBACK]`，有效打破 AI 幻觉死循环。
* **时停与人工接管 (Human-in-the-Loop)**：通过 FastAPI API 网关拦截关键资源调用（如修改底层核心规则、拉起大量容器）。触发挂起状态（Suspend），等待人类管理员在可视化控制台中审批或驳回。
* **声明式技能扩展 (Skill Registry)**：通过 Pydantic 与 `@AgentSkill` 装饰器，一键将 Python 函数转换为 Hermes 支持的 MCP 工具，支持容器拉起时的热挂载。

---

## 🏗️ 架构概览 (Architecture Overview)

AgentSwarm 采用“控制面-数据面”相分离的三层架构：

1. **交互与观测平面 (Dashboard)**：基于 React Flow 和 Monaco Editor，提供动态节点拓扑、实时文件沙箱视图与全局工具调用审计流。
2. **控制平面 (FastAPI + MongoDB)**：充当系统大脑。接管中心化 LLM 网关计费，维护目标状态机，执行沙箱快照以及处理 Docker Swarm 的 API 调度。
3. **执行平面 (Docker Swarm Workers)**：按需拉起的 Hermes 封装容器，通过挂载 Project Workspace 共享项目白板。

---

## 🚀 快速开始 (Quick Start)

### 1. 环境准备
确保你的机器（或集群）已安装 Python 3.10+ 并启用了 Docker Swarm 模式：
```bash
docker swarm init
```

### 2. 本地一键部署
克隆仓库并使用内置的 compose 文件拉起控制平面（包含 FastAPI 网关、MongoDB 和初始化的注册中心）：
```bash
git clone [https://github.com/your-org/agentswarm.git](https://github.com/your-org/agentswarm.git)
cd agentswarm
cp .env.example .env  # 填入你的基础模型 API Key
docker compose up -d
```
控制台默认运行在 `http://localhost:3000`，API 网关运行在 `http://localhost:8000`。

---

## 🧩 核心概念与用例：构建“故事工厂”

AgentSwarm 原生非常适合处理长生命周期、强逻辑依赖的复杂协作项目（如：AI 互动小说生成、大型代码库重构）。

以系统内置的**“互动小说故事工厂 (Story Factory)”**模板为例，演示如何定义并运行一个动态生成《星际农业大亨》小说世界观的任务流：

### 编写一个带审批流的自定义技能 (Skill)
在 `skills/world_building/rules.py` 中，你可以使用声明式语法定义 Agent 的能力：

```python
from pydantic import BaseModel, Field
from agentswarm import AgentSkill, WorkspaceContext

class UpdateSystemRuleInput(BaseModel):
    target_character: str = Field(..., description="目标角色")
    surface_reward: str = Field(..., description="表面奖励设定")
    hidden_trap: str = Field(..., description="隐藏的打工陷阱逻辑")

@AgentSkill(
    name="update_system_rule_with_trap",
    description="以巧妙的方法、最小的修改更新世界观系统规则。",
    require_human_approval=True,  # ⚠️ 触及核心设定，必须挂起等待人类审批
    execution_environment="sandbox"
)
def update_system_rule_with_trap(input_data: UpdateSystemRuleInput, context: WorkspaceContext):
    # 底层沙箱执行逻辑
    file_path = context.get_sandbox_path("world_settings.json")
    # ... JSON 读写与替换逻辑 ...
    return {"status": "success"}
```

### 发起动态编排
在 Web 控制台或通过 CLI 向全局 Agent 发送指令：
```text
> 目标：构建“星际农业大亨”第一卷的详细设定集。要求经济体系必须自洽，且包含完善的互动规则陷阱。
```
全局 Agent 将自动生成 Issue，拉起“星际架构师”、“数值精算师”等 Worker 容器，并在必要时挂起进程等待你的确认。

---

## 🗺️ 演进路线 (Roadmap)

- [ ] **v0.1 (Current)**: 核心基建。FastAPI 网关与单节点 Swarm 调度，跑通基础流水线与 Pydantic 技能解析。
- [ ] **v0.2**: The Orchestration Update。引入跨节点的动态 Swarm 容器拉起、快照回滚机制与事件驱动流转。
- [ ] **v0.3**: The Paperclip Update。发布完整的 Web 控制台，包含动态拓扑图、人工审批流（HITL）面板与内置的 Skill Hub。

## 🤝 贡献指南 (Contributing)
AgentSwarm 处于早期极速迭代阶段。欢迎提交 Issue 讨论架构，或通过 PR 贡献新的优质 Skillpack（尤其是逻辑审查与代码校验方向）。详情请参阅 `CONTRIBUTING.md`。

## 📄 许可证 (License)
本项目采用 [GNU Affero General Public License v3.0](../LICENSE) 开源协议。
