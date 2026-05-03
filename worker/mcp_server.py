"""MCP Server 入口：stdio transport，注册本地工具和远程 Gateway 工具"""

import asyncio
import json
from collections.abc import Awaitable, Callable

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from worker.config import WorkerSettings
from worker.mcp_tools import execute_command, list_dir, read_file, write_file
from worker.snapshot_client import GatewayClient

# ---------------------------------------------------------------------------
# 工具定义
# ---------------------------------------------------------------------------

LOCAL_TOOLS: list[types.Tool] = [
    types.Tool(
        name="read_file",
        description="读取 /workspace 下的文件内容",
        inputSchema={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "相对于 /workspace 的文件路径"}},
            "required": ["path"],
        },
    ),
    types.Tool(
        name="write_file",
        description="写入 /workspace 下的文件",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对于 /workspace 的文件路径"},
                "content": {"type": "string", "description": "文件内容"},
            },
            "required": ["path", "content"],
        },
    ),
    types.Tool(
        name="list_dir",
        description="列出 /workspace 下的目录内容",
        inputSchema={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "相对于 /workspace 的目录路径"}},
            "required": ["path"],
        },
    ),
    types.Tool(
        name="execute_command",
        description="在 /workspace 目录下执行 shell 命令",
        inputSchema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的 shell 命令"},
                "timeout": {"type": "integer", "description": "超时秒数，默认 30", "default": 30},
            },
            "required": ["command"],
        },
    ),
]

REMOTE_TOOLS: list[types.Tool] = [
    types.Tool(
        name="snapshot",
        description="创建工作区快照（回调 Gateway）",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "快照名称"},
                "workspace_id": {"type": "string", "description": "工作区 ID"},
                "volume_name": {"type": "string", "description": "卷名称"},
            },
            "required": ["name", "workspace_id", "volume_name"],
        },
    ),
    types.Tool(
        name="restore",
        description="从快照恢复工作区（回调 Gateway）",
        inputSchema={
            "type": "object",
            "properties": {
                "snapshot_id": {"type": "string", "description": "快照 ID"},
                "workspace_id": {"type": "string", "description": "工作区 ID"},
                "volume_name": {"type": "string", "description": "卷名称"},
            },
            "required": ["snapshot_id", "workspace_id", "volume_name"],
        },
    ),
    types.Tool(
        name="spawn_agent",
        description="创建新 Agent（回调 Gateway）",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Agent 名称"},
                "role": {"type": "string", "description": "Agent 角色"},
                "workspace_id": {"type": "string", "description": "工作区 ID"},
            },
            "required": ["name", "role", "workspace_id"],
        },
    ),
    types.Tool(
        name="list_agents",
        description="列出工作区下的 Agent（回调 Gateway）",
        inputSchema={
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "工作区 ID"},
            },
            "required": ["workspace_id"],
        },
    ),
    types.Tool(
        name="acquire_lock",
        description="获取工作区独占锁（回调 Gateway）",
        inputSchema={
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "工作区 ID"},
                "node_id": {"type": "string", "description": "Agent node ID"},
                "container_id": {"type": "string", "description": "容器 ID"},
                "timeout_seconds": {"type": "integer", "description": "超时秒数，默认 600"},
            },
            "required": ["workspace_id", "node_id", "container_id"],
        },
    ),
    types.Tool(
        name="release_lock",
        description="释放工作区独占锁（回调 Gateway）",
        inputSchema={
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "工作区 ID"},
                "node_id": {"type": "string", "description": "Agent node ID"},
            },
            "required": ["workspace_id", "node_id"],
        },
    ),
    types.Tool(
        name="reject_to_previous_node",
        description="驳回上一个 Agent 的输出，回滚快照并注入反馈（回调 Gateway）",
        inputSchema={
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "工作区 ID"},
                "reviewer_node_id": {"type": "string", "description": "当前审查者 node_id"},
                "reason": {"type": "string", "description": "驳回原因"},
                "max_rejects": {"type": "integer", "description": "最大驳回次数，默认 3", "default": 3},
            },
            "required": ["workspace_id", "reviewer_node_id", "reason"],
        },
    ),
    types.Tool(
        name="get_feedback",
        description="获取当前 Agent 待处理的反馈记录（回调 Gateway）",
        inputSchema={
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "工作区 ID"},
                "node_id": {"type": "string", "description": "Agent node_id"},
            },
            "required": ["workspace_id", "node_id"],
        },
    ),
]

ALL_TOOLS = LOCAL_TOOLS + REMOTE_TOOLS

# ---------------------------------------------------------------------------
# Gateway client（模块级，供 dispatch 使用）
# ---------------------------------------------------------------------------

_gateway: GatewayClient | None = None


def _get_gateway() -> GatewayClient:
    if _gateway is None:
        raise RuntimeError("Gateway client not initialized")
    return _gateway


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _text(text: str) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=text)]


def _arg(arguments: dict[str, object], key: str) -> str:
    return str(arguments[key])


# ---------------------------------------------------------------------------
# 工具分发
# ---------------------------------------------------------------------------


