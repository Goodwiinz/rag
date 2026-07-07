"""Redis buffer for resumable agent SSE streams.

One Redis list per run (``agent:stream:{stream_id}``) holds JSON
``{seq, frame}`` entries; ``agent:stream:active:{thread_id}`` points at the
currently active run. TTL 3600 matches the job store.

ponytail: poll-follow over a plain list; swap to pub/sub if replay latency
matters.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from src.services.agent.job_store import get_redis

_TTL_SECONDS = 3600


@dataclass
class BufferedFrame:
    seq: int
    frame: str


def _buffer_key(stream_id: str) -> str:
    return f"agent:stream:{stream_id}"


def _active_key(thread_id: str) -> str:
    return f"agent:stream:active:{thread_id}"


async def start_stream(thread_id: str) -> str:
    """Mint a stream id and mark it as the thread's active run."""
    stream_id = str(uuid.uuid4())
    redis = await get_redis()
    if redis is not None:
        await redis.set(_active_key(thread_id), stream_id, ex=_TTL_SECONDS)
    return stream_id


async def append(stream_id: str, seq: int, frame: str) -> None:
    """Append one frame to the stream's replay buffer."""
    redis = await get_redis()
    if redis is None:
        return
    key = _buffer_key(stream_id)
    await redis.rpush(key, json.dumps({"seq": seq, "frame": frame}))
    await redis.expire(key, _TTL_SECONDS)


async def read_after(stream_id: str, after_seq: int) -> list[BufferedFrame]:
    """Return buffered frames with seq > after_seq (empty if unknown sid)."""
    redis = await get_redis()
    if redis is None:
        return []
    raw = await redis.lrange(_buffer_key(stream_id), 0, -1)
    frames = [BufferedFrame(**json.loads(item)) for item in raw]
    return [f for f in frames if f.seq > after_seq]


async def active_stream_id(thread_id: str) -> str | None:
    """Return the thread's active stream id, if any."""
    redis = await get_redis()
    if redis is None:
        return None
    return await redis.get(_active_key(thread_id))


async def finish_stream(thread_id: str, stream_id: str) -> None:
    """Clear the active pointer only if it still belongs to this run."""
    redis = await get_redis()
    if redis is None:
        return
    if await redis.get(_active_key(thread_id)) == stream_id:
        await redis.delete(_active_key(thread_id))
