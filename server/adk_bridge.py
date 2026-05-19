"""LiveKit ↔ Google ADK bridge.

This is the artifact we want feedback on. The override of
``Agent.llm_node`` replaces the LLM configured on ``AgentSession`` with
an ADK ``InMemoryRunner`` for the duration of one turn. Each LiveKit
room maps to one ADK session, with state seeded once from the dispatch
metadata so ADK callbacks and instructions can read project- or user-
specific context.

The rest of the LiveKit Agents pipeline (STT, TTS, VAD, turn detection,
data channels) is untouched.
"""

import contextvars
import logging
import os
from collections.abc import AsyncIterable

from google.adk.runners import InMemoryRunner
from google.genai import types
from livekit.agents import Agent, FunctionTool, ModelSettings
from livekit.agents.llm import ChatChunk, ChatContext, ChoiceDelta
from livekit.rtc import Room

from demo_agent import create_demo_agent

logger = logging.getLogger(__name__)

APP_NAME = "livekit_adk_mre"
DEFAULT_MODEL = os.environ.get("DEMO_AGENT_MODEL", "gemini-2.5-flash")

# Tools that need to publish events back to the browser (e.g.
# set_status_message) read the active room from this contextvar.
# adk_bridge sets it before each Runner.run_async call so the tool's
# function body — a plain sync Python function — can see "the room
# this voice turn belongs to" without taking it as a parameter.
current_room: contextvars.ContextVar[Room | None] = contextvars.ContextVar(
    "current_room", default=None
)


class AdkVoiceAgent(Agent):
    """LiveKit ``Agent`` whose LLM step is delegated to an ADK Runner."""

    def __init__(self, *, user_name: str, room: Room) -> None:
        # The instructions on the LiveKit Agent are unused — the ADK
        # demo agent owns the system prompt — but the base class
        # requires a string.
        super().__init__(instructions="(delegated to ADK)")
        self._user_name = user_name
        self._room = room
        self._runner = InMemoryRunner(
            agent=create_demo_agent(DEFAULT_MODEL),
            app_name=APP_NAME,
        )
        self._session_id = f"voice-{user_name}-{id(self)}"
        self._session_ready = False

    async def _ensure_session(self) -> None:
        if self._session_ready:
            return
        await self._runner.session_service.create_session(
            app_name=APP_NAME,
            user_id=self._user_name,
            session_id=self._session_id,
            state={"user_name": self._user_name},
        )
        self._session_ready = True
        logger.info(
            "ADK session ready (user=%s, session=%s)",
            self._user_name,
            self._session_id,
        )

    async def llm_node(
        self,
        chat_ctx: ChatContext,
        tools: list[FunctionTool],
        model_settings: ModelSettings,
    ) -> AsyncIterable[ChatChunk]:
        await self._ensure_session()

        last_user_text: str | None = None
        for item in reversed(chat_ctx.items):
            if getattr(item, "role", None) != "user":
                continue
            text = getattr(item, "text_content", None)
            if text:
                last_user_text = text
                break

        if not last_user_text:
            return

        message = types.Content(
            role="user", parts=[types.Part(text=last_user_text)]
        )

        emitted_so_far = ""
        token = current_room.set(self._room)
        try:
            async for event in self._runner.run_async(
                user_id=self._user_name,
                session_id=self._session_id,
                new_message=message,
            ):
                await self._publish_debug(event)
                content = getattr(event, "content", None)
                if not content or not getattr(content, "parts", None):
                    continue
                for part in content.parts:
                    text = getattr(part, "text", None)
                    if not text:
                        continue
                    delta = (
                        text[len(emitted_so_far) :]
                        if text.startswith(emitted_so_far)
                        else text
                    )
                    emitted_so_far = text
                    if delta:
                        yield ChatChunk(
                            id=str(getattr(event, "invocation_id", "") or ""),
                            delta=ChoiceDelta(role="assistant", content=delta),
                        )
        finally:
            current_room.reset(token)

    async def _publish_debug(self, event: object) -> None:
        """Mirror every ADK event onto the room's data channel.

        The frontend's DebugPanel subscribes to these and renders a live
        feed of authors, function calls, and final responses. Failures
        publishing debug data must never break the voice turn.
        """
        try:
            import json

            payload = {
                "kind": "adk_event",
                "author": getattr(event, "author", None),
                "is_final": (
                    event.is_final_response()
                    if hasattr(event, "is_final_response")
                    else None
                ),
            }
            content = getattr(event, "content", None)
            if content and getattr(content, "parts", None):
                payload["parts"] = [
                    {
                        "text": getattr(p, "text", None),
                        "function_call": (
                            {
                                "name": p.function_call.name,
                                "args": dict(p.function_call.args or {}),
                            }
                            if getattr(p, "function_call", None)
                            else None
                        ),
                        "function_response": (
                            {
                                "name": p.function_response.name,
                                "response": dict(p.function_response.response or {}),
                            }
                            if getattr(p, "function_response", None)
                            else None
                        ),
                    }
                    for p in content.parts
                ]
            await self._room.local_participant.publish_data(
                json.dumps(payload).encode("utf-8"), reliable=True
            )
        except Exception:
            logger.debug("failed to publish debug event", exc_info=True)
