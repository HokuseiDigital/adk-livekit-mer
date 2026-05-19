"""LiveKit voice worker entrypoint.

Reads the participant identity and dispatch metadata, hands them to the
ADK bridge, and starts an ``AgentSession`` with the usual STT/TTS
pipeline. The configured ``llm=`` is a fallback the bridge never calls
— ``AdkVoiceAgent.llm_node`` overrides it for every turn.
"""

import json
import logging
from typing import cast

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import (
    AgentServer,
    AgentSession,
    TurnHandlingOptions,
)
from livekit.plugins import deepgram, openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from adk_bridge import AdkVoiceAgent

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")


AGENT_NAME = "demo-agent"
server = AgentServer()


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: agents.JobContext) -> None:
    await ctx.connect()
    participant = await ctx.wait_for_participant()

    user_name = participant.identity or "guest"
    raw_metadata = getattr(ctx.job, "metadata", None)
    if raw_metadata:
        try:
            parsed = json.loads(raw_metadata)
            if isinstance(parsed, dict) and parsed.get("user_name"):
                user_name = cast(str, parsed["user_name"])
        except (json.JSONDecodeError, TypeError):
            logger.warning("ignoring invalid dispatch metadata: %r", raw_metadata)

    logger.info("voice session starting (user=%s, room=%s)", user_name, ctx.room.name)

    voice_agent = AdkVoiceAgent(user_name=user_name, room=ctx.room)

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        # Required by LiveKit but unused — llm_node delegates to ADK.
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(),
        vad=silero.VAD.load(),
        turn_handling=TurnHandlingOptions(turn_detection=MultilingualModel()),
    )

    await session.start(room=ctx.room, agent=voice_agent)
    await session.generate_reply(
        instructions=(
            f"Greet {user_name} briefly. Tell them you can search facts, "
            "look up users, get the current time, and post status messages "
            "to their screen. Ask what they want to try."
        )
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
