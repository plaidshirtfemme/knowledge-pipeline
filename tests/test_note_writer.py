"""Tests for note_writer.py filename generation logic."""

import pytest
from note_writer import _build_filename


def test_nodate_placeholder_has_no_question_marks():
    """Windows forbids ? in filenames — regression test for [????-??-??] bug."""
    name = _build_filename(published=None, url="https://youtube.com/watch?v=abc", title="Some Title")
    assert "?" not in name


def test_nodate_used_when_no_date():
    name = _build_filename(published=None, url="https://youtube.com/watch?v=abc", title="Title")
    assert "[nodate]" in name


def test_date_used_when_valid():
    name = _build_filename(published="2026-01-15", url="https://youtube.com/watch?v=abc", title="Title")
    assert "[2026-01-15]" in name


def test_filename_sanitizes_forbidden_chars():
    name = _build_filename(published="2026-01-01", url="https://example.com/page", title='A/B: test <draft> file|name*')
    for char in r'\/:*?"<>|':
        assert char not in name


def test_filename_not_empty_when_no_title():
    name = _build_filename(published=None, url="https://youtube.com/watch?v=abc", title="")
    assert name.strip() != ""
    assert "untitled" in name
