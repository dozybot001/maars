"""Config API routes. Backend maintains api_config.json; frontend fetches and overwrites on save."""

from fastapi import APIRouter, Body

from db import get_api_config, save_api_config

router = APIRouter()


@router.get("")
async def get_config():
    """Return api_config.json contents."""
    config = await get_api_config()
    return {"config": config}


@router.post("")
async def save_config(body: dict = Body(...)):
    """Overwrite api_config.json with request body."""
    await save_api_config(body)
    return {"success": True}
