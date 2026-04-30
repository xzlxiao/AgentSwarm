"""MCP 本地工具：直接操作 /workspace 挂载点的文件系统和命令执行"""

import os
import subprocess

WORKSPACE_ROOT = os.path.realpath("/workspace")

# 危险命令模式（容器沙箱内的基本防护）
_DANGEROUS_PATTERNS = (
    "rm -rf /",
    "mkfs.",
    "dd if=",
    ":(){ :|:& };:",
)


def _safe_path(path: str) -> str:
    """验证路径不逃逸 /workspace"""
    full_path = os.path.realpath(os.path.join(WORKSPACE_ROOT, path))
    if not full_path.startswith(WORKSPACE_ROOT + os.sep) and full_path != WORKSPACE_ROOT:
        raise ValueError(f"Path traversal denied: {path}")
    return full_path


def read_file(path: str) -> str:
    """读取 /workspace 下的文件内容"""
    full_path = _safe_path(path)
    with open(full_path, encoding="utf-8") as f:
        return f.read()


def write_file(path: str, content: str) -> None:
    """写入 /workspace 下的文件"""
    full_path = _safe_path(path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)


def list_dir(path: str) -> list[str]:
    """列出 /workspace 下的目录内容"""
    full_path = _safe_path(path)
    return os.listdir(full_path)


def execute_command(command: str, timeout: int = 30) -> dict[str, object]:
    """在 /workspace 目录下执行 shell 命令"""
    for pattern in _DANGEROUS_PATTERNS:
        if pattern in command:
            raise ValueError(f"Forbidden command pattern: {pattern}")
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=WORKSPACE_ROOT,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
