"""Fit scoring filter - uses LLM to score job fit."""

import json
from typing import TypedDict

from langchain_openrouter import ChatOpenRouter

from envoy import config
from envoy.profile import retriever
from envoy import tracker


class GraphState(TypedDict):
    """Graph state passed between all nodes."""
    job: dict  # JobListing
    profile_context: str
    fit_score: float
    resume_data: dict | None
    cover_letter: str
    qa_answers: dict[str, str]
    pdf_path: str
    status: str  # "matched" | "skipped" | "submitted" | "failed" | "manual_review"


def get_llm():
    """Get the LLM client."""
    return ChatOpenRouter(
        model=config.LLM_MODEL,
        api_key=config.OPENROUTER_API_KEY,
        base_url=config.LLM_BASE_URL,
    )


def score_fit(job: dict, profile_context: str) -> dict:
    """
    Use LLM to score how well the profile fits the job description.

    Returns:
        dict with keys: score (float), reason (str), relevant_skills (list[str])
    """
    llm = get_llm()

    prompt = f"""You are a career advisor helping a student assess their fit for a job opportunity.

Job Description:
Title: {job.get('title', 'N/A')}
Company: {job.get('company', 'N/A')}
Description: {job.get('description', 'N/A')}

Candidate Profile Context:
{profile_context}

Based on the job description and candidate profile, evaluate how well the candidate fits this role.

Respond with a JSON object containing:
- "score": A float between 0 and 1 representing fit level
- "reason": A brief explanation (1-2 sentences) of why this score
- "relevant_skills": A list of skills from the profile that match the job requirements

Return ONLY valid JSON, no other text."""

    response = llm.invoke(prompt)
    content = response.content.strip()

    # Try to parse JSON from response
    try:
        # Handle potential markdown code block formatting
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        result = json.loads(content.strip())
        return {
            "score": float(result.get("score", 0.5)),
            "reason": str(result.get("reason", "")),
            "relevant_skills": list(result.get("relevant_skills", [])),
        }
    except (json.JSONDecodeError, ValueError) as e:
        # Fallback: return neutral score on parse error
        print(f"Warning: Failed to parse LLM response: {e}")
        return {
            "score": 0.5,
            "reason": "Unable to determine fit score due to parsing error.",
            "relevant_skills": [],
        }


def filter_node(state: GraphState) -> GraphState:
    """
    Filter node - scores job fit and decides whether to proceed.

    Retrieves relevant profile context, scores the job, and updates
    the graph state with the fit score and decision.
    """
    job = state["job"]

    # Retrieve relevant profile context via RAG
    profile_context = retriever.retrieve(
        job.get("description", ""),
        types=["experience", "project", "skill"],
        k=5,
    )

    state["profile_context"] = profile_context

    # Score the fit
    scoring_result = score_fit(job, profile_context)
    fit_score = scoring_result["score"]

    # Update state
    state["fit_score"] = fit_score
    state["status"] = "matched" if fit_score >= config.FIT_THRESHOLD else "skipped"

    # Log the result to tracker
    tracker.update_status(
        url=job["url"],
        status=state["status"],
        fit_score=fit_score,
        fit_reason=scoring_result["reason"],
    )

    return state