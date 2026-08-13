"""R2-H4: in-process confirm-claim fallback for Redis outages.

stream_confirm_event_generator's HITL confirm claim was skipped entirely
when Redis was unavailable, so two concurrent /stream/confirm requests
could both resume the same interrupt and run a destructive tool twice.
``_acquire_local_confirm_claim`` / ``_release_local_confirm_claim`` provide a
per-process fallback claim (partial protection — single worker only).
"""

from src.api.agent.streaming import (
    _acquire_local_confirm_claim,
    _local_confirm_claims,
    _release_local_confirm_claim,
)


def setup_function(_fn):
    _local_confirm_claims.clear()


def test_second_acquire_of_same_key_fails():
    key = "hitl-confirm-claim:thread-1:ckpt-1"
    assert _acquire_local_confirm_claim(key, now=0.0) is True
    assert _acquire_local_confirm_claim(key, now=1.0) is False


def test_acquirable_again_after_ttl_expiry():
    key = "hitl-confirm-claim:thread-1:ckpt-1"
    assert _acquire_local_confirm_claim(key, now=0.0) is True
    # Just before TTL (330s): still claimed.
    assert _acquire_local_confirm_claim(key, now=329.0) is False
    # Past TTL: claimable again.
    assert _acquire_local_confirm_claim(key, now=331.0) is True


def test_release_frees_the_key_immediately():
    key = "hitl-confirm-claim:thread-1:ckpt-1"
    assert _acquire_local_confirm_claim(key, now=0.0) is True
    _release_local_confirm_claim(key)
    assert _acquire_local_confirm_claim(key, now=0.5) is True


def test_release_of_absent_key_is_a_noop():
    _release_local_confirm_claim("no-such-key")  # must not raise


def test_different_keys_do_not_collide():
    assert _acquire_local_confirm_claim("key-a", now=0.0) is True
    assert _acquire_local_confirm_claim("key-b", now=0.0) is True
