from pydantic import BaseModel, Field


class WorkerTaskPayload(BaseModel):
    task_id: str = Field(..., description="任务唯一 ID")
    task_type: str = Field(..., description="任务类型标识符")
    instructions: str = Field(..., description="任务指令描述")
    output_path: str = Field(..., description="输出文件路径")
