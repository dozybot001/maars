"""Validation API routes."""

from fastapi import APIRouter, Query

from db import get_validation, save_validation

from ..schemas import ValidationRequest

router = APIRouter()


@router.get("")
async def get_validation_route(plan_id: str = Query("test", alias="planId")):
    validation = await get_validation(plan_id)
    return {"validation": validation}


@router.post("")
async def post_validation(body: ValidationRequest):
    plan_id = body.plan_id
    payload = body.model_dump(exclude={"plan_id"})
    result = await save_validation(payload, plan_id)
    return result
