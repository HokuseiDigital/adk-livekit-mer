"""Toy ADK agent for the MRE.

Shape mirrors a small production agent (root coordinator + one
sub-agent + a few function tools) so reviewers can see how the bridge
handles delegation and tool calls, not just plain chat. Nothing here is
LiveKit-aware — this is ordinary ADK code, lifted as-is.
"""

import asyncio
import contextvars
import json
import logging
from datetime import UTC, datetime

from google.adk.agents import LlmAgent

logger = logging.getLogger(__name__)


# Set by adk_bridge before each Runner.run_async so tools that need to
# emit events to the browser (set_status_message) can reach the room.
# Imported lazily inside the tool to avoid a circular module import.


def get_current_time() -> dict:
    """Return the current server time in ISO 8601."""
    return {"iso": datetime.now(UTC).isoformat()}


_USER_DIRECTORY: dict[str, str] = {
    "alice": "alice@example.com",
    "bob": "bob@example.com",
    "charlie": "charlie@example.com",
    "dana": "dana@example.com",
}


def lookup_user(name: str) -> dict:
    """Look up a user's email by their first name.

    Returns ``{"email": null}`` when the name is not in the demo directory.
    """
    return {"email": _USER_DIRECTORY.get(name.strip().lower())}


def set_status_message(text: str) -> dict:
    """Send a status banner to the browser UI (voice → UI demo)."""
    from adk_bridge import current_room  # noqa: PLC0415 — break import cycle

    room = current_room.get()
    if room is None:
        logger.warning("set_status_message called without an active room")
        return {"sent": False}
    payload = json.dumps({"kind": "status", "text": text}).encode("utf-8")
    # Tool bodies are sync but publish_data is async — fire-and-forget so
    # the agent's turn doesn't block on the data channel ACK.
    asyncio.create_task(room.local_participant.publish_data(payload, reliable=True))
    return {"sent": True, "text": text}


_FACTS = {
    "livekit": "LiveKit is an open-source WebRTC platform for voice, video, and realtime AI agents.",
    "agents": "LiveKit Agents is a Python and Node framework for building voice and video AI agents on top of LiveKit.",
    "adk": "Google's Agent Development Kit is a framework for building multi-agent systems on Gemini.",
    "gemini": "Gemini is Google's flagship multimodal LLM, used as the default model in ADK.",
    "mre": "This project is a minimum reproducible example of a LiveKit Agents worker driven by an ADK agent.",
}


def search_facts(query: str) -> dict:
    """Search the demo knowledge base for a fact related to the query."""
    needle = query.lower()
    for key, value in _FACTS.items():
        if key in needle:
            return {"answer": value, "source": key}
    return {"answer": "No matching fact in the demo knowledge base.", "source": None}


def _create_search_agent(model: str) -> LlmAgent:
    return LlmAgent(
        name="SearchAgent",
        model=model,
        description=(
            "Specialist that answers factual questions about LiveKit, ADK, "
            "Gemini, or this demo by calling search_facts."
        ),
        instruction=(
            "You are a research specialist. When the user asks a factual "
            "question, call search_facts with a concise query, then respond "
            "in one short sentence. No formatting, just speech."
        ),
        tools=[search_facts],
    )


def create_demo_agent(model: str) -> LlmAgent:
    """Build the root coordinator with tools and one sub-agent."""
    search_agent = _create_search_agent(model)
    return LlmAgent(
        name="DemoCoordinator",
        model=model,
        description="Voice assistant for the LiveKit + ADK MRE.",
        instruction=(
            "You are a friendly voice assistant. The current user is "
            "{user_name}. Speak naturally and concisely — one or two short "
            "sentences, no markdown, no asterisks, spell numbers. "
            "Delegate to SearchAgent for factual questions about LiveKit, "
            "ADK, Gemini, or this demo. Use get_current_time when asked "
            "about the time, lookup_user when asked to find someone, and "
            "set_status_message when the user asks you to display something "
            "on screen."
        ),
        tools=[get_current_time, lookup_user, set_status_message],
        sub_agents=[search_agent],
    )
