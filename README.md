# Digital Clone AI Bot

The Digital Clone AI is a multi-tenant chatbot architecture designed to clone specific personas (e.g., Alucard, Bob, Carol) using a combination of persona prompting, RAG document knowledge, and Google Calendar integrations.

## Architecture

- **Backend:** FastAPI
- **LLM Routing:** Groq (primary) with OpenRouter (fallback)
- **Embeddings:** Gemini (`text-embedding-004`)
- **Vector Store:** ChromaDB
- **Memory:** 3-tier memory system (Session Buffer, Episodic Summary, Entity Database)

## Setup

1. Copy `.env.example` to `.env` and fill in your API keys.
2. Install dependencies: `pip install -r backend/requirements.txt`
3. Run the development server: `cd backend && uvicorn app.main:app --reload`

## Post-Deploy Steps (Render Ephemeral MVP)

Since the Render free tier uses an ephemeral filesystem, the ChromaDB local vector store is wiped every time a new deploy is pushed or the server spins down entirely. 

To restore your RAG knowledge base after a deployment:
1. SSH into the Render server, or run via Render shell.
2. Run the manual re-ingestion script:
   ```bash
   python3 scripts/reingest.py alucard
   ```
This script runs the full ingestion pipeline and typically takes under 5 minutes to restore the knowledge base.

*Note: Migration to Supabase pgvector is planned for post-v1.0.0 to resolve this persistence issue.*
