from pydantic import BaseModel, Field


class StartRequest(BaseModel):
    input: str = Field(..., max_length=100_000)


class StageStatus(BaseModel):
    name: str
    state: str
    output_length: int
    rounds: int = 0


class PipelineStatus(BaseModel):
    input: str
    stages: list[StageStatus]


class ActionResponse(BaseModel):
    stage: str
    state: str
    message: str = ""
