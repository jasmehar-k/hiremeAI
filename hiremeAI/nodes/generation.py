"""Generation nodes - resume, cover letter, and Q&A answer generation."""

import json
from typing import TypedDict

from langchain_openrouter import ChatOpenRouter

from hiremeAI import config
from hiremeAI.nodes.filter import GraphState
from hiremeAI.profile import retriever


def get_llm():
    """Get the LLM client."""
    return ChatOpenRouter(
        model=config.LLM_MODEL,
        api_key=config.OPENROUTER_API_KEY,
        base_url=config.LLM_BASE_URL,
    )


def resume_writer_node(state: GraphState) -> GraphState:
    """
    Generate a tailored resume for the job using RAG.

    Retrieves relevant profile experience, projects, and skills,
    then prompts the LLM to rewrite bullet points using JD language.
    """
    job = state["job"]
    jd = job.get("description", "")

    # Retrieve relevant profile data for resume
    profile_context = retriever.retrieve_for_resume(jd)

    llm = get_llm()

    prompt = f"""You are a resume writer helping a candidate tailor their resume for a specific job.

Job Description:
{jd}

Candidate Profile:
{profile_context}

Generate a tailored resume in JSON format with the following structure:
{{
    "name": "Full Name",
    "contact": {{"email": "email", "phone": "phone", "location": "city, province"}},
    "summary": "2-3 sentence professional summary",
    "experience": [
        {{
            "title": "Job Title",
            "company": "Company Name",
            "dates": "MM YYYY - MM YYYY",
            "location": "City, Province",
            "highlights": ["Bullet point 1", "Bullet point 2", ...]
        }}
    ],
    "projects": [
        {{
            "name": "Project Name",
            "dates": "YYYY",
            "description": "Brief description",
            "technologies": ["Tech 1", "Tech 2"],
            "highlights": ["Bullet point 1", ...]
        }}
    ],
    "education": [
        {{
            "degree": "Degree Name",
            "institution": "University Name",
            "dates": "YYYY - YYYY",
            "details": ["Relevant coursework or achievements"]
        }}
    ],
    "skills": {{
        "languages": ["Python", "JavaScript"],
        "frameworks": ["React", "FastAPI"],
        "tools": ["Docker", "PostgreSQL"],
        "soft": ["Communication", "Leadership"]
    }}
}}

Use the job description keywords and language in your bullet points.
Return ONLY valid JSON, no markdown or additional text."""

    response = llm.invoke(prompt)
    content = response.content.strip()

    # Parse JSON from response
    try:
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        resume_data = json.loads(content.strip())
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Warning: Failed to parse resume JSON: {e}")
        resume_data = {}

    state["resume_data"] = resume_data
    return state


def cover_letter_writer_node(state: GraphState) -> GraphState:
    """
    Generate a cover letter for the job (if required).

    Only runs if job listing has requires_cover_letter: True.
    """
    job = state["job"]

    # Check if cover letter is required
    if not job.get("requires_cover_letter", False):
        state["cover_letter"] = ""
        return state

    jd = job.get("description", "")
    company = job.get("company", "")

    # Retrieve relevant profile context
    profile_context = retriever.retrieve_for_cover_letter(jd)

    # Get writing samples for tone matching
    writing_samples = retriever.retrieve_writing_samples()

    llm = get_llm()

    prompt = f"""You are writing a cover letter for a job application.

Job Details:
- Position: {job.get('title', 'N/A')}
- Company: {company}
- Description: {jd}

Candidate Profile:
{profile_context}

Writing Samples (for tone reference):
{writing_samples}

Write a professional cover letter (max 350 words) that:
1. Expresses genuine interest in the role and company
2. Highlights relevant experience and skills from the profile
3. Shows understanding of what the company does
4. Matches the tone and style of the writing samples
5. Ends with a call to action

Do NOT mention that you are an AI. Write as if you are the candidate.
Do not include a placeholder like [Your Name] - use a realistic name.
Do not use generic phrases like "I am writing to apply" - be specific and engaging."""

    response = llm.invoke(prompt)
    state["cover_letter"] = response.content.strip()

    return state


def qa_answerer_node(state: GraphState) -> GraphState:
    """
    Generate answers for application form questions.

    This node receives form fields from the applicator and generates
    targeted answers using RAG over the profile.
    """
    job = state["job"]
    jd = job.get("description", "")

    # This node expects qa_answers to already be set in state by the applicator
    # For initial generation, we'll use placeholder logic
    # The actual form field extraction happens in applicator.py

    qa_answers = state.get("qa_answers", {})

    # If no answers yet, this is a no-op - the applicator will extract fields
    # and call this again or the applicator handles field generation
    if not qa_answers:
        # Return empty dict - applicator will extract fields and generate answers
        pass

    state["qa_answers"] = qa_answers
    return state


def generate_qa_answer(question: str, job_description: str) -> str:
    """Generate an answer for a specific form question using RAG."""
    profile_context = retriever.retrieve_for_qa(job_description, question)

    llm = get_llm()

    # Determine expected length based on question
    is_long_form = len(question) > 100
    max_words = 300 if is_long_form else 50

    prompt = f"""You are answering a job application question.

Question: {question}

Job Description:
{job_description}

Relevant Profile Information:
{profile_context}

Provide a {max_words}-word answer that directly addresses the question.
Be specific and use concrete examples from your experience when possible.
Write in first person as if you are the candidate."""

    response = llm.invoke(prompt)

    # Truncate if needed
    answer = response.content.strip()
    words = answer.split()
    if len(words) > max_words:
        answer = " ".join(words[:max_words]) + "..."

    return answer
