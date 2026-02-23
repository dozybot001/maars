"""API route modules."""

from fastapi import FastAPI

from . import config, db, execution, monitor, plan, plans, validation, workers
from ..state import PlanRunState, init_api_state


def register_routes(app: FastAPI, sio, executor_runner, plan_run_state: PlanRunState):
    """Register all API routers. Call after app, sio, executor_runner are created."""
    init_api_state(sio, executor_runner, plan_run_state)

    app.include_router(db.router, prefix="/api/db", tags=["db"])
    app.include_router(plan.router, prefix="/api/plan", tags=["plan"])
    app.include_router(plans.router, prefix="/api/plans", tags=["plans"])
    app.include_router(execution.router, prefix="/api/execution", tags=["execution"])
    app.include_router(monitor.router, prefix="/api/monitor", tags=["monitor"])
    app.include_router(validation.router, prefix="/api/validation", tags=["validation"])
    app.include_router(config.router, prefix="/api/config", tags=["config"])
    app.include_router(workers.router, prefix="/api", tags=["workers"])
