"""Tests for configuration compatibility helpers."""

from pathlib import Path

from hiremeAI import config


def test_resolve_db_path_prefers_canonical(tmp_path, monkeypatch):
    """Canonical database path should win when it already exists."""
    canonical = tmp_path / "hireme.db"
    legacy = tmp_path / "envoy.db"
    canonical.write_text("canonical", encoding="utf-8")
    legacy.write_text("legacy", encoding="utf-8")

    monkeypatch.setattr(config, "CANONICAL_DB_PATH", canonical)
    monkeypatch.setattr(config, "LEGACY_DB_PATH", legacy)

    assert config.resolve_db_path() == canonical


def test_resolve_db_path_migrates_legacy_database(tmp_path, monkeypatch):
    """Legacy database should be copied to the canonical location when needed."""
    canonical = tmp_path / "hireme.db"
    legacy = tmp_path / "envoy.db"
    legacy.write_text("legacy-data", encoding="utf-8")

    monkeypatch.setattr(config, "CANONICAL_DB_PATH", canonical)
    monkeypatch.setattr(config, "LEGACY_DB_PATH", legacy)

    resolved = config.resolve_db_path()

    assert resolved == canonical
    assert canonical.read_text(encoding="utf-8") == "legacy-data"
