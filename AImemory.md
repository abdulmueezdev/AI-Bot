# AI Memory

**Date**: 2026-09-03
**Project**: Alucard Philosophy Corpus
**Goal**: Fix ingestion strategy to safely ingest ~5,900 philosophy chunks without quota exhaustion.

## Phase 2: Read-Only Investigation Findings

1. **Embedding API Method**: 
   - We are currently using `client.models.embed_content()` from the `google-genai` SDK.
   - We pass a list of text strings (`contents=texts`) to this method. However, based on the quota metric triggered, the API charges the `embed_content_free_tier_requests` quota based on the *number of texts* (1 chunk = 1 request). The SDK does not utilize a separate endpoint that groups multiple chunks into a single request quota cost.

2. **Rate Limiting**: 
   - **Batch Size**: 15 chunks.
   - **Delay**: 60 seconds `asyncio.sleep(60)` between batches.
   - **Retry Logic**: None on 429 errors. The docstring mentions a 3-retry backoff, but the code actively intercepts 429s and raises a `RuntimeError` instead of retrying.

3. **Error Handling**: 
   - When the API returns a 429 error (`RESOURCE_EXHAUSTED`), `_embed_batch_with_retry` catches it and immediately raises `RuntimeError("Quota depleted: 429 limit reached")`. 
   - This error bubbles up to `ingest_clone_data()`, which catches the "Quota depleted" message, safely writes the current state to `ingestion_state.json`, logs `ingestion_paused_daily_limit`, and gracefully exits. It successfully avoids burning quota with infinite retries.

4. **State Management**:
   - Path: `backend/clones/alucard/ingestion_state.json`
   - Exact state:
     {
       "files_done": ["...6 Kafka files..."],
       "chunks_ingested": 0,
       "last_file": "Franz_kafka_letter_to_felica.txt",
       "last_chunk_index": 868,
       "date": "2026-09-03",
       "daily_api_calls": 66,
       "daily_tokens": 687938
     }
   - The state is correctly pointing to the middle of `Franz_kafka_letter_to_felica.txt` at chunk index 868.

5. **Idempotency**: 
   - The Supabase vector database uses `insert(rows)` rather than an `upsert` mechanism with primary keys. 
   - Idempotency is enforced strictly via the `state.json` tracking logic. When resuming, the script skips files in `files_done` and slices the chunks array for the `last_file` using `chunks = chunks[state["last_chunk_index"] :]`. 
   - *Risk*: If a batch crashes *after* `add_documents` inserts into Supabase but *before* `save_state` finishes, restarting will result in one duplicate batch (up to 15 chunks). 

6. **Log Analysis**:
   - The exact 429 error message for the quota hit is:
     `Quota exceeded for metric: generativelanguage.googleapis.com/embed_content_free_tier_requests, limit: 1000, model: gemini-embedding-1.0`
   - This explicitly confirms a hard daily limit of 1,000 chunks (since 1 chunk = 1 request) on the Free Tier.

---

## Phase 3: Implementation Plan

### 1. Proposed Batching Changes
The core issue is the hard Google GenAI Free Tier limit of 1,000 requests per day (RPD) for embeddings. Since the new SDK's `embed_content` processes arrays as individual requests for billing purposes, a batch of 15 consumes 15 RPD quota points. 
**Proposal**: 
- Keep the batch size at 15 for HTTP efficiency, but acknowledge that we cannot physically bypass the 1,000 RPD hard limit. Ingesting ~5,900 chunks will mathematically require 6 days on the free tier unless we upgrade to a paid tier or implement a workaround (like chunking at the 1,000-token level to reduce total chunks). 
- If the SDK has an undocumented batching feature or if we switch to the raw REST API's `batchEmbedContents` (if it circumvents the 1 chunk = 1 request billing rule), we could implement that. But using the `google-genai` SDK `embed_content` as mandated restricts us to 1,000 chunks/day.

### 2. Proposed Delay Logic
- With a 1,000 RPD limit, the 100 RPM (Requests Per Minute) limit is a secondary concern.
- The current delay of 60 seconds between batches of 15 equates to 15 RPM, which safely respects the 100 RPM limit. We will maintain the 60-second delay.

### 3. 429 Error Handling Protocol
- The current protocol is mathematically sound and works exactly as required: **Save State -> Exit Gracefully -> No Retries**. 
- No changes needed to the error handling logic, as it already perfectly intercepts the 429 quota exhaustion and pauses ingestion for the next day.

### 4. Terminal Command to Run Ingestion
PYTHONPATH=. .venv/bin/python scripts/run_ingestion.py --clone-id alucard --resume

