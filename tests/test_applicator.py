"""Integration tests and stubs for the applicator node."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from hiremeAI.nodes.filter import GraphState
from hiremeAI.nodes.applicator import (
    detect_portal_type,
    handle_unknown_portal,
)


class TestPortalDetection:
    """Tests for portal type detection."""

    def test_detect_workday_from_url(self):
        """Test Workday detection from URL."""
        assert detect_portal_type("https://myworkdayjobs.com/job/123") == "workday"
        assert detect_portal_type("https://wd1.myworkdayjobs.com/job/456") == "workday"

    def test_detect_greenhouse_from_url(self):
        """Test Greenhouse detection from URL."""
        assert detect_portal_type("https://boards.greenhouse.io/job/123") == "greenhouse"
        assert detect_portal_type("https://app.greenhouse.io/job/456") == "greenhouse"

    def test_detect_lever_from_url(self):
        """Test Lever detection from URL."""
        assert detect_portal_type("https://jobs.lever.co/company/123") == "lever"
        assert detect_portal_type("https://lever.co/postings/456") == "lever"

    def test_detect_handshake_from_url(self):
        """Test Handshake detection from URL."""
        assert detect_portal_type("https://app.joinhandshake.com/jobs/123") == "handshake"
        assert detect_portal_type("https://joinhandshake.com/jobs/456") == "handshake"

    def test_detect_linkedin_from_url(self):
        """Test LinkedIn detection from URL."""
        assert detect_portal_type("https://www.linkedin.com/jobs/view/123") == "linkedin"

    def test_detect_indeed_from_url(self):
        """Test Indeed detection from URL."""
        assert detect_portal_type("https://indeed.com/viewjob?jk=123") == "indeed"
        assert detect_portal_type("https://smartapply.indeed.com/job/456") == "indeed"

    def test_detect_unknown_portal(self):
        """Test unknown portal returns None."""
        assert detect_portal_type("https://example.com/jobs/123") is None
        assert detect_portal_type("https://company.bamboohr.com/jobs/456") is None


@pytest.mark.asyncio
class TestApplicatorIntegration:
    """Integration tests for the applicator node.

    Note: These tests require Playwright to be installed.
    Run with: pytest tests/test_applicator.py -v
    """

    @pytest.fixture
    def sample_job_state(self):
        """Sample job state for applicator testing."""
        return {
            "job": {
                "id": "job-123",
                "title": "Software Engineer",
                "company": "TestCorp",
                "description": "Python job",
                "url": "https://boards.greenhouse.io/testcorp/jobs/123",
                "platform": "portal",
                "portal_type": "greenhouse",
            },
            "profile_context": "",
            "fit_score": 0.8,
            "resume_data": {},
            "cover_letter": "",
            "qa_answers": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
                "phone": "555-1234",
            },
            "pdf_path": "/tmp/test_resume.pdf",
            "status": "matched",
        }

    @patch("hiremeAI.nodes.applicator.get_browser")
    @patch("hiremeAI.nodes.applicator.detect_portal_type")
    @patch("hiremeAI.nodes.applicator.fill_greenhouse")
    @patch("hiremeAI.nodes.applicator.tracker")
    async def test_applicator_submits_successfully(
        self,
        mock_tracker,
        mock_fill,
        mock_detect,
        mock_browser,
        sample_job_state,
    ):
        """Test applicator successfully submits application."""
        # Mock setup
        mock_detect.return_value = "greenhouse"
        mock_fill.return_value = True

        mock_browser_instance = AsyncMock()
        mock_browser.return_value = mock_browser_instance

        from hiremeAI.nodes.applicator import applicator_node

        result = await applicator_node(sample_job_state)

        assert result["status"] == "submitted"
        mock_tracker.update_status.assert_called_once()

    @patch("hiremeAI.nodes.applicator.get_browser")
    @patch("hiremeAI.nodes.applicator.detect_portal_type")
    @patch("hiremeAI.nodes.applicator.handle_unknown_portal")
    @patch("hiremeAI.nodes.applicator.tracker")
    async def test_applicator_unknown_portal(
        self,
        mock_tracker,
        mock_handle,
        mock_detect,
        mock_browser,
        sample_job_state,
    ):
        """Test applicator handles unknown portal."""
        mock_detect.return_value = None  # Unknown portal

        # Set a URL that won't match any pattern
        sample_job_state["job"]["url"] = "https://unknown-portal.com/job/123"

        mock_browser_instance = AsyncMock()
        mock_browser.return_value = mock_browser_instance

        from hiremeAI.nodes.applicator import applicator_node

        result = await applicator_node(sample_job_state)

        assert result["status"] == "manual_review"
        mock_handle.assert_called_once()

    @patch("hiremeAI.nodes.applicator.get_browser")
    @patch("hiremeAI.nodes.applicator.tracker")
    async def test_applicator_handles_missing_pdf(
        self,
        mock_tracker,
        mock_browser,
        sample_job_state,
    ):
        """Test applicator handles missing PDF gracefully."""
        sample_job_state["pdf_path"] = ""

        from hiremeAI.nodes.applicator import applicator_node

        result = await applicator_node(sample_job_state)

        assert result["status"] == "failed"
        mock_browser.assert_not_called()


# Integration test runner stub
def run_integration_tests():
    """Placeholder for running full integration tests with real browser.

    To run actual integration tests:
    1. Install Playwright browsers: playwright install chromium
    2. Set HEADLESS=false in .env for debugging
    3. Use real credentials for testing portals

    Example:
    ```python
    import asyncio
    from hiremeAI.nodes.applicator import applicator_node

    async def test_real_submission():
        state = {
            "job": {...},
            "pdf_path": "path/to/resume.pdf",
            ...
        }
        result = await applicator_node(state)
        print(f"Result: {result['status']}")
    ```
    """
    print("Integration tests require Playwright setup.")
    print("Run: playwright install chromium")
    print("Set HEADLESS=false in .env to debug")
