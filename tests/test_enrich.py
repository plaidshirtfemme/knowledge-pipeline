"""Tests for enrich.py — logic that doesn't call the Anthropic API."""

import json
from unittest.mock import MagicMock, patch
import pytest
import anthropic

from enrich import _strip_markdown_fences, enrich


def test_strip_plain_json():
    raw = '{"title": "test"}'
    assert _strip_markdown_fences(raw) == '{"title": "test"}'


def test_strip_json_fences():
    raw = "```json\n{\"title\": \"test\"}\n```"
    assert _strip_markdown_fences(raw) == '{"title": "test"}'


def test_strip_bare_fences():
    raw = "```\n{\"title\": \"test\"}\n```"
    assert _strip_markdown_fences(raw) == '{"title": "test"}'


def test_enrich_falls_back_to_inbox_on_unknown_folder():
    fake_response = {
        "title": "Test",
        "summary": "Test summary",
        "concepts": [],
        "instructions": [],
        "entities": [],
        "tags": ["design"],
        "insights": [],
        "published_date": None,
        "author": None,
        "folder": "nonexistent_folder_xyz",
    }
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(fake_response))]

    with patch("enrich._client") as mock_client:
        mock_client.messages.create.return_value = mock_message
        result = enrich("some text")

    assert result["folder"] == "inbox"


def test_enrich_uses_hint_title_when_no_title():
    fake_response = {
        "title": None,
        "summary": "s",
        "concepts": [],
        "instructions": [],
        "entities": [],
        "tags": [],
        "insights": [],
        "published_date": None,
        "author": None,
        "folder": "inbox",
    }
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(fake_response))]

    with patch("enrich._client") as mock_client:
        mock_client.messages.create.return_value = mock_message
        result = enrich("some text", hint_title="My Hint")

    assert result["title"] == "My Hint"


def test_enrich_retries_on_connection_error():
    """APIConnectionError should be retried, not crash immediately."""
    fake_response = {
        "title": "Test", "summary": "s", "concepts": [], "instructions": [],
        "entities": [], "tags": [], "insights": [],
        "published_date": None, "author": None, "folder": "inbox",
    }
    mock_ok = MagicMock()
    mock_ok.content = [MagicMock(text=json.dumps(fake_response))]

    with patch("enrich._client") as mock_client, patch("enrich.time.sleep"):
        mock_client.messages.create.side_effect = [
            anthropic.APIConnectionError(request=MagicMock()),
            mock_ok,
        ]
        result = enrich("some text")

    assert result["folder"] == "inbox"
    assert mock_client.messages.create.call_count == 2


def test_enrich_raises_after_all_retries_fail():
    """Should raise RuntimeError after MAX_RETRIES failed attempts."""
    with patch("enrich._client") as mock_client, patch("enrich.time.sleep"):
        mock_client.messages.create.side_effect = anthropic.APIConnectionError(
            request=MagicMock()
        )
        with pytest.raises(RuntimeError, match="попыток"):
            enrich("some text")


def test_enrich_valid_folder_is_kept():
    fake_response = {
        "title": "Figma tricks",
        "summary": "About Figma",
        "concepts": [],
        "instructions": [],
        "entities": [],
        "tags": ["figma"],
        "insights": [],
        "published_date": None,
        "author": None,
        "folder": "figma",
    }
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(fake_response))]

    with patch("enrich._client") as mock_client:
        mock_client.messages.create.return_value = mock_message
        result = enrich("Figma tutorial text")

    assert result["folder"] == "figma"
