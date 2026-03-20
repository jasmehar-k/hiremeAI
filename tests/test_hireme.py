"""Test suite for hireme."""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from hiremeAI.nodes.filter import score_fit, GraphState, filter_node
from hiremeAI.nodes.discovery import create_job_listing, detect_portal_type
from hiremeAI import tracker
from hiremeAI.config import FIT_THRESHOLD


@pytest.fixture(autouse=True)
def clear_tracker_state():
    """Keep tracker-backed tests isolated from one another."""
    tracker.init_db()
    conn = tracker.get_connection()
    try:
        conn.execute("DELETE FROM applications")
        conn.commit()
    finally:
        conn.close()


class TestDiscovery:
    """Tests for job discovery and portal detection."""

    def test_detect_portal_type_workday(self):
        url = "https://wd3.myworkdayjobs.com/en-US/company/job/123"
        assert detect_portal_type(url) == "workday"

    def test_detect_portal_type_greenhouse(self):
        url = "https://boards.greenhouse.io/company/job/123"
        assert detect_portal_type(url) == "greenhouse"

    def test_detect_portal_type_lever(self):
        url = "https://jobs.lever.co/company/123"
        assert detect_portal_type(url) == "lever"

    def test_detect_portal_type_handshake(self):
        url = "https://app.joinhandshake.com/jobs/123"
        assert detect_portal_type(url) == "handshake"

    def test_detect_portal_type_linkedin(self):
        url = "https://www.linkedin.com/jobs/view/123"
        assert detect_portal_type(url) == "linkedin"

    def test_detect_portal_type_indeed(self):
        url = "https://www.indeed.com/viewjob?jk=123"
        assert detect_portal_type(url) == "indeed"

    def test_detect_portal_type_unknown(self):
        url = "https://example.com/careers/job/123"
        assert detect_portal_type(url) is None

    def test_create_job_listing(self):
        job = create_job_listing(
            company="Test Company",
            title="Software Engineer",
            description="We are looking for a Python developer",
            url="https://example.com/job/123",
            platform="portal",
            requires_cover_letter=True,
        )
        assert job["company"] == "Test Company"
        assert job["title"] == "Software Engineer"
        assert job["platform"] == "portal"
        assert job["requires_cover_letter"] is True
        assert job["id"] is not None


class TestTracker:
    """Tests for the SQLite tracker."""

    @pytest.fixture
    def test_app(self):
        """Create a test application in the tracker."""
        app_id = tracker.log_application(
            job_id="test-123",
            company="Test Company",
            title="Software Engineer",
            url="https://test.com/job/123",
            platform="portal",
            portal_type="greenhouse",
        )
        return app_id

    def test_log_application(self, test_app):
        assert test_app is not None
        assert test_app > 0

    def test_get_application_by_url(self, test_app):
        app = tracker.get_application_by_url("https://test.com/job/123")
        assert app is not None
        assert app["company"] == "Test Company"

    def test_update_status(self, test_app):
        tracker.update_status(
            url="https://test.com/job/123",
            status="submitted",
            fit_score=0.8,
            fit_reason="Good fit",
        )
        app = tracker.get_application_by_url("https://test.com/job/123")
        assert app["status"] == "submitted"
        assert app["fit_score"] == 0.8

    def test_is_url_applied(self, test_app):
        # Initially not applied
        assert not tracker.is_url_applied("https://test.com/job/123")

        # After marking as submitted
        tracker.update_status("https://test.com/job/123", "submitted")
        assert tracker.is_url_applied("https://test.com/job/123")


class TestFilter:
    """Tests for the fit scoring filter."""

    @pytest.mark.asyncio
    @patch("hiremeAI.nodes.filter.get_llm")
    async def test_score_fit_high_score(self, mock_get_llm):
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '{"score": 0.8, "reason": "Good match", "relevant_skills": ["Python", "React"]}'
        mock_llm.invoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = score_fit(
            job={"title": "Python Developer", "description": "Need Python dev"},
            profile_context="Experienced Python developer",
        )

        assert result["score"] >= FIT_THRESHOLD

    @pytest.mark.asyncio
    @patch("hiremeAI.nodes.filter.get_llm")
    async def test_score_fit_low_score(self, mock_get_llm):
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '{"score": 0.3, "reason": "Poor match", "relevant_skills": []}'
        mock_llm.invoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = score_fit(
            job={"title": "Java Engineer", "description": "Need Java dev"},
            profile_context="Python developer",
        )

        assert result["score"] < FIT_THRESHOLD


class TestConfig:
    """Tests for configuration."""

    def test_fit_threshold(self):
        assert FIT_THRESHOLD == 0.65

    def test_portal_url_patterns(self):
        from hiremeAI.config import PORTAL_URL_PATTERNS
        assert "workday" in PORTAL_URL_PATTERNS
        assert "greenhouse" in PORTAL_URL_PATTERNS
        assert "lever" in PORTAL_URL_PATTERNS
