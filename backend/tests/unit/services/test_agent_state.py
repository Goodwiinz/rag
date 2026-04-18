"""Tests for AgentState v2 fields."""
import pytest
from src.services.agent.state import AgentState


@pytest.mark.unit
class TestAgentStateV2Fields:
    def test_state_has_plan_field(self):
        state: AgentState = {
            "messages": [], "page_context": {}, "retrieved_contexts": [],
            "tool_executions": [], "thread_id": "", "tool_loop_count": 0,
            "error_count": 0, "last_error": "", "pending_confirmation": {},
            "user_confirmed": False, "intent": "general", "user_memories": [],
            "plan": [], "reflection_count": 0, "compaction_count": 0,
            "intent_confidence": 0.0, "last_error_info": {},
        }
        assert state["plan"] == []
        assert state["reflection_count"] == 0
        assert state["compaction_count"] == 0
        assert state["intent_confidence"] == 0.0
        assert state["last_error_info"] == {}
