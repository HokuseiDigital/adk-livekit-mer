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
import random
from datetime import UTC, datetime

from google.adk.agents import LlmAgent
from google.adk.tools import ToolContext

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


_FORTUNES = [
    "A new opportunity will appear when you least expect it.",
    "The journey of a thousand commits begins with a single push.",
    "Patience and persistence shape data into gold.",
    "Today, the bug you fix may save a thousand future engineers.",
    "Speak less, deploy more.",
    "Your code will compile on the first try this week.",
    "An old tool will solve a new problem.",
    "Refactoring is just procrastination wearing a suit.",
]


def get_fortune_cookie() -> dict:
    """Return a random fortune cookie message."""
    return {"fortune": random.choice(_FORTUNES)}


# Tool functions can declare ``tool_context: ToolContext`` and ADK
# auto-injects the active session's context, exposing ``state`` for
# read/write. The todo list demo uses this to keep state per voice
# call without any external storage.
_TODOS_STATE_KEY = "todos"


def add_todo(item: str, tool_context: ToolContext) -> dict:
    """Add an item to the user's TODO list for this call.

    Gemini Flash occasionally emits two identical ``function_call`` parts
    for a single user request; we dedupe consecutive open duplicates so
    one spoken "add buy milk" reliably produces one row, while still
    letting the user explicitly add the same text twice across
    different turns.
    """
    text = item.strip()
    todos = list(tool_context.state.get(_TODOS_STATE_KEY, []))
    if todos and not todos[-1]["done"] and todos[-1]["text"] == text:
        return {"already_present": text, "total": len(todos)}
    todos.append({"text": text, "done": False})
    tool_context.state[_TODOS_STATE_KEY] = todos
    return {"added": text, "total": len(todos)}


def list_todos(tool_context: ToolContext) -> dict:
    """Read back the current TODO list."""
    todos = tool_context.state.get(_TODOS_STATE_KEY, [])
    return {"todos": list(todos), "total": len(todos)}


def complete_todo(index: int, tool_context: ToolContext) -> dict:
    """Mark a TODO as complete by its 1-based index."""
    todos = list(tool_context.state.get(_TODOS_STATE_KEY, []))
    if index < 1 or index > len(todos):
        return {
            "error": f"There is no TODO at position {index} — you have {len(todos)} item(s)."
        }
    todos[index - 1]["done"] = True
    tool_context.state[_TODOS_STATE_KEY] = todos
    open_count = sum(1 for t in todos if not t["done"])
    return {
        "completed": todos[index - 1]["text"],
        "remaining_open": open_count,
    }


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
            "sentences, no markdown, no asterisks, spell numbers.\n\n"
            "Tool use rules:\n"
            "- Call each tool EXACTLY ONCE per user request. Never call "
            "the same tool with the same arguments twice in a row.\n"
            "- Wait for the tool result before deciding whether you need "
            "another tool — never speculate by re-calling.\n\n"
            "Available tools:\n"
            "- Delegate to SearchAgent for factual questions about "
            "LiveKit, ADK, Gemini, or this demo.\n"
            "- get_current_time for time questions.\n"
            "- lookup_user to find someone's email.\n"
            "- get_fortune_cookie for a random fortune.\n"
            "- add_todo / list_todos / complete_todo for the per-call "
            "TODO list. Adding one item is exactly one add_todo call.\n"
            "- set_status_message when the user asks you to display "
            "something on their screen."
        ),
        tools=[
            get_current_time,
            lookup_user,
            get_fortune_cookie,
            add_todo,
            list_todos,
            complete_todo,
            set_status_message,
        ],
        sub_agents=[search_agent],
    )
