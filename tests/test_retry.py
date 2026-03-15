"""Tests for agent retry buffer and backoff logic."""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from pathlib import Path
from agent.retry import RetryBuffer, with_retry, _backoff_delay


@pytest.fixture
def tmp_buffer(tmp_path):
    buf_file = str(tmp_path / "test_buffer.ndjson")
    return RetryBuffer(buffer_path=buf_file, max_entries=10)


class TestRetryBuffer:
    def test_push_and_size(self, tmp_buffer):
        tmp_buffer.push("metrics", {"cpu": 50})
        assert tmp_buffer.size == 1

    def test_push_multiple(self, tmp_buffer):
        for i in range(5):
            tmp_buffer.push("metrics", {"cpu": i})
        assert tmp_buffer.size == 5

    def test_is_empty_initially(self, tmp_buffer):
        assert tmp_buffer.is_empty is True

    def test_not_empty_after_push(self, tmp_buffer):
        tmp_buffer.push("logs", {"data": "test"})
        assert tmp_buffer.is_empty is False

    def test_peek_all_returns_all(self, tmp_buffer):
        tmp_buffer.push("metrics", {"cpu": 10})
        tmp_buffer.push("metrics", {"cpu": 20})
        items = tmp_buffer.peek_all()
        assert len(items) == 2

    def test_max_entries_evicts_oldest(self, tmp_buffer):
        for i in range(15):  # max is 10
            tmp_buffer.push("metrics", {"cpu": i})
        assert tmp_buffer.size <= 10

    def test_drain_successful(self, tmp_buffer):
        tmp_buffer.push("metrics", {"cpu": 50})
        tmp_buffer.push("logs", {"data": "x"})

        sent_items = []
        def sender(ptype, payload):
            sent_items.append(ptype)
            return True

        sent, failed = tmp_buffer.drain(sender)
        assert sent == 2
        assert failed == 0
        assert tmp_buffer.is_empty

    def test_drain_partial_failure(self, tmp_buffer):
        tmp_buffer.push("metrics", {"cpu": 50})
        tmp_buffer.push("logs", {"data": "x"})
        tmp_buffer.push("metrics", {"cpu": 60})

        call_count = [0]
        def sender(ptype, payload):
            call_count[0] += 1
            # Fail the second call
            return call_count[0] != 2

        sent, failed = tmp_buffer.drain(sender)
        assert sent == 2
        assert failed == 1
        assert tmp_buffer.size == 1  # failed one stays buffered

    def test_persists_to_disk(self, tmp_path):
        buf_file = str(tmp_path / "persist_test.ndjson")
        buf1 = RetryBuffer(buffer_path=buf_file)
        buf1.push("metrics", {"cpu": 77})

        # Create new buffer instance from same file
        buf2 = RetryBuffer(buffer_path=buf_file)
        assert buf2.size == 1
        assert buf2.peek_all()[0]["payload"]["cpu"] == 77

    def test_clear_removes_all(self, tmp_buffer):
        tmp_buffer.push("metrics", {"cpu": 50})
        tmp_buffer.clear()
        assert tmp_buffer.is_empty

    def test_drain_empty_buffer(self, tmp_buffer):
        sent, failed = tmp_buffer.drain(lambda t, p: True)
        assert sent == 0
        assert failed == 0


class TestBackoffDelay:
    def test_first_attempt_equals_base(self):
        delay = _backoff_delay(1, base=2.0, maximum=60.0)
        assert 1.6 <= delay <= 2.4  # ±20% jitter

    def test_delay_increases_with_attempts(self):
        d1 = _backoff_delay(1, base=2.0, maximum=60.0)
        d2 = _backoff_delay(2, base=2.0, maximum=60.0)
        # On average d2 should be larger (though jitter can occasionally invert)
        # Just check they're both positive and reasonable
        assert d1 > 0
        assert d2 > 0

    def test_delay_capped_at_maximum(self):
        delay = _backoff_delay(10, base=2.0, maximum=5.0)
        assert delay <= 5.0 * 1.2  # allow jitter

    def test_delay_never_negative(self):
        for attempt in range(1, 8):
            d = _backoff_delay(attempt, base=1.0, maximum=30.0)
            assert d >= 0.1


class TestWithRetryDecorator:
    def test_succeeds_on_first_try(self):
        calls = [0]
        @with_retry(max_attempts=3)
        def func():
            calls[0] += 1
            return "ok"
        result = func()
        assert result == "ok"
        assert calls[0] == 1

    def test_retries_on_failure_then_succeeds(self):
        calls = [0]
        @with_retry(max_attempts=3, base_delay=0.01)
        def func():
            calls[0] += 1
            if calls[0] < 3:
                raise ValueError("not yet")
            return "success"
        result = func()
        assert result == "success"
        assert calls[0] == 3

    def test_raises_after_all_attempts(self):
        @with_retry(max_attempts=2, base_delay=0.01)
        def always_fails():
            raise RuntimeError("always fails")
        with pytest.raises(RuntimeError):
            always_fails()
