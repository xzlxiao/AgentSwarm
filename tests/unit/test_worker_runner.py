import asyncio
import tempfile
import os

from worker.models import WorkerTaskPayload
from worker.runner import TaskRunner


def test_execute_writes_output() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = TaskRunner(workspace_path=tmpdir)

        payload = WorkerTaskPayload(
            task_id="t-001",
            task_type="write",
            instructions="Hello World",
            output_path="output/result.txt",
        )
        asyncio.run(runner.execute(payload))

        assert runner.status == "completed"
        assert runner.execution_summary is not None
        assert "write" in runner.execution_summary

        assert os.path.exists(os.path.join(tmpdir, "output", "result.txt"))


def test_execute_failure_status() -> None:
    runner = TaskRunner(workspace_path="/nonexistent/path")
    payload = WorkerTaskPayload(
        task_id="t-002",
        task_type="test",
        instructions="fail",
        output_path="/nonexistent/output.txt",
    )
    asyncio.run(runner.execute(payload))

    assert runner.status == "failed"
    assert runner.execution_summary is not None
    assert "Error" in runner.execution_summary
