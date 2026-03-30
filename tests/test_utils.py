"""Tests for backend.utils — JSON parsing from LLM output."""

from backend.utils import parse_json_fenced


class TestParseJsonFenced:
    def test_raw_json(self):
        assert parse_json_fenced('{"a": 1}') == {"a": 1}

    def test_json_with_whitespace(self):
        assert parse_json_fenced('  \n {"a": 1} \n  ') == {"a": 1}

    def test_fenced_json_block(self):
        text = '```json\n{"key": "value"}\n```'
        assert parse_json_fenced(text) == {"key": "value"}

    def test_fenced_block_without_json_tag(self):
        text = '```\n{"key": "value"}\n```'
        assert parse_json_fenced(text) == {"key": "value"}

    def test_fenced_with_surrounding_text(self):
        text = 'Here is the result:\n```json\n{"x": 42}\n```\nDone.'
        assert parse_json_fenced(text) == {"x": 42}

    def test_invalid_json_returns_fallback(self):
        assert parse_json_fenced("not json", fallback={"default": True}) == {"default": True}

    def test_invalid_json_default_fallback(self):
        assert parse_json_fenced("not json") == {}

    def test_empty_string(self):
        assert parse_json_fenced("", fallback={"empty": True}) == {"empty": True}

    def test_nested_json(self):
        text = '```json\n{"tasks": [{"id": "1", "deps": []}]}\n```'
        result = parse_json_fenced(text)
        assert result["tasks"][0]["id"] == "1"

    def test_invalid_fenced_json_returns_fallback(self):
        text = '```json\n{invalid json}\n```'
        assert parse_json_fenced(text, fallback={"fb": 1}) == {"fb": 1}
