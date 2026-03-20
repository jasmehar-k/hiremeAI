"""Tests for the generation nodes."""

import json
import pytest
from unittest.mock import patch, MagicMock

from hiremeAI.nodes.filter import GraphState
from hiremeAI.nodes.generation import (
    resume_writer_node,
    cover_letter_writer_node,
    generate_qa_answer,
)


@pytest.fixture
def sample_job():
    """Sample job for testing."""
    return {
        "id": "job-123",
        "title": "Software Engineer Intern",
        "company": "TechCorp",
        "description": "We are looking for a software engineer to work on Python and React.",
        "url": "https://techcorp.com/jobs/123",
        "platform": "linkedin",
        "portal_type": "greenhouse",
        "requires_cover_letter": False,
    }


@pytest.fixture
def sample_state(sample_job):
    """Sample graph state for testing."""
    return {
        "job": sample_job,
        "profile_context": "",
        "fit_score": 0.8,
        "resume_data": {},
        "cover_letter": "",
        "qa_answers": {},
        "pdf_path": "",
        "status": "matched",
    }


@patch("hiremeAI.nodes.generation.get_llm")
@patch("hiremeAI.nodes.generation.retriever")
def test_resume_writer_node(mock_retriever, mock_get_llm, sample_state):
    """Test resume writer generates valid JSON."""
    mock_retriever.retrieve_for_resume.return_value = "Experience: Python developer"

    mock_llm = MagicMock()
    resume_json = json.dumps({
        "name": "John Doe",
        "contact": {"email": "john@example.com", "phone": "555-1234", "location": "Toronto, ON"},
        "summary": "Experienced developer",
        "experience": [{"title": "Dev", "company": "Corp", "dates": "2024", "location": "Toronto", "highlights": ["Built things"]}],
        "projects": [],
        "education": [{"degree": "BS CS", "institution": "University", "dates": "2024-2028", "details": []}],
        "skills": {"languages": ["Python"], "frameworks": [], "tools": [], "soft": []}
    })
    mock_response = MagicMock()
    mock_response.content = resume_json
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    result = resume_writer_node(sample_state)

    assert "resume_data" in result
    assert result["resume_data"]["name"] == "John Doe"
    assert "experience" in result["resume_data"]


@patch("hiremeAI.nodes.generation.get_llm")
@patch("hiremeAI.nodes.generation.retriever")
def test_resume_writer_node_handles_bad_json(mock_retriever, mock_get_llm, sample_state):
    """Test resume writer handles malformed JSON gracefully."""
    mock_retriever.retrieve_for_resume.return_value = "Experience"
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "This is not JSON"
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    result = resume_writer_node(sample_state)

    # Should return empty dict on parse error
    assert result["resume_data"] == {}


@patch("hiremeAI.nodes.generation.get_llm")
def test_cover_letter_writer_node_skips_when_not_required(mock_get_llm, sample_state):
    """Test cover letter writer skips when not required."""
    # Set requires_cover_letter to False
    sample_state["job"]["requires_cover_letter"] = False

    result = cover_letter_writer_node(sample_state)

    assert result["cover_letter"] == ""
    mock_get_llm.return_value.invoke.assert_not_called()


@patch("hiremeAI.nodes.generation.get_llm")
@patch("hiremeAI.nodes.generation.retriever")
def test_cover_letter_writer_node_generates_letter(mock_retriever, mock_get_llm, sample_state):
    """Test cover letter writer generates when required."""
    sample_state["job"]["requires_cover_letter"] = True

    mock_retriever.retrieve_for_cover_letter.return_value = "My experience"
    mock_retriever.retrieve_writing_samples.return_value = "My writing style"

    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Dear Hiring Manager,\n\nI am excited to apply..."
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    result = cover_letter_writer_node(sample_state)

    assert result["cover_letter"] != ""
    assert "Dear" in result["cover_letter"]


@patch("hiremeAI.nodes.generation.get_llm")
@patch("hiremeAI.nodes.generation.retriever")
def test_generate_qa_answer_short(mock_retriever, mock_get_llm):
    """Test Q&A answer generation for short questions."""
    mock_retriever.retrieve_for_qa.return_value = "Relevant experience"

    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Yes, I have 3 years of experience."
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    answer = generate_qa_answer("Do you have Python experience?", "Python job")

    assert answer != ""
    assert len(answer.split()) <= 60  # Short answer limit


@patch("hiremeAI.nodes.generation.get_llm")
@patch("hiremeAI.nodes.generation.retriever")
def test_generate_qa_answer_long_form(mock_retriever, mock_get_llm):
    """Test Q&A answer generation for long-form questions."""
    mock_retriever.retrieve_for_qa.return_value = "Experience details"

    mock_llm = MagicMock()
    mock_response = MagicMock()
    # Generate a response longer than max_words
    long_answer = " ".join(["word"] * 350)
    mock_response.content = long_answer
    mock_llm.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    question = "Tell us about a time when you had to deal with a difficult technical problem and how you solved it. " * 3
    answer = generate_qa_answer(question, "job description")

    # Should be truncated to 300 words
    assert len(answer.split()) <= 310  # Some tolerance for truncation logic
