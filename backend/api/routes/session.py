"""Session bootstrap API - issue signed session credentials."""

from fastapi import APIRouter

from .. import state as api_state

router = APIRouter()


@router.post("/init")
async def init_session():
    """Issue a signed session credential pair and pre-create session context."""
    creds = api_state.issue_session_credentials()
    await api_state.get_or_create_session_state(creds["sessionId"])
    return {
        "sessionId": creds["sessionId"],
        "sessionToken": creds["sessionToken"],
        "idleTtlSeconds": api_state.SESSION_IDLE_TTL_SECONDS,
    }
