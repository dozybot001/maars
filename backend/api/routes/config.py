"""Config API routes."""

from fastapi import APIRouter, Body

from db import get_api_config, save_api_config

router = APIRouter()


@router.get("")
async def get_config():
    """Get API config from db."""
    config = await get_api_config()
    return {"config": config}


@router.post("")
async def save_config(body: dict = Body(...)):
    """Save API config to db. Accepts full config including presets."""
    await save_api_config(body)
    return {"success": True}
