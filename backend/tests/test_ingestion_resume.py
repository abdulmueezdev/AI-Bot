import mock_deps
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path
import json
import datetime
from app.ingest import ingest_clone_data, DailyLimitReached, save_state, load_state

@pytest.fixture
def mock_settings(tmp_path):
    with patch("app.ingest.get_settings") as mock_get_settings:
        settings = MagicMock()
        data_path = tmp_path / "data"
        data_path.mkdir()
        
        # Create dummy file
        (data_path / "doc1.txt").write_text("Hello world")
        
        settings.get_clone_data_path.return_value = data_path
        settings.get_clone_persona_path.return_value = data_path / "persona.yaml"
        mock_get_settings.return_value = settings
        yield settings, data_path


def test_ingestion_state_preservation_on_exit(mock_settings):
    settings, data_path = mock_settings
    
    # Mock embed_texts to raise Quota depleted on the first yield
    async def mock_embed_texts(*args, **kwargs):
        raise RuntimeError("Quota depleted")
        yield [], 0
        
    with patch("app.ingest.embed_texts", side_effect=mock_embed_texts):
        import asyncio; stats = asyncio.run(ingest_clone_data("test_clone"))
        
    state_file = data_path.parent / "ingestion_state.json"
    assert state_file.exists()
    
    with open(state_file) as f:
        state = json.load(f)
        
    # Assuming the state is saved when Quota depleted is caught
    assert "last_file" in state
    assert "date" in state
    assert state["date"] == datetime.date.today().isoformat()
