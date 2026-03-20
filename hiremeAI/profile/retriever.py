"""Profile retriever - RAG queries over ChromaDB profile store."""

from hiremeAI.profile.loader import get_collection
from hiremeAI import config


def retrieve(
    query: str,
    types: list[str] | None = None,
    k: int | None = None,
) -> str:
    """
    Semantic search over the profile store.

    Args:
        query: The search query string
        types: Filter by chunk type, e.g. ["experience", "project"]. If None, searches all.
        k: Number of results to return. Defaults to config.RAG_TOP_K.

    Returns:
        Formatted string with retrieved context, ready to inject into LLM prompt.
    """
    if k is None:
        k = config.RAG_TOP_K

    collection = get_collection()

    # Build where clause for type filtering
    where_clause = {"type": {"$in": types}} if types else None

    results = collection.query(
        query_texts=[query],
        n_results=k,
        where=where_clause,
        include=["documents", "metadatas"],
    )

    if not results["documents"] or not results["documents"][0]:
        return "No relevant profile information found."

    # Format results for LLM context
    formatted_parts = []
    for i, doc in enumerate(results["documents"][0]):
        metadata = results["metadatas"][0][i]
        source = metadata.get("source", "unknown")
        label = metadata.get("label", "")
        chunk_type = metadata.get("type", "")

        formatted_parts.append(
            f"[{chunk_type.upper()}: {label} (from {source})]\n{doc}"
        )

    return "\n\n".join(formatted_parts)


def retrieve_experience(query: str, k: int = 3) -> str:
    """Retrieve experience chunks most relevant to query."""
    return retrieve(query, types=["experience"], k=k)


def retrieve_projects(query: str, k: int = 3) -> str:
    """Retrieve project chunks most relevant to query."""
    return retrieve(query, types=["project"], k=k)


def retrieve_skills(query: str, k: int = 2) -> str:
    """Retrieve skill chunks most relevant to query."""
    return retrieve(query, types=["skill"], k=k)


def retrieve_preferences() -> str:
    """Retrieve job preferences."""
    return retrieve("job preferences", types=["preference"], k=1)


def retrieve_writing_samples() -> str:
    """Retrieve writing samples for tone matching."""
    return retrieve("writing style sample", types=["writing_sample"], k=2)


def retrieve_certifications(query: str, k: int = 2) -> str:
    """Retrieve certification chunks."""
    return retrieve(query, types=["certification"], k=k)


def retrieve_for_resume(job_description: str) -> str:
    """Retrieve all profile data needed for resume generation."""
    parts = [
        retrieve_experience(job_description, k=3),
        retrieve_projects(job_description, k=2),
        retrieve_skills(job_description, k=1),
    ]
    return "\n\n---\n\n".join(parts)


def retrieve_for_cover_letter(job_description: str) -> str:
    """Retrieve profile data for cover letter generation."""
    parts = [
        retrieve_experience(job_description, k=2),
        retrieve_preferences(),
        retrieve_writing_samples(),
    ]
    return "\n\n---\n\n".join(parts)


def retrieve_for_qa(job_description: str, question: str) -> str:
    """Retrieve relevant profile context for answering a specific question."""
    combined = f"{job_description}\n\nQuestion: {question}"
    return retrieve(combined, types=["experience", "project", "skill"], k=3)
