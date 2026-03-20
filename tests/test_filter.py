"""Tests for the filter node."""

import pytest
from unittest.mock import patch, MagicMock

from hiremeAI.nodes.filter import GraphState, score_fit, filter_node


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    return '{"score": 0.75, "reason": "Good technical fit", "relevant_skills": ["Python", "React"]}'


def test_score_fit_parse_success(mock_llm_response):
    """Test successful parsing of LLM response."""
    with patch("hiremeAI.nodes.filter.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = mock_llm_response
        mock_llm.invoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = score_fit(
            job={"title": "Software Engineer", "description": "Python React", "company": "Test"},
            profile_context="Experienced Python developer",
        )

        assert result["score"] == 0.75
        assert result["reason"] == "Good technical fit"
        assert "Python" in result["relevant_skills"]


def test_score_fit_parse_failure():
    """Test handling of malformed LLM response."""
    with patch("hiremeAI.nodes.filter.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "This is not JSON"
        mock_llm.invoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = score_fit(
            job={"title": "Engineer", "description": "desc", "company": "Test"},
            profile_context="context",
        )

        # Should fallback to neutral score
        assert result["score"] == 0.5
        assert "error" in result["reason"].lower()


@patch("hiremeAI.nodes.filter.get_llm")
@patch("hiremeAI.nodes.filter.retriever")
@patch("hiremeAI.nodes.filter.tracker")
@patch("hiremeAI.nodes.filter.config", create=True)
def test_filter_node_above_threshold(mock_config, mock_tracker, mock_retriever, mock_get_llm):
    """Test filter node when job is above threshold."""
    # Setup mocks
    mock_config.FIT_THRESHOLD = 0.65

    mock_retriever.retrieve.return_value = "Relevant experience"
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '{"score": 0.8, "reason": "Great fit", "skills": []}'
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    # Input state
    state: GraphState = {
        "job": {
            "id": "job-1",
            "title": "SWE",
            "company": "Test",
            "description": "Python job",
            "url": "https://example.com",
            "platform": "linkedin",
            "portal_type": None,
        },
        "profile_context": "",
        "fit_score": 0.0,
        "resume_data": {},
        "cover_letter": "",
        "qa_answers": {},
        "pdf_path": "",
        "status": "pending",
    }

    result = filter_node(state)

    assert result["status"] == "matched"
    assert result["fit_score"] >= 0.65


@patch("hiremeAI.nodes.filter.get_llm")
@patch("hiremeAI.nodes.filter.retriever")
@patch("hiremeAI.nodes.filter.tracker")
@patch("hiremeAI.nodes.filter.config", create=True)
def test_filter_node_below_threshold(mock_config, mock_tracker, mock_retriever, mock_get_llm):
    """Test filter node when job is below threshold."""
    mock_config.FIT_THRESHOLD = 0.65

    mock_retriever.retrieve.return_value = "Some experience"
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '{"score": 0.3, "reason": "Not enough experience", "skills": []}'
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    state: GraphState = {
        "job": {
            "id": "job-2",
            "title": "Senior DevOps",
            "company": "Test",
            "description": "Kubernetes AWS",
            "url": "https://example.com/2",
            "platform": "indeed",
            "portal_type": None,
        },
        "profile_context": "",
        "fit_score": 0.0,
        "resume_data": {},
        "cover_letter": "",
        "qa_answers": {},
        "pdf_path": "",
        "status": "pending",
    }

    result = filter_node(state)

    assert result["status"] == "skipped"
    assert result["fit_score"] < 0.65
