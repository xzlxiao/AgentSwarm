"""MCP 本地工具单元测试"""

import json
import os
from typing import Any

import pytest

from worker.mcp_tools import WORKSPACE_ROOT, execute_command, list_dir, read_file, write_file


@pytest.fixture(autouse=True)
def setup_workspace(tmp_path: Any, monkeypatch: Any) -> Any:
    """将 WORKSPACE_ROOT 重定向到临时目录"""
    monkeypatch.setattr("worker.mcp_tools.WORKSPACE_ROOT", str(tmp_path))
    return tmp_path


def test_write_and_read_file(setup_workspace: Any) -> Any:
    write_file("subdir/test.txt", "hello world")
    content = read_file("subdir/test.txt")
    assert content == "hello world"


def test_read_file_not_found(setup_workspace: Any) -> Any:
    with pytest.raises(FileNotFoundError):
        read_file("nonexistent.txt")


def test_write_file_creates_dirs(setup_workspace: Any) -> Any:
    write_file("a/b/c/deep.txt", "deep content")
    assert read_file("a/b/c/deep.txt") == "deep content"


def test_list_dir(setup_workspace: Any) -> Any:
    write_file("file1.txt", "a")
    write_file("file2.txt", "b")
    write_file("sub/file3.txt", "c")
    entries = list_dir(".")
    assert "file1.txt" in entries
    assert "file2.txt" in entries
    assert "sub" in entries


def test_list_dir_not_found(setup_workspace: Any) -> Any:
    with pytest.raises(FileNotFoundError):
        list_dir("nonexistent_dir")


def test_execute_command_success(setup_workspace: Any) -> Any:
    result = execute_command("echo hello")
    assert result["returncode"] == 0
    assert "hello" in str(result["stdout"])


def test_execute_command_failure(setup_workspace: Any) -> Any:
    result = execute_command("exit 1")
    assert result["returncode"] == 1


def test_execute_command_captures_stderr(setup_workspace: Any) -> Any:
    result = execute_command("echo error >&2")
    assert result["returncode"] == 0
    assert "error" in str(result["stderr"])


def test_path_traversal_denied(setup_workspace: Any) -> Any:
    with pytest.raises(ValueError, match="Path traversal denied"):
        read_file("../../etc/passwd")


def test_path_traversal_write_denied(setup_workspace: Any) -> Any:
    with pytest.raises(ValueError, match="Path traversal denied"):
        write_file("../outside.txt", "escape")


def test_path_traversal_list_denied(setup_workspace: Any) -> Any:
    with pytest.raises(ValueError, match="Path traversal denied"):
        list_dir("../../")


def test_forbidden_command_denied(setup_workspace: Any) -> Any:
    with pytest.raises(ValueError, match="Forbidden command pattern"):
        execute_command("rm -rf /")
