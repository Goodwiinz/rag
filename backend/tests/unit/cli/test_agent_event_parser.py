from src.cli.agent_event_parser import parse_sse_lines


def test_parse_sse_lines_returns_trace_and_token_events() -> None:
    events = list(
        parse_sse_lines(
            [
                "event: trace",
                'data: {"thread_id":"t1","cli_session_id":"c1","langsmith_run_id":"r1","langsmith_url":"u1"}',
                "",
                "event: token",
                'data: {"content":"Hello"}',
                "",
            ]
        )
    )

    assert events[0].type == "trace"
    assert events[0].data["langsmith_run_id"] == "r1"
    assert events[1].type == "token"
    assert events[1].data["content"] == "Hello"
