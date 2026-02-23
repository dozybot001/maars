"""Monitor API routes."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from monitor import build_layout_from_execution

from .. import state as api_state
from ..schemas import MonitorTimetableRequest

router = APIRouter()


@router.post("/timetable")
async def set_timetable(body: MonitorTimetableRequest):
    execution = body.execution
    plan_id = body.plan_id
    layout = build_layout_from_execution(execution)
    try:
        api_state.executor_runner.set_layout(layout, plan_id=plan_id, execution=execution)
    except ValueError as e:
        return JSONResponse(status_code=409, content={"error": str(e)})
    return {"layout": layout}
