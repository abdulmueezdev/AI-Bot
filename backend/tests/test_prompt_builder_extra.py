from __future__ import annotations

import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from app.prompt_builder import (
    _truncate_to_budget,
    _load_persona,
    build_prompt,
    PersonaConfig,
    count_tokens
)
from app.vector_store import RetrievalResult

class TestPromptBuilderExtra:
    def test_truncate_to_budget(self) -> None:
        text = "word " * 100
        truncated = _truncate_to_budget(text, 10)
        assert count_tokens(truncated) <= 10

    @patch("app.prompt_builder.get_settings")
    def test_load_persona_missing_file(self, mock_settings) -> None:
        mock_sett = MagicMock()
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_sett.get_clone_config_path.return_value = mock_path
        mock_settings.return_value = mock_sett
        
        cfg = _load_persona.__wrapped__("missing")
        assert "missing" in cfg.system_prompt
        assert cfg.examples == ""

    @patch("app.prompt_builder.get_settings")
    def test_load_persona_invalid_yaml(self, mock_settings, tmp_path: Path) -> None:
        file = tmp_path / "config.yaml"
        file.write_text("invalid: [yaml: :", encoding="utf-8")
        
        mock_sett = MagicMock()
        mock_sett.get_clone_config_path.return_value = file
        mock_settings.return_value = mock_sett
        
        cfg = _load_persona.__wrapped__("invalid")
        assert "invalid" in cfg.system_prompt
        
    @patch("app.prompt_builder.get_settings")
    def test_load_persona_with_examples(self, mock_settings, tmp_path: Path) -> None:
        file = tmp_path / "config.yaml"
        data = {
            "system_prompt": "Hello I am bot",
            "conversation_examples": [
                {"user": "hi", "assistant": "hello there"}
            ]
        }
        file.write_text(yaml.dump(data), encoding="utf-8")
        
        mock_sett = MagicMock()
        mock_sett.get_clone_config_path.return_value = file
        mock_settings.return_value = mock_sett
        
        cfg = _load_persona.__wrapped__("valid")
        assert "Hello I am bot" in cfg.system_prompt
        assert "hello there" in cfg.examples
        
    @patch("app.prompt_builder._load_persona")
    def test_build_prompt_overshoot(self, mock_load) -> None:
        mock_load.return_value = PersonaConfig(system_prompt="Short", examples="")
        
        # huge query
        query = "X " * 5000
        result = build_prompt("alucard", query, [])
        assert result.total_tokens <= 4000
        
    @patch("app.prompt_builder._load_persona")
    def test_build_prompt_history_truncation(self, mock_load) -> None:
        mock_load.return_value = PersonaConfig(system_prompt="Short", examples="")
        history = [{"role": "user", "content": "long " * 500}] * 5
        result = build_prompt("alucard", "hi", [], history=history)
        assert result.total_tokens <= 4000

    @patch("app.prompt_builder._load_persona")
    def test_build_prompt_all_blocks_truncation(self, mock_load) -> None:
        mock_load.return_value = PersonaConfig(system_prompt="Short", examples="")
        
        result = build_prompt(
            "alucard", 
            "X "*200, 
            [RetrievalResult(text="X "*2000, metadata={}, similarity=0.9)],
            calendar_context="C "*500,
            episodic_summaries=["E "*500],
            entity_context=[{"entity_type": "T", "entity_name": "N", "context": "C "*500}],
            dialectic_context=["D "*500],
            inject_calendar=True
        )
        assert result.total_tokens <= 4000

    @patch("app.prompt_builder._load_persona")
    def test_build_prompt_fallback_truncation(self, mock_load) -> None:
        mock_load.return_value = PersonaConfig(system_prompt="Short", examples="")
        
        # We need a combination of things that individually fit but collectively exceed TOTAL_BUDGET
        # Let's provide huge histories, memories, and everything.
        # Since the budgets are max caps, they might add up to more than TOTAL_BUDGET (4000).
        # history max=1500, context max=2000, memory max=1500. Total = 5000 > 4000.
        # So fallback truncation kicks in.
        history = [{"role": "user", "content": "H "*1000}] * 2 # 2000 tokens
        docs = [RetrievalResult(text="C "*2000, metadata={}, similarity=0.9)]
        
        result = build_prompt(
            "alucard",
            "query",
            docs,
            history=history,
            episodic_summaries=["M "*2000]
        )
        assert result.total_tokens <= 4000