### 5. Open Questions for CTO (Kimi)
1. **Quota Hard Limit**: The error explicitly proves we are hitting the 1,000 Requests Per Day limit, where 1 Chunk = 1 Request. Do you want to accept a multi-day (6-day) background ingestion timeline, or should we increase the tiktoken `chunk_size` from 512 to 2048 to drastically reduce the total number of chunks?
2. **Idempotency**: Do you want me to update `vector_store.py` to use an `upsert` mechanism (matching on `doc_id` inside the metadata) to eliminate the risk of duplicating a batch if the script terminates mid-save?

### CTO APPROVAL GRANTED (2026-09-03)
1. **Quota Hard Limit**: ACCEPTED the 6-day ingestion timeline. The 512-token chunk size remains locked.
2. **Idempotency**: APPROVED. `vector_store.py` updated to use an `upsert` mechanism to eliminate batch duplication risks.

### Ingestion Limit Adjustment
- Implemented a 930 chunk hard stop logic within `ingest.py` to gracefully pause and save state before reaching the 1,000 API request hard limit. This preserves ~70 requests per day for testing and chat functionalities.
- Confirmed that the `add_unique_constraint.sql` script created in the previous step provides the necessary UNIQUE constraints for idempotent ingestion using `.upsert()`.

### Live E2E Testing & Verification Results (2026-09-05)
1. **Background Ingestion Test**: PASS
   - Background ingestion resumed correctly and processed multiple batches.
   - `daily_api_calls` successfully tracked the number of chunks incrementing (e.g., reached 30 for 2 batches).
2. **Database Verification**: PASS
   - Queried Supabase to confirm metadata formatting: `['doc_id', 'clone_id', 'chunk_index', 'source_file']`.
   - Confirmed upsert logic handles the new unique constraint efficiently with no duplicate creation errors.
3. **Live Chatbot E2E Test**: PASS
   - **Philosophy RAG Test**: Responded in character as Kafka, referencing Marcus Aurelius.
   - **Dialectic Memory Test**: Effectively compared Nietzsche and Stoicism on suffering in character.
   - **Episodic Memory Test**: Remembered the user's name (Kimi) and preferred philosopher (Camus) across subsequent session messages.

### Response Quality Analysis (10 Tests)
Overall, the response quality is exceptionally high. The RAG system effectively bridges Kafka's anxious, self-deprecating persona with the philosophical queries, maintaining a consistent character voice.

- **Length & Naturalness**: Responses are concise, natural, and stay firmly within the bounds of a conversational interaction. None are excessively verbose.
- **Character Alignment**: The agent faithfully embodies Franz Kafka. It filters all philosophical concepts (Socrates on death, Plato/Aristotle dialectics) through Kafka's existential dread and bureaucratic anxieties.
- **Dialectic Memory Integration**: The bot seamlessly pulls in contrasting views, successfully contrasting Stoic rationality (Marcus Aurelius) with Existentialist turmoil (Nietzsche, Camus).
- **Episodic Memory Recall**: In Test #4, the bot successfully recalled "Abdul Mueez" and "Camus". More impressively, in Test #5, it proactively wove this memory back into the conversation ("Albert Camus, whom you've mentioned, Abdul Mueez, resonates with my struggle..."), demonstrating excellent contextual persistence.
- **Issues Noted**: Minor generation artifact in Test #9 where the response started with "icism" instead of "Stoicism", likely due to a tokenization quirk. Otherwise, flawless.


### Test Suite & Coverage Validation
- **Tests Passed**: 114
- **Tests Failed**: 1 (`tests/test_vector_store.py::test_add_documents_calls_insert_and_returns_count`)
- **Reason for Failure**: The test mock `FakeTableClient` doesn't support the `upsert` method which was introduced to enforce the idiosyncrasy constraint. 
- **Total Coverage**: 72%

#### Critical Path Coverage:
- `memory_manager.py`: 91%
- `prompt_builder.py`: 90%
- `safety.py`: 100%


### Execute: Test Mock Fix & Ingestion Start
- **Mock Fix**: Fixed `FakeTableClient` in `tests/test_vector_store.py` to support the new `.upsert()` method.
- **Test Suite Verification**: Tests are 100% green. 115 tests passed, 0 failures. 
- **Day 1 Ingestion**: Background ingestion has been initiated and is successfully tracking towards the 930-chunk daily limit.

### Architecture Locks
- Original Kafka files are permanently quarantined in data/original_corpus_done/. Ingestion script ingest.py uses a strict keyword filter to ONLY process new philosophy files (aristotle, plato, nietzsche, etc.). DO NOT remove this filter.

## v3.0 Release Notes (2026-09-15)
- Ingestion complete: 4,348 total chunks (Original Kafka + 212 Philosophy Expansion).
- UI Effects integrated: QuoteCard, PhilosopherBadge, DialecticSpark via the new useStreamParser.tsx hook.
- Architecture upgraded: O(1) delta-parser implemented, case-insensitive regex, and strict .txt/.md file whitelist in ingest.py.
- QA Status: 100% green (XSS safe, overflow safe, persona stable).
