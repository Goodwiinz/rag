from src.api.agent.streaming import _SeqEmitter
from src.shared.enums import AgentStreamEvent


async def test_status_frames_accumulate_bounded_display_safe_progress() -> None:
    emitter = _SeqEmitter()

    for index in range(18):
        await emitter.emit(
            AgentStreamEvent.STATUS,
            {"phase": "planning", "detail": f"Step {index}"},
            buffer=False,
        )
    await emitter.emit(
        AgentStreamEvent.STATUS,
        {"phase": "planning", "detail": "Step 17"},
        buffer=False,
    )
    await emitter.emit(
        AgentStreamEvent.STATUS,
        {"phase": "private", "detail": "hidden"},
        buffer=False,
    )

    assert len(emitter.progress_steps) == 16
    assert emitter.progress_steps[0]["detail"] == "Step 2"
    assert emitter.progress_steps[-1] == {
        "phase": "planning",
        "detail": "Step 17",
    }
