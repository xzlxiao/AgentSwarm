import os

from worker.models import WorkerTaskPayload


class TaskRunner:
    def __init__(self, workspace_path: str = "/workspace") -> None:
        self.workspace_path = workspace_path
        self.status: str = "idle"
        self.current_task_id: str | None = None
        self.execution_summary: str | None = None

    async def execute(self, payload: WorkerTaskPayload) -> None:
        self.status = "running"
        self.current_task_id = payload.task_id
        self.execution_summary = None

        try:
            full_path = os.path.join(self.workspace_path, payload.output_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(payload.instructions)

            self.status = "completed"
            self.execution_summary = f"Task {payload.task_type} completed"
        except Exception as e:
            self.status = "failed"
            self.execution_summary = f"Error: {e}"
        finally:
            self.current_task_id = None
