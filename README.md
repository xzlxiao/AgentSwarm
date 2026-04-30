# AgentSwarm

> An open-source, full-stack multi-agent operating system bridging infrastructure-level container orchestration with high-level business logic, natively optimized for Hermes.

[![License](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker)](https://docs.docker.com/compose/)

AgentSwarm is an enterprise-grade multi-agent orchestration system. It combines **organizational-level business goal decomposition** with **low-level physical compute resource isolation**. Built on FastAPI, MongoDB, and Docker, with native deep integration for the Hermes LLM.

**[中文文档](docs/README_CN.md)** | **[架构白皮书](docs/架构白皮书.md)** | **[项目指南](docs/项目指南.md)** | **[里程碑路线图](docs/里程碑路线图.md)**

## Key Features

- **Container-Level Isolation**: Dynamically provision per-agent runtime environments via Docker. Each agent gets its own volume, network boundary, and dependency stack — no logical isolation loopholes.
- **AI-Driven Orchestration**: Built-in global scheduling agent. No static YAML wiring — the system decomposes high-level goals into tasks and spins up worker containers on demand.
- **Strict Pipeline & Rollback**: Exclusive sandbox access with incremental snapshots. When a review agent rejects content, the system physically rolls back the sandbox and injects `[CRITICAL FEEDBACK]`, breaking AI hallucination loops.
- **Human-in-the-Loop**: The FastAPI gateway intercepts critical operations (e.g., modifying core rules, spawning many containers), triggering a suspended state for admin approval.
- **Declarative Skill Extension**: Via Pydantic and `@AgentSkill` decorators, turn Python functions into Hermes-compatible MCP tools with hot-mounting support.

## Architecture

AgentSwarm uses a three-layer control-plane / data-plane architecture:

1. **Dashboard Plane**: React Flow + Monaco Editor — dynamic node topology, real-time sandbox file viewer, and global tool-call audit stream.
2. **Control Plane** (FastAPI + MongoDB): System brain — centralized LLM gateway billing, goal state machine, sandbox snapshots, and Docker API scheduling.
3. **Execution Plane** (Docker Workers): On-demand Hermes worker containers with mounted project workspace volumes.

## Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose

### Deploy

```bash
git clone https://github.com/your-org/agentswarm.git
cd agentswarm
cp .env.example .env   # fill in your LLM API key
docker compose up -d
```

The API gateway runs at `http://localhost:8000`. Verify with:

```bash
curl http://localhost:8000/health
```

## API Endpoints

| Path | Description |
|------|-------------|
| `GET /health` | Health check |
| `/api/v1/workspaces` | Workspace management |
| `/api/v1/agents` | Agent registration & lifecycle |
| `/api/v1/gateway` | LLM proxy & token tracking |

## Roadmap

- [ ] **v0.1 (Current)**: Core infrastructure — FastAPI gateway, single-node Docker scheduling, basic pipeline & Pydantic skill parsing.
- [ ] **v0.2**: Orchestration update — cross-node dynamic container scheduling, snapshot rollback, event-driven flow.
- [ ] **v0.3**: Full web console — dynamic topology graph, HITL approval panel, built-in Skill Hub.

## Contributing

AgentSwarm is in early rapid iteration. Issues and PRs welcome — especially skill packs for logic review and code validation. See `CONTRIBUTING.md`.

## License

[GNU Affero General Public License v3.0](LICENSE)
