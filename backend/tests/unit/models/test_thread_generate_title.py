"""Regression tests for Thread.generate_title async-safety.

`generate_title()` is called by the project-chat link/list endpoints via
`thread.title or thread.generate_title()`. It reads `self.messages`, which
triggers a lazy load when the relationship is not eager-loaded. Under the async
engine that raises MissingGreenlet -> HTTP 500, which is how linking an
*untitled* thread surfaced as "Failed to link thread to project". The method
must never force a lazy load: when messages aren't loaded it falls back to an
id-based title instead.
"""

import sqlalchemy
from unittest.mock import MagicMock
from uuid import uuid4

from src.models.thread import Thread
from src.models.chat_message import MessageRole


def _make_thread(title=None):
    thread = Thread()
    thread.title = title
    thread.id = uuid4()
    return thread


def test_generate_title_returns_existing_title():
    """An explicit title short-circuits and never touches messages."""
    thread = _make_thread(title="Existing Title")
    assert thread.generate_title() == "Existing Title"


def test_generate_title_falls_back_when_messages_unloaded(monkeypatch):
    """Regression: when `messages` is unloaded, generate_title must NOT read it
    (which would lazy-load and raise MissingGreenlet) — it returns the id-based
    fallback instead, even if a message happens to be attached."""
    thread = _make_thread(title=None)
    # A user message is present, but the relationship is reported unloaded, so
    # the guard must ignore it rather than lazy-loading.
    thread.messages = [MagicMock(role=MessageRole.USER, content="hello world")]

    fake_state = MagicMock()
    fake_state.unloaded = {"messages"}
    monkeypatch.setattr(sqlalchemy, "inspect", lambda obj: fake_state)

    title = thread.generate_title()
    assert title == f"Thread {str(thread.id)[:8]}"


def test_generate_title_uses_first_user_message_when_loaded(monkeypatch):
    """When messages are eager-loaded, the first user message drives the title."""
    thread = _make_thread(title=None)
    thread.messages = [
        MagicMock(role=MessageRole.ASSISTANT, content="hi there"),
        MagicMock(role=MessageRole.USER, content="What is RAG?"),
    ]

    fake_state = MagicMock()
    fake_state.unloaded = set()
    monkeypatch.setattr(sqlalchemy, "inspect", lambda obj: fake_state)
    monkeypatch.setattr(
        "src.services.threads.thread_title_generator.generate_title_sync",
        lambda content: f"title::{content}",
    )

    assert thread.generate_title() == "title::What is RAG?"
