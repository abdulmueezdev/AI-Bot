# Alucard — Franz Kafka Digital Clone

A conversational AI system that embodies Franz Kafka's voice, 
drawing from his personal letters, diaries, and published works.

## Live Demo
https://ai-738trgzg9-abdulmueezs-projects-99b2e67f.vercel.app

## Tech Stack
- **LLM:** OpenRouter (Llama 4 Scout)
- **Embeddings:** Google Gemini gemini-embedding-001
- **Vector DB:** Supabase pgvector
- **Backend:** FastAPI deployed on Render
- **Frontend:** Next.js 14 deployed on Vercel
- **Memory:** 3-tier system (short-term, episodic ChromaDB, entity JSON)

## Architecture
The system employs a sophisticated Retrieval-Augmented Generation (RAG) pipeline to ensure the persona accurately reflects Franz Kafka's unique voice and perspectives. When a user sends a message, the system embeds the query using Gemini `gemini-embedding-001` and queries a Supabase `pgvector` database containing Kafka's works. The retrieved context is combined with a dynamic 3-tier memory system—managing short-term conversation history, episodic memories via ChromaDB, and persistent entity relationships via JSON—before being processed by the OpenRouter Llama 4 Scout LLM to generate a character-accurate response.

## Local Development
To run this project locally, follow these steps:

1. Clone the repository.
2. Setup the backend:
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```
3. Setup the frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
4. Ensure you have the necessary environment variables configured for Supabase, Groq, and Google Gemini in your `.env` files.

## Corpus
Kafka's works used as knowledge base:
- Letter to His Father
- The Metamorphosis  
- The Trial
- Letters to Milena
- Diaries 1910–1913
- Complete Short Stories
- Letters to Felice

## License
MIT
