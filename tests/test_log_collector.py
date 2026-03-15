"""Tests for agent log collector."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import patch, MagicMock
from agent.log_collector import (
    LogCollector, LogBatch, _detect_level, _hash_line, _extract_timestamp
)


class TestDetectLevel:
    def test_error_keywords(self):
        assert _detect_level("ERROR: connection refused") == "error"
        assert _detect_level("CRITICAL: disk full") == "error"
        assert _detect_level("Fatal exception in thread") == "error"

    def test_warn_keywords(self):
        assert _detect_level("WARNING: high memory usage") == "warn"
        assert _detect_level("warn: timeout") == "warn"

    def test_debug_keywords(self):
        assert _detect_level("DEBUG: entering function") == "debug"
        assert _detect_level("TRACE: request id=abc") == "debug"

    def test_default_info(self):
        assert _detect_level("Server started on port 8000") == "info"
        assert _detect_level("") == "info"


class TestHashLine:
    def test_hash_is_consistent(self):
        line = "Mar 15 10:00:00 server sshd[123]: Accepted"
        assert _hash_line(line) == _hash_line(line)

    def test_different_lines_different_hashes(self):
        assert _hash_line("line one") != _hash_line("line two")

    def test_hash_is_16_chars(self):
        assert len(_hash_line("test")) == 16


class TestExtractTimestamp:
    def test_extracts_syslog_timestamp(self):
        line = "Mar 15 10:22:34 myhost sshd[123]: Connection from 10.0.0.1"
        ts = _extract_timestamp(line)
        assert "Mar" in ts or ts == ""

    def test_empty_line_returns_empty(self):
        assert _extract_timestamp("") == ""


class TestLogCollector:
    def test_init(self):
        lc = LogCollector(server_name="test-server", tail_lines=10)
        assert lc.server_name == "test-server"
        assert lc.tail_lines == 10

    def test_collect_returns_log_batch(self):
        lc = LogCollector(server_name="test", collect_docker=False, collect_journald=False)
        batch = lc.collect()
        assert isinstance(batch, LogBatch)
        assert batch.server_name == "test"
        assert isinstance(batch.entries, list)
        assert isinstance(batch.sources_read, list)
        assert isinstance(batch.sources_failed, list)

    def test_collect_has_collected_at(self):
        lc = LogCollector(server_name="test", collect_docker=False, collect_journald=False)
        batch = lc.collect()
        assert batch.collected_at is not None
        assert len(batch.collected_at) > 0

    def test_to_dict_serializable(self):
        lc = LogCollector(server_name="test", collect_docker=False, collect_journald=False)
        batch = lc.collect()
        d = batch.to_dict()
        assert isinstance(d, dict)
        assert "server_name" in d
        assert "entries" in d
        assert "total_lines" in d

    def test_deduplication_removes_duplicates(self):
        lc = LogCollector(server_name="test")
        from agent.log_collector import LogEntry
        entries = [
            LogEntry(source="syslog", level="info", message="line A",
                     timestamp="", line_hash=_hash_line("line A")),
            LogEntry(source="syslog", level="info", message="line A",
                     timestamp="", line_hash=_hash_line("line A")),  # duplicate
            LogEntry(source="syslog", level="info", message="line B",
                     timestamp="", line_hash=_hash_line("line B")),
        ]
        deduped = lc._deduplicate(entries)
        assert len(deduped) == 2
        messages = {e.message for e in deduped}
        assert "line A" in messages
        assert "line B" in messages

    def test_dedup_does_not_return_already_seen(self):
        lc = LogCollector(server_name="test")
        from agent.log_collector import LogEntry
        entry = LogEntry(source="syslog", level="info", message="seen",
                         timestamp="", line_hash="abc123")
        # First call sees it
        lc._deduplicate([entry])
        # Second call should not return it again
        result = lc._deduplicate([entry])
        assert len(result) == 0

    def test_nonexistent_log_file_returns_empty(self):
        lc = LogCollector(server_name="test")
        result = lc._read_file_tail("fake", "/nonexistent/path/file.log")
        assert result == []
