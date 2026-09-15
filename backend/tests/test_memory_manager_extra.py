from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.memory_manager import MemoryManager

@pytest.mark.asyncio
class TestMemoryManagerExtra:
    async def test_flush_session_generates_and_stores(self) -> None:
        mm = MemoryManager()
        await mm.store_interaction("alucard", "sess1", "hello", "hi")
        
        with patch("app.memory_manager.MemoryManager._generate_summary", new_callable=AsyncMock) as mock_gen, \
             patch("app.memory_manager.MemoryManager._store_episodic_memory", new_callable=AsyncMock) as mock_store, \
             patch("app.memory_manager.MemoryManager._extract_and_store_entities", new_callable=AsyncMock) as mock_extract:
            
            mock_gen.return_value = "Summary text"
            summary = await mm.flush_session("alucard", "sess1")
            
            assert summary == "Summary text"
            mock_gen.assert_called_once()
            mock_store.assert_called_once()
            mock_extract.assert_called_once()
            
            assert await mm.get_session_context("alucard", "sess1") == []

    async def test_flush_empty_session_returns_none(self) -> None:
        mm = MemoryManager()
        summary = await mm.flush_session("alucard", "empty")
        assert summary is None

    def test_check_session_timeout(self) -> None:
        mm = MemoryManager()
        assert mm._check_session_timeout("alucard", "empty") is False
        
        from app.memory_manager import SessionState
        import time
        state = SessionState()
        state.last_activity = time.monotonic() - 4000
        mm._sessions[("alucard", "sess1")] = state
        assert mm._check_session_timeout("alucard", "sess1") is True

    @patch("app.memory_manager.MemoryManager.get_episodic_context", new_callable=AsyncMock)
    @patch("app.memory_manager.MemoryManager.get_entity_context", new_callable=AsyncMock)
    async def test_get_dialectic_context(self, mock_entities, mock_episodic) -> None:
        mm = MemoryManager()
        mock_episodic.return_value = ["Episodic summary"]
        mock_entities.return_value = [{"entity_type": "person", "entity_name": "Marcus", "context": "friend"}]
        
        res = await mm.get_dialectic_context("alucard", "nietzsche is great")
        assert len(res) == 2
        assert "Episodic summary" in res
        assert "person: Marcus — friend" in res
        
    async def test_get_dialectic_context_no_match(self) -> None:
        mm = MemoryManager()
        res = await mm.get_dialectic_context("alucard", "hello there")
        assert res == []

    def test_parse_entity_response(self) -> None:
        mm = MemoryManager()
        res = mm._parse_entity_response('[{"entity_name": "A"}]')
        assert len(res) == 1
        assert res[0]["entity_name"] == "A"
        
        res = mm._parse_entity_response('```json\n[{"entity_name": "A"}]\n```')
        assert len(res) == 1
        
        res = mm._parse_entity_response('invalid json')
        assert res == []

    @patch("app.vector_store._get_client")
    @patch("app.embedder.embed_texts", new_callable=AsyncMock)
    async def test_store_episodic_memory(self, mock_embed, mock_client) -> None:
        mm = MemoryManager()
        mock_embed.return_value = [[0.1, 0.2]]
        mock_db = MagicMock()
        mock_client.return_value = mock_db
        await mm._store_episodic_memory("alucard", "sess1", "Summ", 1)
        mock_db.table.assert_called_with("episodic_memory")

    @patch("app.vector_store._get_client")
    async def test_get_entity_context(self, mock_client) -> None:
        mm = MemoryManager()
        mock_db = MagicMock()
        mock_client.return_value = mock_db
        mock_response = MagicMock()
        mock_response.data = [{"entity_type": "t", "entity_name": "n", "context": "c"}]
        mock_db.table().select().eq().order().limit().execute.return_value = mock_response
        
        res = await mm.get_entity_context("alucard", "q")
        assert len(res) == 1
        assert res[0]["entity_name"] == "n"
        
    @patch("app.vector_store._get_client")
    @patch("app.llm_client.generate", new_callable=AsyncMock)
    async def test_extract_and_store_entities(self, mock_gen, mock_client) -> None:
        mm = MemoryManager()
        mock_resp = MagicMock()
        mock_resp.text = '[{"entity_name": "A", "entity_type": "B", "context": "C"}]'
        mock_gen.return_value = mock_resp
        mock_db = MagicMock()
        mock_client.return_value = mock_db
        
        await mm._extract_and_store_entities("alucard", "summary")
        mock_db.table.assert_called_with("entity_memory")

    @patch("app.llm_client.generate", new_callable=AsyncMock)
    async def test_generate_summary(self, mock_gen) -> None:
        mm = MemoryManager()
        mock_resp = MagicMock()
        mock_resp.text = "this is a summary"
        mock_gen.return_value = mock_resp
        
        res = await mm._generate_summary("alucard", "transcript")
        assert res == "this is a summary"
