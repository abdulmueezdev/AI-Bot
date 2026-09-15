import sys
from unittest.mock import MagicMock
sys.modules['structlog'] = MagicMock()
sys.modules['google'] = MagicMock()
sys.modules['google.genai'] = MagicMock()
sys.modules['google.genai.types'] = MagicMock()
sys.modules['supabase'] = MagicMock()
