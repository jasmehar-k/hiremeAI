"""Tests for the SQLite tracker."""

import tempfile
import os
from pathlib import Path

import pytest

# Override DB path for tests
TEST_DB = tempfile.mktemp(suffix=".db")


# Mock config before importing tracker
import hiremeAI.config as config_module
original_db_path = config_module.DB_PATH


def setup_module(module):
    """Set up test fixtures."""
    # Patch DB path
    config_module.DB_PATH = Path(TEST_DB)


def teardown_module(module):
    """Clean up test fixtures."""
    config_module.DB_PATH = original_db_path
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


@pytest.fixture(autouse=True)
def clear_applications_table():
    """Isolate tracker tests by clearing the SQLite table before each case."""
    from hiremeAI import tracker

    tracker.init_db()
    conn = tracker.get_connection()
    try:
        conn.execute("DELETE FROM applications")
        conn.commit()
    finally:
        conn.close()


def test_init_db():
    """Test database initialization."""
    from hiremeAI import tracker

    # Should not raise
    tracker.init_db()

    # Check that table exists
    conn = tracker.get_connection()
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='applications'"
    )
    result = cursor.fetchone()
    conn.close()

    assert result is not None


def test_log_application():
    """Test logging a new application."""
    from hiremeAI import tracker

    app_id = tracker.log_application(
        job_id="test-job-123",
        company="Test Company",
        title="Software Engineer",
        url="https://example.com/job/123",
        platform="linkedin",
        portal_type=None,
        status="pending",
        fit_score=0.8,
        fit_reason="Good match",
    )

    assert app_id > 0

    # Verify it was logged
    app = tracker.get_application_by_url("https://example.com/job/123")
    assert app is not None
    assert app["company"] == "Test Company"
    assert app["status"] == "pending"
    assert app["fit_score"] == 0.8


def test_update_status():
    """Test updating application status."""
    from hiremeAI import tracker

    # Create an application
    tracker.log_application(
        job_id="test-job-456",
        company="Another Company",
        title="Backend Engineer",
        url="https://example.com/job/456",
        platform="indeed",
        status="pending",
    )

    # Update status
    tracker.update_status(
        url="https://example.com/job/456",
        status="submitted",
    )

    # Verify update
    app = tracker.get_application_by_url("https://example.com/job/456")
    assert app["status"] == "submitted"
    assert app["applied_at"] is not None


def test_is_url_applied():
    """Test checking if URL was already applied."""
    from hiremeAI import tracker

    # Clean slate
    url = "https://example.com/job/789"

    # Not applied yet
    assert not tracker.is_url_applied(url)

    # Log and update to submitted
    tracker.log_application(
        job_id="test-job-789",
        company="Company",
        title="Role",
        url=url,
        platform="handshake",
        status="pending",
    )
    tracker.update_status(url, "submitted")

    # Should now be considered applied
    assert tracker.is_url_applied(url)


def test_get_applications_by_status():
    """Test filtering applications by status."""
    from hiremeAI import tracker

    # Create applications with different statuses
    tracker.log_application(
        job_id="job-1",
        company="Company 1",
        title="Role 1",
        url="https://example.com/job/1",
        platform="linkedin",
        status="submitted",
    )
    tracker.log_application(
        job_id="job-2",
        company="Company 2",
        title="Role 2",
        url="https://example.com/job/2",
        platform="linkedin",
        status="skipped",
    )
    tracker.log_application(
        job_id="job-3",
        company="Company 3",
        title="Role 3",
        url="https://example.com/job/3",
        platform="linkedin",
        status="submitted",
    )

    submitted = tracker.get_applications(status="submitted")
    assert len(submitted) == 2

    skipped = tracker.get_applications(status="skipped")
    assert len(skipped) == 1
