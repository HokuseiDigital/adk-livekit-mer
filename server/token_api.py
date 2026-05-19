"""LiveKit access token endpoint for the MRE.

Exposes ``POST /token`` taking ``{ user_name }`` and returning a signed
JWT plus the room URL the React frontend should connect to. The token
embeds a ``RoomAgentDispatch`` so LiveKit Cloud automatically launches
the ``demo-agent`` worker when the user joins.
"""

import json
import logging
import os
from datetime import timedelta
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from livekit.api import (
    AccessToken,
    RoomAgentDispatch,
    RoomConfiguration,
    VideoGrants,
)
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("token_api")


LIVEKIT_URL = os.environ.get("LIVEKIT_URL")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET")
AGENT_NAME = os.environ.get("LIVEKIT_AGENT_NAME", "demo-agent")

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")


app = FastAPI(title="LiveKit + ADK MRE — token API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TokenRequest(BaseModel):
    user_name: str | None = None


class TokenResponse(BaseModel):
    url: str
    token: str
    room_name: str
    agent_name: str


@app.post("/token", response_model=TokenResponse)
def issue_token(req: TokenRequest) -> TokenResponse:
    if not (LIVEKIT_URL and LIVEKIT_API_KEY and LIVEKIT_API_SECRET):
        raise HTTPException(
            status_code=503,
            detail="LiveKit not configured. Set LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET.",
        )

    user_name = (req.user_name or "guest").strip() or "guest"
    room_name = f"mre-{uuid4().hex[:8]}"

    jwt = (
        AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(user_name)
        .with_name(user_name)
        .with_grants(
            VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .with_room_config(
            RoomConfiguration(
                agents=[
                    RoomAgentDispatch(
                        agent_name=AGENT_NAME,
                        metadata=json.dumps({"user_name": user_name}),
                    )
                ],
            )
        )
        .with_ttl(timedelta(minutes=15))
        .to_jwt()
    )

    logger.info("issued token for user=%s room=%s", user_name, room_name)
    return TokenResponse(
        url=LIVEKIT_URL,
        token=jwt,
        room_name=room_name,
        agent_name=AGENT_NAME,
    )


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "livekit_configured": bool(LIVEKIT_URL and LIVEKIT_API_KEY)}
