"""Pydantic request/response schemas for API."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PlanRunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    idea: Optional[str] = None
    plan_id: str = Field(default="test", alias="planId")
    skip_quality_assessment: bool = Field(default=False, alias="skipQualityAssessment")


class MonitorTimetableRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    execution: dict = Field(..., description="Execution data with tasks")
    plan_id: str = Field(default="test", alias="planId")


class TaskIdRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    task_id: str = Field(..., alias="taskId")


class ExecutionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    plan_id: str = Field(default="test", alias="planId")


class ValidationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    plan_id: str = Field(default="test", alias="planId")
