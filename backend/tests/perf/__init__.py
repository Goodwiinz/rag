"""Performance / latency harness for the NOUS LangGraph agent.

Houses the repeatable, LangSmith-traced version of the manual SDK latency
audit. Tests here are gated behind ``RUN_PERF_HARNESS=1`` plus live LLM +
LangSmith credentials and skip cleanly in the unit lane.
"""
