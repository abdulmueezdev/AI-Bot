# Alucard — Digital Clone AI Bot

Alucard is a RAG-powered AI persona chatbot embodying Franz Kafka, built on free-tier infrastructure.

## Table of Contents
1. [Live Demo](#live-demo)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Database & RAG Pipeline](#database--rag-pipeline)
5. [Local Development](#local-development)
6. [Deployment](#deployment)
7. [Persona System](#persona-system)
8. [Project Status](#project-status)
9. [License & Credits](#license--credits)

## Live Demo
- **Frontend URL:** https://ai-bot-psi-three.vercel.app?_vercel_share=Yjy35iK3DEXxpARnbllJmtVApuS0DFI4(Wait as the Backend starts)
- **Backend URL:** https://ai-bot-tp8d.onrender.com (Render)

## Architecture
The system uses a modern decoupled architecture where a Next.js frontend communicates with a FastAPI backend. The backend manages the conversation state, retrieves relevant Kafka text snippets from Supabase via pgvector, formats the prompt under strict limits, and routes inference to the Groq LLM API.

```ascii
 [ User Browser ] 
        |
 (Next.js Frontend)
        |
        v
 [ FastAPI Backend ] <---> [ Supabase pgvector ] (RAG Context)
        |
        v
  [ Groq API ] (LLM Inference)
```

## Tech Stack
| Component | Technology | Purpose |
| --- | --- | --- |
| **Frontend Framework** | Next.js 14 | UI and client-side routing |
| **Frontend Host** | Vercel | Global CDN & serverless hosting |
| **Backend Framework** | FastAPI | Core logic, prompt assembly, and API endpoints |
| **Backend Host** | Render | Free-tier backend hosting |
| **Vector Store** | Supabase pgvector | Persistent vector database for RAG |
| **Embeddings** | Gemini (`text-embedding-004`) | Generating vector embeddings for text chunks |
| **LLM Inference** | Groq (`meta-llama/llama-4-scout-17b-16e-instruct`) | Fast text generation and persona adherence |

## Database & RAG Pipeline

### Supabase Setup
The RAG pipeline relies on a `documents` table in Supabase. It features an embedding column (sized to match `text-embedding-004` dimensions) and utilizes the pgvector extension to perform cosine similarity searches when the user queries the bot.

### Ingestion & Chunking
The `backend/app/ingest.py` script powers the ingestion pipeline:
- **`_chunk_plaintext`**: Recursively splits plain `.txt` files based on character counts while maintaining semantic boundaries and overlapping text.
- **`_chunk_markdown`**: Uses markdown headers (`##` and `###`) to preserve logical semantic groupings for structured documents.

### Corpus Composition
The current corpus consists of ~4,172 chunks derived from 7 distinct Kafka source texts:
1. `Daires_of_franz_kafka_1910-1913.txt`
2. `Franz_kafka_letter_to_felica.txt`
3. `Letter_to_my_father.txt`
4. `The_Metamorphosis.txt`
5. `The_trail.txt`
6. `complete_short_stories.txt`
7. `frans_kafka_milenaya_mektublar-eng.txt`

### Running an Ingestion Job
To run an ingestion job locally:
```bash
cd backend
source .venv/bin/activate
python3 -c "
from app.ingest import ingest_clone_data
import asyncio
async def run():
    stats = await ingest_clone_data('alucard', file_name='YOUR_FILE.txt')
    print(f'Done. Created: {stats.chunks_created}, Errors: {stats.errors}')
asyncio.run(run())
"
```

### Rate Limits
The Gemini free tier enforces a rate limit of ~1,000 embedding requests per day (rolling 24-hour window). To accommodate this, the pipeline groups documents into resumable batches and employs a safety stop at 800 chunks per run to avoid throttling.

## Local Development

1. **Clone the repository:**
   ```bash
   git clone git@github.com:abdulmueezdev/AI-Bot.git
   cd "AI Bot"
   ```

2. **Environment Variables:**
   Create a `.env` file based on `.env.example`. Required keys:
   - `GROQ_API_KEY`
   - `GEMINI_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`

3. **Backend Setup:**
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

4. **Frontend Setup:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Deployment
- **Backend:** Hosted on Render. The service auto-deploys via GitHub integration whenever code is pushed to the `main` branch.
- **Frontend:** Hosted on Vercel. Similarly auto-deploys on `main` branch pushes.

## Persona System
Kafka's distinct, brooding personality is defined centrally in `backend/clones/alucard/config.yaml`.
- **Rules:** The system dictates precise constraints, including length limits (maximum 50 words per response), voice rules (short, precise, non-poetic), forbidden words, identity facts (tuberculosis, 1922 Prague setting), and an explicit engagement rule requiring acknowledgment of user input before pivoting.
- **Identity Budget:** Controlled in `backend/app/prompt_builder.py`, `IDENTITY_BUDGET` ensures that up to 800 tokens of the system prompt are guaranteed to reach the LLM without truncation.

## Project Status
- **Corpus fully ingested:** Yes (~4,172 chunks across 7 source texts)
- **Backend deployed:** Yes (Render)
- **Frontend rebuilt:** Yes (Brutalist Stitch UI implemented and connected)
- **Pending:** N/A (v1.0 is stable and live)

## License & Credits
The literary works of Franz Kafka utilized in this corpus are in the **public domain**.
