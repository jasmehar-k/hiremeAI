"""Tests for profile collection compatibility."""

from hiremeAI import config
from hiremeAI.profile import loader


class FakeCollection:
    """Minimal in-memory Chroma-like collection for migration tests."""

    def __init__(self, name: str, payload: dict | None = None):
        self.name = name
        self.payload = payload or {"ids": [], "documents": [], "metadatas": []}

    def get(self, include=None):
        return self.payload

    def upsert(self, ids, documents, metadatas):
        self.payload = {
            "ids": list(ids),
            "documents": list(documents),
            "metadatas": list(metadatas),
        }


class FakeClient:
    """Minimal client that mimics the Chroma methods used by loader."""

    def __init__(self):
        self.collections = {}

    def list_collections(self):
        return list(self.collections.values())

    def get_collection(self, name):
        return self.collections[name]

    def get_or_create_collection(self, name, metadata=None):
        if name not in self.collections:
            self.collections[name] = FakeCollection(name)
        return self.collections[name]

    def delete_collection(self, name):
        self.collections.pop(name, None)


def test_get_collection_migrates_legacy_profile(monkeypatch):
    """Legacy profile data should be copied into the canonical collection."""
    client = FakeClient()
    client.collections[config.LEGACY_PROFILE_COLLECTION_NAME] = FakeCollection(
        config.LEGACY_PROFILE_COLLECTION_NAME,
        payload={
            "ids": ["doc-1"],
            "documents": ["legacy profile chunk"],
            "metadatas": [{"type": "experience", "source": "experience.md"}],
        },
    )
    monkeypatch.setattr(loader, "get_client", lambda: client)

    collection = loader.get_collection()

    assert collection.name == config.PROFILE_COLLECTION_NAME
    assert collection.get()["ids"] == ["doc-1"]
    assert collection.get()["documents"] == ["legacy profile chunk"]


def test_clear_profile_removes_canonical_and_legacy(monkeypatch):
    """Clear should remove both canonical and legacy collection names."""
    client = FakeClient()
    client.collections[config.PROFILE_COLLECTION_NAME] = FakeCollection(config.PROFILE_COLLECTION_NAME)
    client.collections[config.LEGACY_PROFILE_COLLECTION_NAME] = FakeCollection(
        config.LEGACY_PROFILE_COLLECTION_NAME
    )
    monkeypatch.setattr(loader, "get_client", lambda: client)

    loader.clear_profile()

    assert client.collections == {}
