"""Profile loader - reads markdown files, chunks, and embeds into ChromaDB."""

import hashlib
from pathlib import Path

import chromadb
from chromadb.config import Settings

from hiremeAI import config


def get_client() -> chromadb.PersistentClient:
    """Get or create ChromaDB client."""
    return chromadb.PersistentClient(
        path=str(config.CHROMA_PERSIST_DIR),
        settings=Settings(anonymized_telemetry=False),
    )


def _collection_exists(client: chromadb.PersistentClient, name: str) -> bool:
    """Return whether the named collection exists for this client."""
    try:
        collections = client.list_collections()
    except Exception:
        return False

    for collection in collections:
        collection_name = getattr(collection, "name", collection)
        if collection_name == name:
            return True
    return False


def _migrate_legacy_collection(client: chromadb.PersistentClient) -> None:
    """Copy legacy profile data into the canonical collection if needed."""
    if not _collection_exists(client, config.LEGACY_PROFILE_COLLECTION_NAME):
        return

    canonical = client.get_or_create_collection(
        name=config.PROFILE_COLLECTION_NAME,
        metadata={"description": "User profile for job applications"},
    )
    legacy = client.get_collection(config.LEGACY_PROFILE_COLLECTION_NAME)

    payload = legacy.get(include=["documents", "metadatas"])
    ids = payload.get("ids", [])
    documents = payload.get("documents", [])
    metadatas = payload.get("metadatas", [])

    if ids:
        canonical.upsert(ids=ids, documents=documents, metadatas=metadatas)


def get_collection():
    """Get or create the canonical profile collection, migrating legacy data if needed."""
    client = get_client()
    _migrate_legacy_collection(client)
    return client.get_or_create_collection(
        name=config.PROFILE_COLLECTION_NAME,
        metadata={"description": "User profile for job applications"},
    )


def get_type_from_filename(filename: str) -> str | None:
    """Map filename to chunk type."""
    mapping = {
        "experience.md": "experience",
        "projects.md": "project",
        "certifications.md": "certification",
        "skills.md": "skill",
        "preferences.md": "preference",
        "writing_samples.md": "writing_sample",
    }
    return mapping.get(filename)


def chunk_by_headings(content: str) -> list[tuple[str, str]]:
    """Split content by H2 headings (##). Returns list of (label, content)."""
    chunks = []
    lines = content.split("\n")
    current_label = "Introduction"
    current_content = []

    for line in lines:
        if line.startswith("## "):
            # Save previous chunk if there's content
            if current_content:
                chunks.append((current_label, "\n".join(current_content).strip()))
            # Start new chunk
            current_label = line[3:].strip()
            current_content = []
        else:
            current_content.append(line)

    # Save last chunk
    if current_content:
        chunks.append((current_label, "\n".join(current_content).strip()))

    return chunks


def load_profile() -> None:
    """Load all profile markdown files into ChromaDB."""
    collection = get_collection()

    if not config.PROFILE_DIR.exists():
        raise FileNotFoundError(f"Profile directory not found: {config.PROFILE_DIR}")

    markdown_files = list(config.PROFILE_DIR.glob("*.md"))
    if not markdown_files:
        raise FileNotFoundError(f"No markdown files found in {config.PROFILE_DIR}")

    for md_file in markdown_files:
        content = md_file.read_text(encoding="utf-8")
        chunk_type = get_type_from_filename(md_file.name)

        if not chunk_type:
            print(f"Skipping unknown file type: {md_file.name}")
            continue

        chunks = chunk_by_headings(content)

        for label, chunk_content in chunks:
            # Create unique ID based on source and label
            doc_id = hashlib.md5(
                f"{md_file.name}:{label}".encode()
            ).hexdigest()

            # Prepare metadata
            metadata = {
                "type": chunk_type,
                "source": md_file.name,
                "label": label,
            }

            # Add date if present in content (looking for patterns like "2024-05" or "2024")
            import re
            date_match = re.search(r"\b(20\d{2}(?:-\d{2})?)\b", chunk_content)
            if date_match:
                metadata["date"] = date_match.group(1)

            # Upsert into ChromaDB
            collection.upsert(
                ids=[doc_id],
                documents=[chunk_content],
                metadatas=[metadata],
            )

    print(f"Loaded profile from {len(markdown_files)} files into ChromaDB")


def clear_profile() -> None:
    """Clear all profile data from ChromaDB."""
    client = get_client()
    for name in (config.PROFILE_COLLECTION_NAME, config.LEGACY_PROFILE_COLLECTION_NAME):
        if _collection_exists(client, name):
            client.delete_collection(name)
    print("Cleared profile from ChromaDB")


if __name__ == "__main__":
    load_profile()
