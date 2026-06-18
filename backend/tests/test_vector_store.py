import pytest
import types
from dataclasses import dataclass

import app.vector_store as vector_store

# simple fake response container to emulate supabase execute() return
@dataclass
class FakeResponse:
    data: list | None = None
    count: int | None = None

# Fake client that exposes .table(...).insert(...).execute(), .rpc(...).execute() patterns
class FakeTableClient:
    def __init__(self, parent, behavior):
        self._parent = parent
        self._name = None
        self._behavior = behavior
        self._eq_filters = []

    def table(self, name):
        self._name = name
        return self

    def insert(self, rows):
        self._parent._last_insert_rows = rows
        return self

    def execute(self):
        if self._behavior.get("raise_exception"):
            raise RuntimeError("Database error")
        return FakeResponse(data=self._behavior.get("insert_response", []))

    def select(self, *args, **kwargs):
        self._last_select = True
        return self

    def eq(self, key, val):
        self._eq_filters.append((key, val))
        return self

    def delete(self):
        self._last_delete = True
        return self

class FakeRPCClient:
    def __init__(self, response_data, should_raise=False):
        self._response_data = response_data
        self._should_raise = should_raise

    def rpc(self, name, params):
        self._last_rpc_name = name
        self._last_rpc_params = params
        
        class ExecWrapper:
            def __init__(self, data, should_raise):
                self.data = data
                self._should_raise = should_raise
            def execute(self):
                if self._should_raise:
                    raise RuntimeError("RPC error")
                return FakeResponse(data=self.data)
        return ExecWrapper(self._response_data, self._should_raise)

class FakeCountClient:
    def __init__(self, count, should_raise=False):
        self._count = count
        self._should_raise = should_raise
    def table(self, name):
        self._name = name
        return self
    def select(self, *args, **kwargs):
        return self
    def eq(self, key, val):
        return self
    def execute(self):
        if self._should_raise:
            raise RuntimeError("Count error")
        return FakeResponse(data=[], count=self._count)

@pytest.mark.asyncio
async def test_add_documents_calls_insert_and_returns_count(monkeypatch):
    fake = types.SimpleNamespace()
    fake._last_insert_rows = None
    fake_client = FakeTableClient(fake, behavior={"insert_response": []})

    vector_store._client = fake_client

    chunks = ["a", "b"]
    embeddings = [[0.1, 0.2], [0.3, 0.4]]
    metadatas = [{"source_file": "f1"}, {"source_file": "f2"}]
    ids = ["id1", "id2"]

    count = await vector_store.add_documents("clone_x", chunks=chunks, embeddings=embeddings, metadatas=metadatas, ids=ids)
    assert count == 2
    assert isinstance(fake._last_insert_rows, list)
    assert fake._last_insert_rows[0]["clone_id"] == "clone_x"
    assert fake._last_insert_rows[0]["metadata"]["doc_id"] == "id1"

@pytest.mark.asyncio
async def test_query_returns_filtered_results_and_dedup(monkeypatch):
    rows = [
        {"content": "same", "metadata": {"source_file": "f"}, "similarity": "0.95"},
        {"content": "same", "metadata": {"source_file": "f"}, "similarity": "0.90"},
        {"content": "other", "metadata": {"source_file": "f"}, "similarity": "0.85"},
        {"content": "low", "metadata": {"source_file": "f"}, "similarity": "0.10"},
    ]
    fake_rpc_client = FakeRPCClient(rows)
    monkeypatch.setattr(vector_store, "_get_client", lambda: fake_rpc_client)

    class FakeSettings:
        top_k_results = 2
        similarity_threshold = 0.5
    monkeypatch.setattr(vector_store, "get_settings", lambda: FakeSettings())

    import random
    monkeypatch.setattr(random, "sample", lambda pool, k: pool[:k])

    results = await vector_store.query("clone_a", [0.1, 0.2], top_k=2)
    assert len(results) <= 2
    assert any(r.text == "same" for r in results)
    assert all(r.similarity >= FakeSettings.similarity_threshold for r in results)