async def _handle_read_file(arguments: dict[str, object]) -> list[types.TextContent]:
    return _text(read_file(_arg(arguments, "path")))


async def _handle_write_file(arguments: dict[str, object]) -> list[types.TextContent]:
    write_file(_arg(arguments, "path"), _arg(arguments, "content"))
    return _text("ok")


async def _handle_list_dir(arguments: dict[str, object]) -> list[types.TextContent]:
    return _text(json.dumps(list_dir(_arg(arguments, "path"))))


async def _handle_execute_command(arguments: dict[str, object]) -> list[types.TextContent]:
    timeout = int(str(arguments.get("timeout", "30")))
    return _text(json.dumps(execute_command(_arg(arguments, "command"), timeout)))


async def _handle_snapshot(arguments: dict[str, object]) -> list[types.TextContent]:
    gateway = _get_gateway()
    snapshot_id = await gateway.snapshot(
        _arg(arguments, "name"), _arg(arguments, "workspace_id"), _arg(arguments, "volume_name"),
    )
    return _text(json.dumps({"snapshot_id": snapshot_id}))


async def _handle_restore(arguments: dict[str, object]) -> list[types.TextContent]:
    gateway = _get_gateway()
    await gateway.restore(
        _arg(arguments, "snapshot_id"), _arg(arguments, "workspace_id"), _arg(arguments, "volume_name"),
    )
    return _text("ok")


async def _handle_spawn_agent(arguments: dict[str, object]) -> list[types.TextContent]:
    gateway = _get_gateway()
    agent = await gateway.spawn_agent(
        _arg(arguments, "name"), _arg(arguments, "role"), _arg(arguments, "workspace_id"),
    )
    return _text(json.dumps(agent))


async def _handle_list_agents(arguments: dict[str, object]) -> list[types.TextContent]:
    gateway = _get_gateway()
    agents = await gateway.list_agents(_arg(arguments, "workspace_id"))
    return _text(json.dumps(agents))


async def _handle_acquire_lock(arguments: dict[str, object]) -> list[types.TextContent]:
    gateway = _get_gateway()
    timeout = arguments.get("timeout_seconds")
    result = await gateway.acquire_lock(
        _arg(arguments, "workspace_id"),
        _arg(arguments, "node_id"),
        _arg(arguments, "container_id"),
        int(str(timeout)) if timeout is not None else None,
    )
    return _text(json.dumps(result))


async def _handle_release_lock(arguments: dict[str, object]) -> list[types.TextContent]:
    gateway = _get_gateway()
    result = await gateway.release_lock(
        _arg(arguments, "workspace_id"),
        _arg(arguments, "node_id"),
    )
    return _text(json.dumps(result))


async def _handle_reject_to_previous_node(arguments: dict[str, object]) -> list[types.TextContent]:
    gateway = _get_gateway()
    max_rejects = arguments.get("max_rejects")
    result = await gateway.reject_to_previous_node(
        _arg(arguments, "workspace_id"),
        _arg(arguments, "reviewer_node_id"),
        _arg(arguments, "reason"),
        int(str(max_rejects)) if max_rejects is not None else 3,
    )
    return _text(json.dumps(result))


async def _handle_get_feedback(arguments: dict[str, object]) -> list[types.TextContent]:
    gateway = _get_gateway()
    result = await gateway.get_feedback(
        _arg(arguments, "workspace_id"),
        _arg(arguments, "node_id"),
    )
    return _text(json.dumps(result))


_ToolHandler = Callable[[dict[str, object]], Awaitable[list[types.TextContent]]]

_DISPATCH_TABLE: dict[str, _ToolHandler] = {
    "read_file": _handle_read_file,
    "write_file": _handle_write_file,
    "list_dir": _handle_list_dir,
    "execute_command": _handle_execute_command,
    "snapshot": _handle_snapshot,
    "restore": _handle_restore,
    "spawn_agent": _handle_spawn_agent,
    "list_agents": _handle_list_agents,
    "acquire_lock": _handle_acquire_lock,
    "release_lock": _handle_release_lock,
    "reject_to_previous_node": _handle_reject_to_previous_node,
    "get_feedback": _handle_get_feedback,
}


async def dispatch_tool(name: str, arguments: dict[str, object]) -> list[types.TextContent]:
    """根据工具名分发到本地函数或远程 Gateway 调用"""
    handler = _DISPATCH_TABLE.get(name)
    if handler is None:
        raise ValueError(f"Unknown tool: {name}")
    return await handler(arguments)


# ---------------------------------------------------------------------------
# Server 创建
# ---------------------------------------------------------------------------


async def _list_tools() -> list[types.Tool]:
    return ALL_TOOLS


def create_server() -> Server:
    """创建 MCP Server 实例并注册所有工具 handler"""
    global _gateway  # noqa: PLW0603
    settings = WorkerSettings()
    _gateway = GatewayClient(settings)
    server = Server("agent-swarm-worker")

    server.list_tools()(_list_tools)
    server.call_tool()(dispatch_tool)

    return server


async def main() -> None:
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        init_options = server.create_initialization_options()
        await server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    asyncio.run(main())
