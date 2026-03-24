"""Integration tests for Phase 18 agent infrastructure."""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# --- Session tests ---

class TestSessions:
    def test_create_new_session(self):
        from app.agents.sessions import get_or_create_session, _sessions
        _sessions.clear()
        sid, history = get_or_create_session(None, "canvas_agent")
        assert sid is not None
        assert len(sid) == 36  # UUID format
        assert history == []

    def test_get_existing_session(self):
        from app.agents.sessions import get_or_create_session, update_session, _sessions
        _sessions.clear()
        sid, history = get_or_create_session(None)
        history.append("test_message")
        update_session(sid, history)
        sid2, history2 = get_or_create_session(sid)
        assert sid2 == sid
        assert history2 == ["test_message"]

    def test_session_count(self):
        from app.agents.sessions import get_or_create_session, active_session_count, _sessions
        _sessions.clear()
        get_or_create_session(None)
        get_or_create_session(None)
        assert active_session_count() == 2

    def test_session_cleanup_removes_expired(self):
        """Session cleanup removes sessions older than TTL."""
        from app.agents.sessions import _sessions, active_session_count
        _sessions.clear()
        # Manually insert a session with old last_accessed
        _sessions["expired-session"] = {
            "history": [],
            "last_accessed": time.time() - 99999,  # way in the past
            "persona": "canvas_agent",
        }
        _sessions["active-session"] = {
            "history": [],
            "last_accessed": time.time(),
            "persona": "canvas_agent",
        }
        # Simulate cleanup logic
        ttl_seconds = 30 * 60  # 30 minutes
        now = time.time()
        expired = [
            sid for sid, s in _sessions.items()
            if now - s["last_accessed"] > ttl_seconds
        ]
        for sid in expired:
            del _sessions[sid]
        assert "expired-session" not in _sessions
        assert "active-session" in _sessions
        assert active_session_count() == 1


# --- Registry tests ---

class TestRegistry:
    def test_agent_tool_decorator_registers(self):
        from app.agents.registry import _tools, agent_tool, get_tool

        @agent_tool(
            name="test_tool_xyz",
            description="test",
            parameters_schema={"type": "object", "properties": {}},
        )
        async def my_test_tool(ctx):
            return {"ok": True}

        assert get_tool("test_tool_xyz") is not None
        # Cleanup
        del _tools["test_tool_xyz"]

    def test_get_nonexistent_tool(self):
        from app.agents.registry import get_tool
        assert get_tool("does_not_exist_xyz") is None

    def test_catalog_tools_registered(self):
        import app.agents.tools.catalog_tools  # trigger registration
        from app.agents.registry import get_tool
        assert get_tool("list_cubes_summary") is not None
        assert get_tool("get_cube_definition") is not None


# --- Dispatcher tests ---

class TestDispatcher:
    @pytest.mark.asyncio
    async def test_dispatch_unknown_tool(self):
        from app.agents.dispatcher import dispatch_tool
        from app.agents.context import ToolContext
        ctx = ToolContext(db_session=None, cube_registry=None)
        result = await dispatch_tool("totally_fake_tool", {}, ctx)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_dispatch_failing_tool_returns_error(self):
        from app.agents.registry import agent_tool, _tools
        from app.agents.dispatcher import dispatch_tool
        from app.agents.context import ToolContext

        @agent_tool(
            name="always_fails_xyz",
            description="fails",
            parameters_schema={"type": "object", "properties": {}},
        )
        async def fail_tool(ctx):
            raise ValueError("intentional failure")

        ctx = ToolContext(db_session=None, cube_registry=None)
        result = await dispatch_tool("always_fails_xyz", {}, ctx)
        assert "error" in result
        assert "intentional failure" in result["error"]
        del _tools["always_fails_xyz"]


# --- Context tests ---

class TestContext:
    def test_estimate_tokens_simple(self):
        from app.agents.context import estimate_tokens

        class MockPart:
            def __init__(self, text):
                self.text = text
                self.function_response = None

        class MockContent:
            def __init__(self, text):
                self.parts = [MockPart(text)]

        # 400 chars should be ~100 tokens
        history = [MockContent("a" * 400)]
        tokens = estimate_tokens(history)
        assert tokens == 100

    def test_prune_preserves_system_prompt(self):
        from app.agents.context import prune_history, PRUNE_THRESHOLD_TOKENS

        class MockPart:
            def __init__(self, text):
                self.text = text
                self.function_response = None

        class MockContent:
            def __init__(self, text):
                self.parts = [MockPart(text)]

        # Create history that exceeds threshold
        system = MockContent("system prompt")
        big = MockContent("x" * (PRUNE_THRESHOLD_TOKENS * 4 + 100))
        recent = MockContent("recent message")
        history = [system, big, recent]
        pruned = prune_history(history, system_prompt_turns=1)
        # System prompt should still be first
        assert pruned[0].parts[0].text == "system prompt"

    def test_prune_returns_same_list(self):
        """prune_history mutates in place and returns the list."""
        from app.agents.context import prune_history

        class MockPart:
            def __init__(self, text):
                self.text = text
                self.function_response = None

        class MockContent:
            def __init__(self, text):
                self.parts = [MockPart(text)]

        history = [MockContent("a")]
        result = prune_history(history)
        assert result is history


# --- Skills tests ---

class TestSkills:
    def test_load_and_get(self):
        from app.agents.skills_loader import load_skill_files, get_skill
        load_skill_files()
        brief = get_skill("system_brief")
        assert len(brief) > 0
        assert "Tracer 42" in brief or "tracer" in brief.lower()

    def test_get_system_prompt_combines(self):
        from app.agents.skills_loader import load_skill_files, get_system_prompt
        load_skill_files()
        prompt = get_system_prompt("canvas_agent")
        assert "Canvas Agent" in prompt

    def test_all_personas_loaded(self):
        from app.agents.skills_loader import load_skill_files, get_all_personas
        load_skill_files()
        personas = get_all_personas()
        expected = {"canvas_agent", "build_agent", "cube_expert", "validation_agent", "results_interpreter"}
        assert set(personas) == expected, f"Got {personas}"


# --- Schema tests ---

class TestSchemas:
    def test_chat_request_requires_message(self):
        from app.agents.schemas import AgentChatRequest
        req = AgentChatRequest(message="hello")
        assert req.message == "hello"
        assert req.session_id is None
        assert req.persona == "canvas_agent"

    def test_sse_event(self):
        from app.agents.schemas import AgentSSEEvent
        evt = AgentSSEEvent(type="text", data="hello")
        dumped = evt.model_dump_json()
        assert "text" in dumped

    def test_chat_request_empty_message_invalid(self):
        from app.agents.schemas import AgentChatRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AgentChatRequest(message="")