@pytest.mark.asyncio
async def test_query_returns_empty_list_on_exception(monkeypatch):
    fake_rpc_client = FakeRPCClient([], should_raise=True)
    monkeypatch.setattr(vector_store, "_get_client", lambda: fake_rpc_client)

    class FakeSettings:
        top_k_results = 2
        similarity_threshold = 0.5
    monkeypatch.setattr(vector_store, "get_settings", lambda: FakeSettings())

    results = await vector_store.query("clone_a", [0.1, 0.2], top_k=2)
    assert results == []

@pytest.mark.asyncio
async def test_get_counts_and_deletes(monkeypatch):
    monkeypatch.setattr(vector_store, "_get_client", lambda: FakeCountClient(count=5))
    cnt = await vector_store.get_collection_count("clone_x")
    assert cnt == 5

    monkeypatch.setattr(vector_store, "_get_client", lambda: FakeCountClient(count=3))
    cnt2 = await vector_store.get_file_chunk_count("clone_x", "myfile.py")
    assert cnt2 == 3

    class FakeDelClient:
        def table(self, name):
            return self
        def delete(self):
            return self
        def eq(self, k, v):
            return self
        def execute(self):
            return FakeResponse(data=[{"id": 1}, {"id": 2}])
            
    monkeypatch.setattr(vector_store, "_get_client", lambda: FakeDelClient())
    deleted = await vector_store.delete_collection("clone_x")
    assert deleted is True
    deleted_count = await vector_store.delete_file_chunks("clone_x", "f")
    assert deleted_count == 2

@pytest.mark.asyncio
async def test_get_counts_and_deletes_exceptions(monkeypatch):
    monkeypatch.setattr(vector_store, "_get_client", lambda: FakeCountClient(count=5, should_raise=True))
    cnt = await vector_store.get_collection_count("clone_x")
    assert cnt == 0

    cnt2 = await vector_store.get_file_chunk_count("clone_x", "myfile.py")
    assert cnt2 == 0

    class FakeDelClientThrows:
        def table(self, name):
            return self
        def delete(self):
            return self
        def eq(self, k, v):
            return self
        def execute(self):
            raise RuntimeError("Delete error")
            
    monkeypatch.setattr(vector_store, "_get_client", lambda: FakeDelClientThrows())
    deleted = await vector_store.delete_collection("clone_x")
    assert deleted is False
    deleted_count = await vector_store.delete_file_chunks("clone_x", "f")
    assert deleted_count == 0

@pytest.mark.asyncio
async def test_delete_with_no_data(monkeypatch):
    class FakeDelClientEmpty:
        def table(self, name):
            return self
        def delete(self):
            return self
        def eq(self, k, v):
            return self
        def execute(self):
            return FakeResponse(data=[])
            
    monkeypatch.setattr(vector_store, "_get_client", lambda: FakeDelClientEmpty())
    deleted = await vector_store.delete_collection("clone_x")
    assert deleted is False
    deleted_count = await vector_store.delete_file_chunks("clone_x", "f")
    assert deleted_count == 0

def test_get_client(monkeypatch):
    # Test that _get_client creates client successfully
    class FakeSettings:
        supabase_url = "http://fake-url.com"
        supabase_key = "fake-key"
    monkeypatch.setattr(vector_store, "get_settings", lambda: FakeSettings())
    
    # Reset the global
    vector_store._client = None
    
    def fake_create_client(url, key):
        return "fake_supabase_client"
    
    monkeypatch.setattr(vector_store, "create_client", fake_create_client)
    
    client = vector_store._get_client()
    assert client == "fake_supabase_client"
    
    # Next call should return same client
    client2 = vector_store._get_client()
    assert client2 == "fake_supabase_client"

def test_get_client_raises(monkeypatch):
    # Test that _get_client raises if variables are missing
    class FakeSettings:
        supabase_url = None
        supabase_key = None
    monkeypatch.setattr(vector_store, "get_settings", lambda: FakeSettings())
    
    vector_store._client = None
    
    with pytest.raises(RuntimeError, match="SUPABASE_URL and SUPABASE_KEY must be set in environment variables."):
        vector_store._get_client()
